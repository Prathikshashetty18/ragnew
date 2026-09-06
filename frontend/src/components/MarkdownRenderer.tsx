import React from "react";

interface MarkdownRendererProps {
  content: string;
}

export const MarkdownRenderer: React.FC<MarkdownRendererProps> = ({ content }) => {
  if (!content) return null;

  const lines = content.split("\n");
  const elements: React.ReactNode[] = [];

  let listItems: string[] = [];
  let isNumberedList = false;
  let inList = false;

  let tableRows: string[][] = [];
  let inTable = false;

  let codeBlockLines: string[] = [];
  let inCodeBlock = false;
  let codeLanguage = "";

  const parseInlineMarkdown = (text: string): string => {
    // Bold: **text**
    let parsed = text.replace(/\*\*(.*?)\*\*/g, '<strong class="font-semibold text-slate-900">$1</strong>');
    // Italic: *text*
    parsed = parsed.replace(/\*(.*?)\*/g, '<em class="italic text-slate-800">$1</em>');
    // Inline code: `code`
    parsed = parsed.replace(/`(.*?)`/g, '<code class="bg-slate-100 px-1.5 py-0.5 rounded font-mono text-xs text-rose-900 border border-slate-200/60">$1</code>');
    // Citations: [1], [2], [1, 2]
    parsed = parsed.replace(/(?<!\w)\[(\d+(?:,\s*\d+)*)\]/g, '<span class="inline-flex items-center px-1.5 py-0.5 rounded text-[10.5px] font-bold font-mono bg-rose-50 text-rose-900 border border-rose-200/80 mx-0.5 align-baseline select-none">[$1]</span>');
    return parsed;
  };

  const flushList = (key: string) => {
    if (listItems.length > 0) {
      if (isNumberedList) {
        elements.push(
          <ol key={key} className="list-decimal pl-5 my-3 space-y-2 text-slate-800 text-[14px] leading-relaxed">
            {listItems.map((item, idx) => (
              <li key={idx} dangerouslySetInnerHTML={{ __html: parseInlineMarkdown(item) }} />
            ))}
          </ol>
        );
      } else {
        elements.push(
          <ul key={key} className="list-disc pl-5 my-3 space-y-2 text-slate-800 text-[14px] leading-relaxed">
            {listItems.map((item, idx) => (
              <li key={idx} dangerouslySetInnerHTML={{ __html: parseInlineMarkdown(item) }} />
            ))}
          </ul>
        );
      }
      listItems = [];
      inList = false;
      isNumberedList = false;
    }
  };

  const flushTable = (key: string) => {
    if (tableRows.length > 0) {
      const headers = tableRows[0];
      const bodyRows = tableRows.slice(tableRows.length > 1 && tableRows[1][0]?.includes("-") ? 2 : 1);
      
      elements.push(
        <div key={key} className="overflow-x-auto my-3 border border-slate-200 rounded-xl shadow-2xs">
          <table className="min-w-full divide-y divide-slate-200 text-xs text-left">
            <thead className="bg-slate-50 text-slate-700 font-bold uppercase tracking-wider">
              <tr>
                {headers.map((h, idx) => (
                  <th key={idx} className="px-3.5 py-2.5 border-r last:border-0 border-slate-200" dangerouslySetInnerHTML={{ __html: parseInlineMarkdown(h.trim()) }} />
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 bg-white text-slate-700">
              {bodyRows.map((row, rIdx) => (
                <tr key={rIdx} className="hover:bg-slate-50/50 transition-colors">
                  {row.map((cell, cIdx) => (
                    <td key={cIdx} className="px-3.5 py-2 border-r last:border-0 border-slate-200" dangerouslySetInnerHTML={{ __html: parseInlineMarkdown(cell.trim()) }} />
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
      tableRows = [];
      inTable = false;
    }
  };

  const flushCodeBlock = (key: string) => {
    if (codeBlockLines.length > 0 || inCodeBlock) {
      elements.push(
        <div key={key} className="my-3 rounded-xl overflow-hidden border border-slate-800 bg-slate-900 shadow-xs">
          {codeLanguage && (
            <div className="px-3.5 py-1.5 bg-slate-850 text-slate-400 text-[11px] font-mono border-b border-slate-800 flex items-center justify-between">
              <span>{codeLanguage}</span>
            </div>
          )}
          <pre className="p-3.5 text-slate-100 font-mono text-xs overflow-x-auto leading-relaxed">
            <code>{codeBlockLines.join("\n")}</code>
          </pre>
        </div>
      );
      codeBlockLines = [];
      inCodeBlock = false;
      codeLanguage = "";
    }
  };

  // Known clinical sections for natural section visual separation
  const clinicalSectionRegex = /^(?:#+\s*)?(CHIEF COMPLAINT|CLINICAL HISTORY|OBSERVATIONS\s*(?:&|AND)?\s*VITALS|INVESTIGATIONS\s*(?:&|AND)?\s*LABS|CLINICAL ASSESSMENT\s*(?:&|AND)?\s*DIAGNOSIS|RECOMMENDATIONS\s*(?:&|AND)?\s*TREATMENT PLAN|CLINICAL FINDINGS|ASSESSMENT|RECOMMENDATIONS|TREATMENT PLAN|FOLLOW[\s-]UP|LABORATORY FINDINGS|RADIOLOGY FINDINGS)(?::|\s*$)/i;

  lines.forEach((line, index) => {
    const key = `md-line-${index}`;
    const trimmed = line.trim();

    // Code block toggle
    if (trimmed.startsWith("```")) {
      if (inCodeBlock) {
        flushCodeBlock(key);
      } else {
        if (inList) flushList(key + "-list");
        if (inTable) flushTable(key + "-tbl");
        inCodeBlock = true;
        codeLanguage = trimmed.slice(3).trim();
      }
      return;
    }

    if (inCodeBlock) {
      codeBlockLines.push(line);
      return;
    }

    // Table checking
    if (trimmed.startsWith("|") && trimmed.endsWith("|")) {
      if (inList) flushList(key + "-list");
      inTable = true;
      const cells = trimmed.split("|").map(c => c.trim()).filter((_, idx, arr) => idx > 0 && idx < arr.length - 1);
      tableRows.push(cells);
      return;
    } else if (inTable) {
      flushTable(key);
    }

    // List checking: Bullet
    if (/^[-*•]\s+/.test(trimmed)) {
      if (inList && isNumberedList) flushList(key + "-ordered-end");
      inList = true;
      isNumberedList = false;
      listItems.push(trimmed.replace(/^[-*•]\s+/, ""));
      return;
    }

    // List checking: Numbered (e.g., "1. ", "2) ")
    if (/^\d+[.)]\s+/.test(trimmed)) {
      if (inList && !isNumberedList) flushList(key + "-bullet-end");
      inList = true;
      isNumberedList = true;
      listItems.push(trimmed.replace(/^\d+[.)]\s+/, ""));
      return;
    }

    if (inList) {
      flushList(key + "-list-end");
    }

    // Blank lines
    if (trimmed === "") {
      return;
    }

    // Headings
    if (trimmed.startsWith("#### ")) {
      elements.push(
        <h4 key={key} className="text-[13px] font-bold text-slate-900 mt-4 mb-2 flex items-center gap-1.5" dangerouslySetInnerHTML={{ __html: parseInlineMarkdown(trimmed.substring(5)) }} />
      );
      return;
    }

    if (trimmed.startsWith("### ")) {
      elements.push(
        <h3 key={key} className="text-xs font-bold uppercase tracking-wider text-rose-950 mt-5 mb-2 flex items-center gap-1.5" dangerouslySetInnerHTML={{ __html: parseInlineMarkdown(trimmed.substring(4)) }} />
      );
      return;
    }

    if (trimmed.startsWith("## ")) {
      elements.push(
        <h2 key={key} className="text-sm font-bold text-slate-900 mt-5 mb-2.5 pb-1 border-b border-slate-150 flex items-center gap-2" dangerouslySetInnerHTML={{ __html: parseInlineMarkdown(trimmed.substring(3)) }} />
      );
      return;
    }

    if (trimmed.startsWith("# ")) {
      elements.push(
        <h1 key={key} className="text-base font-bold text-slate-900 mt-6 mb-3 pb-1.5 border-b border-slate-200" dangerouslySetInnerHTML={{ __html: parseInlineMarkdown(trimmed.substring(2)) }} />
      );
      return;
    }

    // Clinical Section Header Detection (e.g., "CLINICAL ASSESSMENT & DIAGNOSIS:" or "Observations & Vitals:")
    const sectionMatch = trimmed.match(clinicalSectionRegex);
    if (sectionMatch && trimmed.length < 90) {
      elements.push(
        <div key={key} className="mt-4 mb-2 pt-2.5 first:mt-0 first:pt-0 border-t border-slate-100 first:border-0">
          <span className="inline-flex items-center text-xs font-bold uppercase tracking-wider text-rose-950 bg-rose-50/70 border border-rose-200/60 px-2.5 py-1 rounded-md">
            {trimmed.replace(/^#+\s*/, "").replace(/:$/, "")}
          </span>
        </div>
      );
      return;
    }

    // Standard Paragraph
    elements.push(
      <p key={key} className="my-2.5 text-slate-800 text-[14px] leading-relaxed" dangerouslySetInnerHTML={{ __html: parseInlineMarkdown(trimmed) }} />
    );
  });

  if (inCodeBlock) flushCodeBlock("final-code-flush");
  if (inList) flushList("final-list-flush");
  if (inTable) flushTable("final-table-flush");

  return <div className="space-y-1.5">{elements}</div>;
};
