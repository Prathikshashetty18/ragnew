"""
Controlled Migration Script: Local Document Files -> S3 Object Storage (e.g. Backblaze B2)

Scans all ACTIVE documents (and radiology images) in the database,
locates local files on disk, uploads to private S3-compatible object storage,
and validates size and checksum integrity.

DOES NOT:
- alter database rows or schema
- delete local files
- expose secrets or auth tokens
"""

import argparse
import hashlib
import json
import logging
import mimetypes
import os
import sys

# Ensure backend path is available
sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(__file__), "..")))

from app import config
from app.database import SessionLocal, Document, RadiologyReport
from app.storage import S3StorageProvider, sanitize_filename

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("migrate_files_to_object_storage")


def compute_md5(data: bytes) -> str:
    return hashlib.md5(data).hexdigest()


def find_local_file(file_path: str, safe_name: str) -> str:
    """Finds the local file either at its exact path or inside UPLOAD_DIR or SEED_DIR."""
    if file_path and os.path.isabs(file_path) and os.path.exists(file_path):
        return file_path

    candidate1 = os.path.join(config.UPLOAD_DIR, safe_name)
    if os.path.exists(candidate1):
        return candidate1

    candidate2 = os.path.join(config.SEED_DIR, safe_name)
    if os.path.exists(candidate2):
        return candidate2

    if file_path:
        base = os.path.basename(file_path.replace("\\", "/"))
        candidate3 = os.path.join(config.UPLOAD_DIR, base)
        if os.path.exists(candidate3):
            return candidate3

    return ""


def run_migration(dry_run: bool = False):
    logger.info("=" * 60)
    logger.info("CLINICAL RAG CDSS - S3 / BACKBLAZE B2 FILE MIGRATION")
    logger.info("=" * 60)

    safe_cfg = config.get_safe_storage_config()
    logger.info(f"Target Bucket: {config.S3_BUCKET_NAME or 'NOT CONFIGURED'}")
    logger.info(f"Endpoint URL:  {safe_cfg.get('endpoint', 'not set')}")
    logger.info(f"Region:        {safe_cfg.get('region', 'not set')}")
    logger.info(f"Access Key:    {'[SET]' if safe_cfg.get('access_key_set') else '[MISSING]'}")
    logger.info(f"Secret Key:    {'[SET]' if safe_cfg.get('secret_key_set') else '[MISSING]'}")
    logger.info(f"Dry Run Mode:  {dry_run}")
    logger.info("-" * 60)

    if not dry_run:
        if not config.S3_BUCKET_NAME or not config.S3_ENDPOINT_URL or not config.S3_ACCESS_KEY_ID or not config.S3_SECRET_ACCESS_KEY:
            logger.error("S3 credentials not fully configured in environment. Cannot proceed with live upload.")
            logger.error("Set S3_BUCKET_NAME, S3_ENDPOINT_URL, S3_ACCESS_KEY_ID, and S3_SECRET_ACCESS_KEY.")
            return False

        s3_provider = S3StorageProvider()
    else:
        s3_provider = None

    db = SessionLocal()
    try:
        active_docs = db.query(Document).filter(Document.approval_status == "ACTIVE").all()
        logger.info(f"Found {len(active_docs)} ACTIVE documents in database.")

        rad_reports = db.query(RadiologyReport).filter(RadiologyReport.image_path.isnot(None)).all()
        logger.info(f"Found {len(rad_reports)} radiology reports with image paths.")

        results = {
            "total_documents": len(active_docs),
            "uploaded": 0,
            "skipped": 0,
            "missing_local": 0,
            "failed": 0,
            "items": []
        }

        # Process active documents
        for doc in active_docs:
            safe_name = sanitize_filename(doc.name or os.path.basename(doc.file_path or ""))
            local_path = find_local_file(doc.file_path, safe_name)

            item = {
                "id": doc.id,
                "name": doc.name,
                "scope": doc.scope,
                "safe_name": safe_name,
                "canonical_key": f"documents/{safe_name}",
                "local_found": bool(local_path),
                "status": "PENDING"
            }

            if not local_path:
                logger.warning(f"[MISSING] Doc {doc.id} ('{doc.name}'): Local file not found on disk.")
                item["status"] = "MISSING_LOCAL"
                results["missing_local"] += 1
                results["items"].append(item)
                continue

            with open(local_path, "rb") as f:
                content = f.read()

            file_size = len(content)
            file_md5 = compute_md5(content)
            item["size_bytes"] = file_size
            item["md5"] = file_md5

            mime_type, _ = mimetypes.guess_type(local_path)
            if not mime_type:
                mime_type = "application/octet-stream"
            item["mime_type"] = mime_type

            if dry_run:
                logger.info(f"[DRY-RUN] Would upload Doc {doc.id}: '{safe_name}' ({file_size} bytes, {mime_type}) -> {item['canonical_key']}")
                item["status"] = "DRY_RUN_OK"
                results["uploaded"] += 1
                results["items"].append(item)
            else:
                try:
                    # Check if object already exists in B2
                    if s3_provider.exists(item["canonical_key"]):
                        head = s3_provider.client.head_object(
                            Bucket=s3_provider.bucket_name,
                            Key=item["canonical_key"]
                        )
                        remote_size = head.get("ContentLength")
                        remote_etag = head.get("ETag", "").strip('"').lower()

                        if remote_size == file_size and remote_etag == file_md5.lower():
                            logger.info(
                                f"[ALREADY EXISTS IDENTICAL] Doc {doc.id}: '{item['canonical_key']}' "
                                f"already in B2 ({remote_size} bytes, ETag: {remote_etag}). Reusing object without overwriting."
                            )
                            item["status"] = "ALREADY_EXISTS_IDENTICAL"
                            results["already_exists"] = results.get("already_exists", 0) + 1
                            item["remote_size"] = remote_size
                            item["remote_etag"] = remote_etag
                            results["items"].append(item)
                            continue
                        else:
                            logger.error(
                                f"[CRITICAL CONFLICT] Doc {doc.id}: '{item['canonical_key']}' already exists in B2 but DIFFERS! "
                                f"Remote: {remote_size} bytes, ETag {remote_etag} vs Local: {file_size} bytes, MD5 {file_md5}. Aborting!"
                            )
                            item["status"] = "CONFLICT_DIFFERENT"
                            results["failed"] += 1
                            results["items"].append(item)
                            return False

                    # New object: upload to B2
                    s3_provider.upload(safe_name, content, content_type=mime_type)

                    # Post-upload verification
                    head = s3_provider.client.head_object(
                        Bucket=s3_provider.bucket_name,
                        Key=item["canonical_key"]
                    )
                    remote_size = head.get("ContentLength")
                    remote_etag = head.get("ETag", "").strip('"').lower()

                    if remote_size != file_size:
                        logger.error(
                            f"[VERIFY FAILED] Doc {doc.id}: Size mismatch for '{item['canonical_key']}'. "
                            f"Uploaded {file_size} bytes, remote reports {remote_size} bytes."
                        )
                        item["status"] = "VERIFY_FAILED"
                        results["failed"] += 1
                        results["items"].append(item)
                        return False

                    logger.info(
                        f"[UPLOADED & VERIFIED] Doc {doc.id}: '{safe_name}' -> {item['canonical_key']} "
                        f"({file_size} bytes, ETag: {remote_etag})"
                    )
                    item["status"] = "SUCCESS"
                    item["remote_size"] = remote_size
                    item["remote_etag"] = remote_etag
                    results["uploaded"] += 1
                    results["items"].append(item)
                except Exception as e:
                    logger.error(f"[ERROR] Doc {doc.id} upload failed: {e}")
                    item["status"] = f"ERROR: {e}"
                    results["failed"] += 1
                    results["items"].append(item)
                    return False

        logger.info("=" * 60)
        logger.info("MIGRATION SUMMARY:")
        logger.info(f"  Total Processed:       {len(active_docs)}")
        logger.info(f"  Newly Uploaded:        {results.get('uploaded', 0)}")
        logger.info(f"  Already Exists/Reused: {results.get('already_exists', 0)}")
        logger.info(f"  Missing Local:         {results.get('missing_local', 0)}")
        logger.info(f"  Failed:                {results.get('failed', 0)}")
        logger.info("=" * 60)

        # Output summary JSON
        report_path = os.path.join(config.BASE_DIR, "..", "s3_migration_summary.json")
        try:
            with open(report_path, "w", encoding="utf-8") as f:
                json.dump(results, f, indent=2)
            logger.info(f"Detailed summary written to {report_path}")
        except Exception:
            pass

        if dry_run:
            return results["failed"] == 0
        return results["failed"] == 0 and results["missing_local"] == 0 and (results.get("uploaded", 0) + results.get("already_exists", 0) == len(active_docs))
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Migrate local document files to S3 / Backblaze B2 object storage")
    parser.add_argument("--dry-run", action="store_true", help="Perform audit and verification without uploading")
    args = parser.parse_args()

    success = run_migration(dry_run=args.dry_run)
    sys.exit(0 if success else 1)