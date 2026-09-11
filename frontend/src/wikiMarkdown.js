function escapeHtml(value) {
  return String(value || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function apiUrl(url) {
  if (!url) {
    return "";
  }
  if (/^https?:\/\//i.test(url) || url.startsWith("data:")) {
    return url;
  }
  const base = (import.meta.env.BASE_URL || "/").replace(/\/$/, "");
  return `${base}${url.startsWith("/") ? url : `/${url}`}`;
}

function attachmentUrl(attachments, target) {
  const key = String(target || "").replace(/\\/g, "/").replace(/^\.\//, "").toLowerCase();
  const name = key.split("/").pop();
  for (const item of attachments || []) {
    const rel = String(item.relPath || "").replace(/\\/g, "/").toLowerCase();
    const original = String(item.originalName || "").toLowerCase();
    if (rel === key || original === name || rel.endsWith(`/${name}`)) {
      return apiUrl(item.url);
    }
  }
  return "";
}

function inlineFormat(text, attachments) {
  let html = escapeHtml(text);
  html = html.replace(/!\[\[([^\]|#]+)(?:\|[^\]]+)?\]\]/g, (_, target) => {
    const src = attachmentUrl(attachments, target.trim());
    return src ? `<img src="${src}" alt="${escapeHtml(target.trim())}" />` : escapeHtml(`![[${target}]]`);
  });
  html = html.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, (_, alt, src) => {
    const resolved = attachmentUrl(attachments, src) || apiUrl(src);
    return `<img src="${resolved}" alt="${escapeHtml(alt)}" />`;
  });
  html = html.replace(/\[\[([^\]|#]+)(?:#([^\]|]+))?(?:\|([^\]]+))?\]\]/g, (_, title, _heading, alias) => {
    const label = alias || title;
    return `<button type="button" class="wiki-link" data-wiki-title="${escapeHtml(title.trim())}">${escapeHtml(label.trim())}</button>`;
  });
  html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, (_, label, href) => {
    const safe = escapeHtml(href);
    if (/^javascript:/i.test(href)) {
      return escapeHtml(label);
    }
    return `<a href="${safe}" target="_blank" rel="noreferrer">${escapeHtml(label)}</a>`;
  });
  html = html.replace(/`([^`]+)`/g, "<code>$1</code>");
  html = html.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  html = html.replace(/\*([^*]+)\*/g, "<em>$1</em>");
  return html;
}

export function renderWikiMarkdown(body, attachments = []) {
  const lines = String(body || "").replace(/\r\n/g, "\n").split("\n");
  const out = [];
  let inCode = false;
  let code = [];
  let list = [];

  const flushList = () => {
    if (!list.length) {
      return;
    }
    out.push(`<ul>${list.map((item) => `<li>${inlineFormat(item, attachments)}</li>`).join("")}</ul>`);
    list = [];
  };

  const flushCode = () => {
    out.push(`<pre><code>${escapeHtml(code.join("\n"))}</code></pre>`);
    code = [];
    inCode = false;
  };

  for (const line of lines) {
    if (line.trim().startsWith("```")) {
      if (inCode) {
        flushCode();
      } else {
        flushList();
        inCode = true;
        code = [];
      }
      continue;
    }
    if (inCode) {
      code.push(line);
      continue;
    }
    const bullet = line.match(/^\s*[-*]\s+(.+)$/);
    if (bullet) {
      list.push(bullet[1]);
      continue;
    }
    flushList();
    const heading = line.match(/^(#{1,6})\s+(.+)$/);
    if (heading) {
      const level = heading[1].length;
      out.push(`<h${level}>${inlineFormat(heading[2], attachments)}</h${level}>`);
      continue;
    }
    if (!line.trim()) {
      continue;
    }
    out.push(`<p>${inlineFormat(line, attachments)}</p>`);
  }
  if (inCode) {
    flushCode();
  }
  flushList();
  return out.join("") || "<p class=\"preview-empty\">This note is empty.</p>";
}
