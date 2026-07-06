// 安全 Markdown 渲染：把问答结果转换为可读的标题、表格和列表。
(function () {
  const { escapeHtml } = window.CCFCommon;

  function inlineMarkdown(value) {
    return escapeHtml(value)
      .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
      .replace(/`([^`]+)`/g, "<code>$1</code>");
  }

  function isTableDivider(line) {
    return /^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$/.test(line);
  }

  function parseTable(lines, start) {
    let dividerIndex = start + 1;
    while (dividerIndex < lines.length && !lines[dividerIndex].trim()) {
      dividerIndex += 1;
    }
    if (dividerIndex >= lines.length || !lines[start].includes("|") || !isTableDivider(lines[dividerIndex])) {
      return null;
    }
    const rows = [];
    let index = start;
    while (index < lines.length && lines[index].includes("|")) {
      if (!isTableDivider(lines[index])) {
        const cells = lines[index]
          .trim()
          .replace(/^\|/, "")
          .replace(/\|$/, "")
          .split("|")
          .map((cell) => inlineMarkdown(cell.trim()));
        if (cells.some((cell) => cell.trim())) {
          rows.push(cells);
        }
      }
      index += 1;
    }
    if (rows.length < 2) return null;
    const header = rows[0];
    const body = rows.slice(1);
    const html = `
      <div class="markdown-table-wrap">
        <table class="markdown-table">
          <thead><tr>${header.map((cell) => `<th>${cell}</th>`).join("")}</tr></thead>
          <tbody>
            ${body.map((row) => `<tr>${row.map((cell) => `<td>${cell}</td>`).join("")}</tr>`).join("")}
          </tbody>
        </table>
      </div>
    `;
    return { html, next: index };
  }

  function renderParagraph(buffer) {
    if (!buffer.length) return "";
    const text = buffer.join("\n").trim();
    buffer.length = 0;
    return text ? `<p>${inlineMarkdown(text).replace(/\n/g, "<br>")}</p>` : "";
  }

  function renderMarkdown(value) {
    const lines = String(value ?? "")
      .replace(/\r\n/g, "\n")
      .replace(/\n{3,}/g, "\n\n")
      .split("\n");
    const html = [];
    const paragraph = [];
    let list = [];

    function flushList() {
      if (!list.length) return;
      html.push(`<ul>${list.map((item) => `<li>${inlineMarkdown(item)}</li>`).join("")}</ul>`);
      list = [];
    }

    for (let index = 0; index < lines.length;) {
      const raw = lines[index];
      const line = raw.trim();
      const table = parseTable(lines, index);
      if (table) {
        html.push(renderParagraph(paragraph));
        flushList();
        html.push(table.html);
        index = table.next;
        continue;
      }

      if (!line || /^-{3,}$/.test(line)) {
        html.push(renderParagraph(paragraph));
        flushList();
        index += 1;
        continue;
      }

      const heading = /^(#{1,4})\s+(.+)$/.exec(line);
      if (heading) {
        html.push(renderParagraph(paragraph));
        flushList();
        const level = Math.min(4, heading[1].length + 2);
        html.push(`<h${level}>${inlineMarkdown(heading[2])}</h${level}>`);
        index += 1;
        continue;
      }

      const bullet = /^[-*]\s+(.+)$/.exec(line);
      if (bullet) {
        html.push(renderParagraph(paragraph));
        list.push(bullet[1]);
        index += 1;
        continue;
      }

      const numbered = /^\d+[.)]\s+(.+)$/.exec(line);
      if (numbered) {
        html.push(renderParagraph(paragraph));
        list.push(numbered[1]);
        index += 1;
        continue;
      }

      const blockQuote = /^>\s*(.+)$/.exec(line);
      if (blockQuote) {
        html.push(renderParagraph(paragraph));
        flushList();
        paragraph.push(blockQuote[1]);
        index += 1;
        continue;
      }

      flushList();
      paragraph.push(raw);
      index += 1;
    }

    html.push(renderParagraph(paragraph));
    flushList();
    return `<div class="markdown-body">${html.filter(Boolean).join("")}</div>`;
  }

  window.CCFMarkdown = {
    renderMarkdown,
  };
})();
