export function wordCount(text) {
  return text.trim() ? text.trim().split(/\s+/).length : 0;
}

export function searchParts(text, query) {
  const needle = query.trim().toLowerCase();
  if (!needle) return [{ text, match: false }];
  const haystack = text.toLowerCase();
  const parts = [];
  let cursor = 0;
  let index;
  while ((index = haystack.indexOf(needle, cursor)) !== -1) {
    if (index > cursor) parts.push({ text: text.slice(cursor, index), match: false });
    parts.push({ text: text.slice(index, index + needle.length), match: true });
    cursor = index + needle.length;
  }
  if (cursor < text.length) parts.push({ text: text.slice(cursor), match: false });
  return parts;
}

export function exportLecture({ title, transcript, summary, warning, comments }) {
  return [
    `# ${title.trim() || "Untitled lecture"}`,
    summary && `## Study notes\n${summary}`,
    warning,
    transcript && `## Transcript\n${transcript}`,
    comments.length > 0 && `## Personal notes\n${comments.map(note => `- ${note.text}`).join("\n")}`,
  ].filter(Boolean).join("\n\n");
}

export function safeFilename(title) {
  return (title.trim().replace(/[^a-z0-9_-]+/gi, "-").replace(/^-|-$/g, "").slice(0, 80) || "airsketch-lecture");
}
