import React from "react";

interface MarkdownRendererProps {
  content: string;
}

export const MarkdownRenderer: React.FC<MarkdownRendererProps> = ({ content }) => {
  const lines = content.split("\n");
  const elements: React.ReactNode[] = [];
  let listItems: string[] = [];
  let inList = false;
  let tableRows: string[][] = [];
  let inTable = false;

  const flushList = (key: string) => {
    if (listItems.length > 0) {
      elements.push(
        <ul key={key} className="list-disc pl-5 my-2 space-y-1 text-slate-800 dark:text-slate-200">
          {listItems.map((item, idx) => (
            <li key={idx} dangerouslySetInnerHTML={{ __html: parseInlineMarkdown(item) }} />
          ))}
        </ul>
      );
      listItems = [];
    }
  };

  const flushTable = (key: string) => {
    if (tableRows.length > 0) {
      const headers = tableRows[0];
      const bodyRows = tableRows.slice(2); // line 1 is divider `|---|---|`
      
      elements.push(
        <div key={key} className="overflow-x-auto my-3 border border-slate-200 dark:border-slate-800 rounded-lg shadow-sm">
          <table className="min-w-full divide-y divide-slate-200 dark:divide-slate-850 text-xs text-left">
            <thead className="bg-slate-50 dark:bg-slate-900 text-slate-700 dark:text-slate-350 font-bold uppercase">
              <tr>
                {headers.map((h, idx) => (
                  <th key={idx} className="px-4 py-2 border-r last:border-0 border-slate-200 dark:border-slate-800" dangerouslySetInnerHTML={{ __html: parseInlineMarkdown(h.trim()) }} />
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200 dark:divide-slate-850 bg-white dark:bg-slate-950 text-slate-650 dark:text-slate-300">
              {bodyRows.map((row, rIdx) => (
                <tr key={rIdx} className="hover:bg-slate-50/50 dark:hover:bg-slate-900/30">
                  {row.map((cell, cIdx) => (
                    <td key={cIdx} className="px-4 py-2 border-r last:border-0 border-slate-200 dark:border-slate-800" dangerouslySetInnerHTML={{ __html: parseInlineMarkdown(cell.trim()) }} />
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
      tableRows = [];
    }
  };

  const parseInlineMarkdown = (text: string): string => {
    // Bold: **text**
    let parsed = text.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");
    // Italic: *text*
    parsed = parsed.replace(/\*(.*?)\*/g, "<em>$1</em>");
    // Inline code: `code`
    parsed = parsed.replace(/`(.*?)`/g, '<code class="bg-slate-100 dark:bg-slate-900 px-1 py-0.5 rounded font-mono text-xs text-clinical-600 dark:text-clinical-400">$1</code>');
    return parsed;
  };

  lines.forEach((line, index) => {
    const key = `markdown-line-${index}`;
    const trimmed = line.trim();

    // Table checking
    if (trimmed.startsWith("|")) {
      flushList(key);
      inTable = true;
      const cells = trimmed.split("|").map(c => c.trim()).filter((_, idx, arr) => idx > 0 && idx < arr.length - 1);
      tableRows.push(cells);
      return;
    } else if (inTable) {
      flushTable(key);
      inTable = false;
    }

    // List checking
    if (trimmed.startsWith("- ") || trimmed.startsWith("* ")) {
      inList = true;
      listItems.push(trimmed.substring(2));
      return;
    } else {
      if (inList) {
        flushList(key + "-list-end");
        inList = false;
      }
    }

    // Heading 3
    if (trimmed.startsWith("### ")) {
      elements.push(
        <h3 key={key} className="text-sm font-bold text-slate-800 dark:text-slate-100 mt-4 mb-1.5" dangerouslySetInnerHTML={{ __html: parseInlineMarkdown(trimmed.substring(4)) }} />
      );
      return;
    }

    // Heading 2
    if (trimmed.startsWith("## ")) {
      elements.push(
        <h2 key={key} className="text-base font-bold text-slate-800 dark:text-slate-100 mt-5 mb-2 border-b border-slate-100 dark:border-slate-850 pb-1" dangerouslySetInnerHTML={{ __html: parseInlineMarkdown(trimmed.substring(3)) }} />
      );
      return;
    }

    // Heading 1
    if (trimmed.startsWith("# ")) {
      elements.push(
        <h1 key={key} className="text-lg font-bold text-slate-800 dark:text-slate-100 mt-6 mb-3 border-b border-slate-200 dark:border-slate-800 pb-1.5" dangerouslySetInnerHTML={{ __html: parseInlineMarkdown(trimmed.substring(2)) }} />
      );
      return;
    }

    // Paragraph
    if (trimmed !== "") {
      elements.push(
        <p key={key} className="my-2.5 text-slate-800 dark:text-slate-200 text-sm leading-relaxed" dangerouslySetInnerHTML={{ __html: parseInlineMarkdown(line) }} />
      );
    }
  });

  if (inList) flushList("final-list-flush");
  if (inTable) flushTable("final-table-flush");

  return <div className="space-y-1">{elements}</div>;
};
