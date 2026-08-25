'use client';

import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { ExternalLink } from 'lucide-react';

interface MarkdownRendererProps {
  content: string;
}

export const MarkdownRenderer: React.FC<MarkdownRendererProps> = ({ content }) => {
  return (
    <div className="w-full text-sm leading-relaxed text-slate-800 space-y-2">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          // Headings
          h1: ({ children }) => (
            <h1 className="text-base font-extrabold text-slate-900 mt-3 mb-1.5 pb-1 border-b border-slate-200">
              {children}
            </h1>
          ),
          h2: ({ children }) => (
            <h2 className="text-sm font-bold text-slate-900 mt-2.5 mb-1 text-indigo-950">
              {children}
            </h2>
          ),
          h3: ({ children }) => (
            <h3 className="text-sm font-bold text-indigo-900 mt-2 mb-1">
              {children}
            </h3>
          ),
          h4: ({ children }) => (
            <h4 className="text-xs font-bold text-slate-800 mt-1.5 mb-0.5 uppercase tracking-wide">
              {children}
            </h4>
          ),

          // Paragraphs
          p: ({ children }) => (
            <p className="my-1.5 leading-relaxed text-slate-800">
              {children}
            </p>
          ),

          // Lists
          ul: ({ children }) => (
            <ul className="my-2 ml-4 list-disc space-y-1 text-slate-800">
              {children}
            </ul>
          ),
          ol: ({ children }) => (
            <ol className="my-2 ml-4 list-decimal space-y-1 text-slate-800">
              {children}
            </ol>
          ),
          li: ({ children }) => (
            <li className="leading-relaxed pl-0.5">
              {children}
            </li>
          ),

          // Strong & Emphasis
          strong: ({ children }) => (
            <strong className="font-bold text-slate-900">
              {children}
            </strong>
          ),
          em: ({ children }) => (
            <em className="text-slate-600 not-italic font-medium">
              {children}
            </em>
          ),

          // Tables - Beautiful Modern Responsive Tables
          table: ({ children }) => (
            <div className="my-3 overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-2xs">
              <table className="w-full text-left text-xs border-collapse">
                {children}
              </table>
            </div>
          ),
          thead: ({ children }) => (
            <thead className="bg-slate-50 border-b border-slate-200 text-slate-700 font-bold">
              {children}
            </thead>
          ),
          tbody: ({ children }) => (
            <tbody className="divide-y divide-slate-100">
              {children}
            </tbody>
          ),
          tr: ({ children }) => (
            <tr className="hover:bg-indigo-50/40 transition-colors">
              {children}
            </tr>
          ),
          th: ({ children }) => (
            <th className="px-3.5 py-2.5 font-bold text-slate-800 text-[11px] uppercase tracking-wider whitespace-nowrap bg-slate-100/70">
              {children}
            </th>
          ),
          td: ({ children }) => (
            <td className="px-3.5 py-2.5 text-slate-700 align-top leading-relaxed">
              {children}
            </td>
          ),

          // Links
          a: ({ href, children }) => (
            <a
              href={href}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-0.5 font-semibold text-indigo-600 hover:text-indigo-800 hover:underline"
            >
              <span>{children}</span>
              <ExternalLink className="h-3 w-3 inline shrink-0" />
            </a>
          ),

          // Blockquote
          blockquote: ({ children }) => (
            <div className="my-2.5 border-l-3 border-indigo-500 bg-indigo-50/60 px-3.5 py-2 rounded-r-lg text-xs text-indigo-950 font-medium italic">
              {children}
            </div>
          ),

          // Code
          code: ({ children }) => (
            <code className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-[11px] font-semibold text-indigo-700 border border-slate-200/80">
              {children}
            </code>
          ),
          pre: ({ children }) => (
            <pre className="my-2 overflow-x-auto rounded-xl bg-slate-900 p-3 text-xs text-slate-100">
              {children}
            </pre>
          ),

          // Horizontal Rule
          hr: () => <hr className="my-3 border-slate-200" />,
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
};
