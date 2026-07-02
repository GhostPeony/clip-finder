import React from 'react';
import { LibraryGraphVideo } from '../types';
import { formatTimestampLabel } from './time';
import { buildTimestampUrl } from './videoKnowledge';

interface ReportBlock {
  type: 'heading' | 'paragraph' | 'list';
  level?: number;
  text?: string;
  items?: string[];
}

export function ReportContent({ content, video }: { content: string; video?: LibraryGraphVideo }) {
  const blocks = parseReportMarkdown(content);

  return (
    <div className="mt-5 space-y-5 text-bark">
      {blocks.map((block, index) => {
        if (block.type === 'heading') {
          const HeadingTag = block.level === 1 ? 'h3' : 'h4';
          return (
            <HeadingTag
              key={`heading-${index}`}
              className={
                block.level === 1
                  ? 'font-serif text-2xl font-medium leading-tight text-ink'
                  : 'pt-2 text-sm font-semibold uppercase tracking-wide text-muted'
              }
            >
              {block.text}
            </HeadingTag>
          );
        }

        if (block.type === 'list') {
          return (
            <ul key={`list-${index}`} className="space-y-3">
              {(block.items || []).map((item, itemIndex) => (
                <li
                  key={`${index}-${itemIndex}`}
                  className="border-l-2 border-rose/30 pl-4 text-base leading-8 text-bark"
                >
                  {renderReportInlineText(item, video)}
                </li>
              ))}
            </ul>
          );
        }

        return (
          <p key={`paragraph-${index}`} className="text-base leading-8 text-bark">
            {renderReportInlineText(block.text || '', video)}
          </p>
        );
      })}
    </div>
  );
}

function parseReportMarkdown(content: string): ReportBlock[] {
  const blocks: ReportBlock[] = [];
  const lines = content.split(/\r?\n/);
  let paragraph: string[] = [];
  let listItems: string[] = [];

  const flushParagraph = () => {
    if (paragraph.length === 0) return;
    blocks.push({ type: 'paragraph', text: paragraph.join(' ').trim() });
    paragraph = [];
  };

  const flushList = () => {
    if (listItems.length === 0) return;
    blocks.push({ type: 'list', items: listItems });
    listItems = [];
  };

  lines.forEach((line) => {
    const trimmed = line.trim();
    if (!trimmed) {
      flushParagraph();
      flushList();
      return;
    }

    const heading = /^(#{1,3})\s+(.+)$/.exec(trimmed);
    if (heading) {
      flushParagraph();
      flushList();
      blocks.push({
        type: 'heading',
        level: heading[1].length,
        text: heading[2].trim(),
      });
      return;
    }

    const bullet = /^[-*]\s+(.+)$/.exec(trimmed);
    if (bullet) {
      flushParagraph();
      listItems.push(bullet[1].trim());
      return;
    }

    flushList();
    paragraph.push(trimmed);
  });

  flushParagraph();
  flushList();
  return blocks;
}

function renderReportInlineText(text: string, video?: LibraryGraphVideo): React.ReactNode {
  const pieces: React.ReactNode[] = [];
  const sourcePattern = /\(source:\s*([^)]+)\)/gi;
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = sourcePattern.exec(text)) !== null) {
    if (match.index > lastIndex) {
      pieces.push(text.slice(lastIndex, match.index));
    }

    const timestampLinks = match[1]
      .split(',')
      .map((label) => label.trim())
      .map((label) => ({ label, seconds: parseTimestampToSeconds(label) }))
      .filter((item): item is { label: string; seconds: number } => item.seconds !== null);

    if (timestampLinks.length > 0) {
      pieces.push(
        <span key={`source-${match.index}`} className="inline-flex flex-wrap gap-1 align-baseline">
          {timestampLinks.map(({ label, seconds }) => (
            <a
              key={`${match.index}-${label}`}
              href={buildTimestampUrl(video, seconds)}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex rounded-lg bg-petal px-2 py-0.5 font-mono text-xs font-semibold text-rose-deep transition-colors hover:bg-rose/15"
            >
              source {formatTimestampLabel(seconds)}
            </a>
          ))}
        </span>,
      );
    } else {
      pieces.push(match[0]);
    }
    lastIndex = match.index + match[0].length;
  }

  if (lastIndex < text.length) {
    pieces.push(text.slice(lastIndex));
  }

  return pieces.length > 0 ? pieces : text;
}

function parseTimestampToSeconds(label: string): number | null {
  const cleaned = label
    .trim()
    .replace(/^source\s*/i, '')
    .replace(/[^\d:]/g, '');
  if (!cleaned) return null;
  const parts = cleaned.split(':').map((part) => Number(part));
  if (parts.some((part) => Number.isNaN(part))) return null;
  if (parts.length === 1) return parts[0];
  if (parts.length === 2) return parts[0] * 60 + parts[1];
  if (parts.length === 3) return parts[0] * 3600 + parts[1] * 60 + parts[2];
  return null;
}
