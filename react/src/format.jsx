/* Small shared helpers: language direction, initials, timestamps, and just
 * enough Markdown to render what the model actually sends.
 */

import React from "react";

/** The model answers in whichever language it was asked in. */
export const isArabic = (text) => /[؀-ۿ]/.test(text || "");

export const dirOf = (text) => (isArabic(text) ? "rtl" : "ltr");

export function initials(name) {
  return (name || "")
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((word) => word[0])
    .join("")
    .toUpperCase();
}

export const clockOf = (date) =>
  new Date(date).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

export const prettyRole = (role) => (role || "").replace(/_/g, " ");

/* --- Markdown ------------------------------------------------------------
 *
 * The model replies with **bold**, `code`, and bullet or numbered lists.
 * Rendering those as React elements — never as raw HTML — means a tool
 * result that happens to contain markup is text, and stays text.
 */

export function Markdown({ text }) {
  const blocks = [];
  let list = null;

  const closeList = () => {
    if (!list) return;
    const Tag = list.ordered ? "ol" : "ul";
    blocks.push(
      <Tag key={`l${blocks.length}`}>
        {list.items.map((item, i) => (
          <li key={i}>{inline(item)}</li>
        ))}
      </Tag>
    );
    list = null;
  };

  for (const raw of String(text || "").split("\n")) {
    const line = raw.trimEnd();

    const bullet = line.match(/^\s*[-*•]\s+(.*)$/);
    const numbered = line.match(/^\s*\d+[.)]\s+(.*)$/);

    if (bullet || numbered) {
      const ordered = Boolean(numbered);
      const item = (bullet || numbered)[1];
      if (!list || list.ordered !== ordered) {
        closeList();
        list = { ordered, items: [] };
      }
      list.items.push(item);
      continue;
    }

    closeList();
    if (line.trim() === "") continue;
    blocks.push(<p key={`p${blocks.length}`}>{inline(line)}</p>);
  }

  closeList();
  return <div className="md">{blocks}</div>;
}

/** **bold** and `code`, in one pass, so neither can swallow the other. */
function inline(text) {
  const parts = [];
  const pattern = /(\*\*[^*]+\*\*|`[^`]+`)/g;
  let last = 0;
  let match;

  while ((match = pattern.exec(text)) !== null) {
    if (match.index > last) parts.push(text.slice(last, match.index));
    const token = match[0];
    if (token.startsWith("**")) {
      parts.push(<strong key={parts.length}>{token.slice(2, -2)}</strong>);
    } else {
      parts.push(<code key={parts.length}>{token.slice(1, -1)}</code>);
    }
    last = match.index + token.length;
  }

  if (last < text.length) parts.push(text.slice(last));
  return parts;
}
