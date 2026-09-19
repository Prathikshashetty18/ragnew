/**
 * Centralized Frontend API Configuration
 *
 * Provides environment-aware API URL resolution.
 * - In development (import.meta.env.DEV): falls back to 'http://127.0.0.1:8000'
 *   if VITE_API_BASE_URL is not set, preserving out-of-the-box local development.
 * - In production: uses VITE_API_BASE_URL if set, or empty string '' for same-origin
 *   reverse-proxy routing.
 */

const envBaseUrl = import.meta.env.VITE_API_BASE_URL;

export const API_BASE_URL: string =
  typeof envBaseUrl === "string" && envBaseUrl.trim() !== ""
    ? envBaseUrl.trim().replace(/\/+$/, "")
    : import.meta.env.DEV
    ? "http://127.0.0.1:8000"
    : "";

/**
 * Resolves an API endpoint, document path, or static file path against
 * the configured API base URL without duplicate slashes.
 *
 * Examples:
 *   getApiUrl("/api/patients") -> "http://127.0.0.1:8000/api/patients" (dev)
 *   getApiUrl("/api/documents/123/file") -> "http://127.0.0.1:8000/api/documents/123/file" (dev)
 */
export function getApiUrl(path: string): string {
  if (!path) return API_BASE_URL;
  if (/^https?:\/\//i.test(path)) {
    return path;
  }
  const cleanPath = path.startsWith("/") ? path : `/${path}`;
  if (!API_BASE_URL) {
    return cleanPath;
  }
  return `${API_BASE_URL}${cleanPath}`;
}
