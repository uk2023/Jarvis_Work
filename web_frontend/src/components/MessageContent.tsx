import { useState } from 'react';
import { Copy, Check } from 'lucide-react';

/**
 * MESSAGE CONTENT -- code renders like CodeBox, not like a sentence.
 *
 * UK's report: when JARVIS gives code in chat, it showed up as plain
 * text inside a chat bubble -- no syntax box, no copy button, wrapped
 * and clipped exactly like a WhatsApp message, which is a bad reading
 * experience for anything longer than a few lines.
 *
 * This is a small, dependency-free parser: it does NOT pull in a
 * markdown library (none are installed and this environment has no
 * network access to add one). It looks for fenced code blocks
 * (```lang ... ```) specifically -- the one markdown construct that
 * actually needs different treatment -- and renders everything else as
 * plain paragraphs. That is a deliberately narrow scope: this is not a
 * markdown renderer, it is a code-fence splitter.
 */

interface Segment {
  type: 'text' | 'code';
  content: string;
  language?: string;
}

function splitIntoSegments(text: string): Segment[] {
  const segments: Segment[] = [];
  const fenceRe = /```([a-zA-Z0-9_+-]*)\n?([\s\S]*?)```/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = fenceRe.exec(text)) !== null) {
    if (match.index > lastIndex) {
      segments.push({ type: 'text', content: text.slice(lastIndex, match.index) });
    }
    segments.push({ type: 'code', language: match[1] || 'text', content: match[2].replace(/\n$/, '') });
    lastIndex = fenceRe.lastIndex;
  }
  if (lastIndex < text.length) {
    segments.push({ type: 'text', content: text.slice(lastIndex) });
  }
  return segments.length ? segments : [{ type: 'text', content: text }];
}

function CodeBlock({ code, language, isDark }: { code: string; language: string; isDark: boolean }) {
  const [copied, setCopied] = useState(false);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // Clipboard API unavailable -- the code is still selectable by hand.
    }
  };

  return (
    <div
      className={`my-2 overflow-hidden rounded-xl border ${
        isDark ? 'border-white/10 bg-[#0a0e18]' : 'border-slate-300 bg-slate-950'
      }`}
    >
      <div
        className={`flex items-center justify-between px-3 py-1.5 text-[11px] font-mono ${
          isDark ? 'bg-white/[0.03] text-slate-400' : 'bg-black/20 text-slate-300'
        }`}
      >
        <span className="uppercase tracking-wide">{language}</span>
        <button
          type="button"
          onClick={copy}
          className="flex items-center gap-1 rounded px-1.5 py-0.5 transition hover:bg-white/10"
        >
          {copied ? <Check size={12} /> : <Copy size={12} />}
          {copied ? 'Copied' : 'Copy'}
        </button>
      </div>
      <pre className="overflow-x-auto p-3 text-[12.5px] leading-relaxed text-slate-200">
        <code>{code}</code>
      </pre>
    </div>
  );
}

export default function MessageContent({
  text,
  isDark = true,
}: {
  text: string;
  isDark?: boolean;
}) {
  const segments = splitIntoSegments(text || '');

  return (
    <>
      {segments.map((seg, i) =>
        seg.type === 'code' ? (
          <CodeBlock key={i} code={seg.content} language={seg.language || 'text'} isDark={isDark} />
        ) : (
          seg.content.trim() && (
            <p key={i} className="whitespace-pre-wrap break-words [overflow-wrap:anywhere]">
              {seg.content.trim()}
            </p>
          )
        )
      )}
    </>
  );
}
