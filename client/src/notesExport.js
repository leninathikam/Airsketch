import { safeFilename } from "./workspaceUtils";

function escapeHtml(value) {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function inline(value) {
  return escapeHtml(value).replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
}

function renderNotes(text) {
  const lines = text.replace(/\r\n/g, "\n").split("\n");
  let html = "";
  let list = null;

  const closeList = () => {
    if (!list) return;
    html += `</${list}>`;
    list = null;
  };

  const openList = (kind) => {
    if (list === kind) return;
    closeList();
    html += `<${kind}>`;
    list = kind;
  };

  lines.forEach((raw) => {
    let line = raw.trim();
    if (!line || /^[-*_]{3,}$/.test(line)) {
      closeList();
      return;
    }
    const markdownHeading = line.match(/^#{1,3}\s+(.*)$/);
    if (markdownHeading) line = markdownHeading[1].trim();
    const wrapped = line.match(/^\*\*(.*)\*\*$/);
    if (wrapped) line = wrapped[1].trim();

    const bullet = line.match(/^[-*â€¢]\s+(.*)$/);
    const numbered = line.match(/^\d+[.)]\s+(.*)$/);
    const shortLabel =
      !bullet &&
      !numbered &&
      line.length < 48 &&
      /quiz|question|study|summary|notes/i.test(line) &&
      !line.includes("?");

    if (markdownHeading || shortLabel) {
      closeList();
      html += `<h2>${inline(line.replace(/[:#]+$/g, ""))}</h2>`;
      return;
    }
    if (bullet) {
      openList("ul");
      html += `<li>${inline(bullet[1])}</li>`;
      return;
    }
    if (numbered) {
      openList("ol");
      html += `<li>${inline(numbered[1])}</li>`;
      return;
    }
    closeList();
    html += `<p>${inline(line)}</p>`;
  });

  closeList();
  return html;
}

export function buildNotesHtml(text, title = "Lecture notes") {
  const content = text.startsWith(`# ${title}\n`) ? text.slice(title.length + 3).trimStart() : text;
  const written = new Date();
  const stamp = written.toLocaleString(undefined, {
    dateStyle: "long",
    timeStyle: "short",
  });
  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>${escapeHtml(title)} — AirSketch</title>
  <style>
    body {
      margin: 0;
      color: #1d2a3a;
      background: #f5f6f8;
      font-family: Georgia, "Times New Roman", serif;
    }
    main {
      max-width: 720px;
      margin: 32px auto;
      padding: 36px 42px 48px;
      background: #fff;
      border: 1px solid #e1e5eb;
      border-radius: 4px;
    }
    header {
      margin-bottom: 28px;
      padding-bottom: 18px;
      border-bottom: 1px solid #dce1e8;
    }
    .brand {
      margin: 0;
      color: #33445f;
      font-family: "Segoe UI", sans-serif;
      font-size: 14px;
      letter-spacing: 0.16em;
      text-transform: uppercase;
    }
    h1 {
      margin: 8px 0 6px;
      font-size: 34px;
    }
    .when {
      margin: 0;
      color: #5c6b7a;
      font-family: "Segoe UI", sans-serif;
      font-size: 14px;
    }
    h2 {
      margin: 28px 0 8px;
      color: #33445f;
      font-family: "Segoe UI", sans-serif;
      font-size: 18px;
    }
    p, li {
      font-size: 18px;
      line-height: 1.55;
    }
    ul, ol {
      margin: 8px 0 0;
      padding-left: 22px;
    }
    li { margin: 8px 0; }
    li::marker { color: #566783; }
    @media print { body { background: #fff; } main { margin: 0; padding: 0; border: 0; } }
  </style>
</head>
<body>
  <main>
    <header>
      <p class="brand">AirSketch</p>
      <h1>${escapeHtml(title)}</h1>
      <p class="when">${escapeHtml(stamp)}</p>
    </header>
    ${renderNotes(content)}
  </main>
</body>
</html>`;
}

function saveFile(blob, filename) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  // Allow the browser to begin reading the object URL before releasing it.
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function downloadNotes(text, title = "Lecture notes") {
  saveFile(new Blob([buildNotesHtml(text, title)], { type: "text/html;charset=utf-8" }), `${safeFilename(title)}.html`);
}

export function downloadText(text, format = "txt", title = "Lecture notes") {
  const markdown = format === "md";
  const content = markdown ? text : text.replace(/^#{1,6}\s+/gm, "").replace(/\*\*(.+?)\*\*/g, "$1");
  saveFile(new Blob([content], { type: markdown ? "text/markdown;charset=utf-8" : "text/plain;charset=utf-8" }),
    `${safeFilename(title)}.${markdown ? "md" : "txt"}`);
}
