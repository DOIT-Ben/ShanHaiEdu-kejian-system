import type { ReactNode } from "react";

function inlineText(value: string): ReactNode[] {
  return value.split(/(\*\*[^*]+\*\*|\*[^*]+\*)/g).map((part, index) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      return (
        <strong
          className="font-semibold text-[var(--sh-ink-strong)]"
          key={`${part}-${String(index)}`}
        >
          {part.slice(2, -2)}
        </strong>
      );
    }
    if (part.startsWith("*") && part.endsWith("*")) {
      return <em key={`${part}-${String(index)}`}>{part.slice(1, -1)}</em>;
    }
    return <span key={`${part}-${String(index)}`}>{part}</span>;
  });
}

function isBlockStart(line: string) {
  return /^(#{1,3})\s+|^>\s?|^[-*]\s+|^\d+\.\s+|^---+$/.test(line);
}

export function MarkdownPreview({ markdown }: { markdown: string }) {
  const lines = markdown.replace(/\r/g, "").split("\n");
  const blocks: ReactNode[] = [];
  let index = 0;

  while (index < lines.length) {
    const line = lines[index]?.trimEnd() ?? "";
    if (!line.trim()) {
      index += 1;
      continue;
    }

    const heading = /^(#{1,3})\s+(.+)$/.exec(line);
    if (heading) {
      const level = heading[1]?.length ?? 2;
      const content = inlineText(heading[2] ?? "");
      if (level === 1) {
        blocks.push(
          <h2
            className="sh-display-type text-3xl font-semibold leading-tight text-[var(--sh-ink-strong)] md:text-4xl"
            key={`heading-${String(index)}`}
          >
            {content}
          </h2>,
        );
      } else if (level === 2) {
        blocks.push(
          <h3
            className="mt-8 border-b border-[var(--sh-line-subtle)] pb-2 text-xl font-semibold text-[var(--sh-ink-strong)] first:mt-0"
            key={`heading-${String(index)}`}
          >
            {content}
          </h3>,
        );
      } else {
        blocks.push(
          <h4
            className="mt-5 text-base font-semibold text-[var(--sh-brand-700)]"
            key={`heading-${String(index)}`}
          >
            {content}
          </h4>,
        );
      }
      index += 1;
      continue;
    }

    if (/^---+$/.test(line.trim())) {
      blocks.push(
        <hr className="my-7 border-[var(--sh-line-subtle)]" key={`rule-${String(index)}`} />,
      );
      index += 1;
      continue;
    }

    if (/^>\s?/.test(line)) {
      const quoteLines: string[] = [];
      while (index < lines.length && /^>\s?/.test(lines[index] ?? "")) {
        quoteLines.push((lines[index] ?? "").replace(/^>\s?/, ""));
        index += 1;
      }
      blocks.push(
        <blockquote
          className="rounded-r-[var(--sh-radius-sm)] border-l-2 border-[var(--sh-brand-300)] bg-[var(--sh-brand-50)] px-4 py-3 text-sm leading-7 text-[var(--sh-ink-default)]"
          key={`quote-${String(index)}`}
        >
          {quoteLines.map((quoteLine, quoteIndex) => (
            <p key={`${quoteLine}-${String(quoteIndex)}`}>{inlineText(quoteLine)}</p>
          ))}
        </blockquote>,
      );
      continue;
    }

    if (/^[-*]\s+/.test(line)) {
      const items: string[] = [];
      while (index < lines.length && /^[-*]\s+/.test(lines[index] ?? "")) {
        items.push((lines[index] ?? "").replace(/^[-*]\s+/, ""));
        index += 1;
      }
      blocks.push(
        <ul
          className="my-3 space-y-2 pl-5 text-base leading-7 text-[var(--sh-ink-default)]"
          key={`list-${String(index)}`}
        >
          {items.map((item, itemIndex) => (
            <li className="list-disc pl-1" key={`${item}-${String(itemIndex)}`}>
              {inlineText(item)}
            </li>
          ))}
        </ul>,
      );
      continue;
    }

    if (/^\d+\.\s+/.test(line)) {
      const items: string[] = [];
      while (index < lines.length && /^\d+\.\s+/.test(lines[index] ?? "")) {
        items.push((lines[index] ?? "").replace(/^\d+\.\s+/, ""));
        index += 1;
      }
      blocks.push(
        <ol
          className="my-3 space-y-2 pl-6 text-base leading-7 text-[var(--sh-ink-default)]"
          key={`ordered-${String(index)}`}
        >
          {items.map((item, itemIndex) => (
            <li className="list-decimal pl-1" key={`${item}-${String(itemIndex)}`}>
              {inlineText(item)}
            </li>
          ))}
        </ol>,
      );
      continue;
    }

    const paragraph: string[] = [line];
    index += 1;
    while (index < lines.length) {
      const next = lines[index]?.trimEnd() ?? "";
      if (!next.trim() || isBlockStart(next)) break;
      paragraph.push(next);
      index += 1;
    }
    blocks.push(
      <p
        className="text-base leading-8 text-[var(--sh-ink-default)]"
        key={`paragraph-${String(index)}`}
      >
        {inlineText(paragraph.join(" "))}
      </p>,
    );
  }

  return (
    <article
      className="space-y-4 rounded-[var(--sh-radius-lg)] border border-[var(--sh-line-default)] bg-[var(--sh-surface-paper)] px-5 py-7 shadow-[var(--sh-shadow-card)] md:px-12 md:py-10"
      data-testid="markdown-preview"
    >
      {blocks}
    </article>
  );
}
