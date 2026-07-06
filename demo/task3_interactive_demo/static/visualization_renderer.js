// 表格与图表渲染：展示分析库统计结果和证据视图。
(function () {
  const { $, escapeHtml, formatNumber, truncate } = window.CCFCommon;

  function renderTable(container, rows, maxLen = 110) {
    if (!rows || rows.length === 0) {
      container.innerHTML = `<div class="empty-state">暂无数据</div>`;
      return;
    }
    const columns = Object.keys(rows[0]);
    container.innerHTML = `
      <table>
        <thead>
          <tr>${columns.map((col) => `<th>${escapeHtml(col)}</th>`).join("")}</tr>
        </thead>
        <tbody>
          ${rows
            .map(
              (row) => `
                <tr>
                  ${columns
                    .map((col) => `<td title="${escapeHtml(row[col])}">${escapeHtml(truncate(row[col], maxLen))}</td>`)
                    .join("")}
                </tr>
              `,
            )
            .join("")}
        </tbody>
      </table>
    `;
  }

  function renderBarChart(chart) {
    const canvas = $("#chartCanvas");
    if (!chart || !chart.data || chart.data.length === 0) {
      canvas.innerHTML = `<div class="empty-state">当前结果不适合绘制统计图</div>`;
      return;
    }
    const data = chart.data.slice(0, chart.limit || 12);
    const width = Math.max(560, Math.round(canvas.getBoundingClientRect().width || 760));
    const rowHeight = 36;
    const height = Math.max(330, 94 + data.length * rowHeight);
    const margin = { top: 72, right: 92, bottom: 34, left: 150 };
    const max = Math.max(...data.map((row) => Number(row[chart.value_key] || 0)), 1);
    const innerWidth = width - margin.left - margin.right;
    const title = chart.title || `${chart.label_key} / ${chart.value_key}`;
    const subtitle = chart.subtitle || "由任务三分析库实时查询生成，可随问答或实体子图切换。";

    const bars = data
      .map((row, index) => {
        const value = Number(row[chart.value_key] || 0);
        const w = Math.max(2, (value / max) * innerWidth);
        const y = margin.top + index * rowHeight;
        const label = row[chart.label_key];
        return `
          <g>
            <text x="${margin.left - 12}" y="${y + 19}" text-anchor="end" font-size="13" fill="#334155">${escapeHtml(truncate(label, 16))}</text>
            <rect x="${margin.left}" y="${y}" width="${w}" height="24" rx="5" fill="#2563eb"></rect>
            <text x="${Math.min(margin.left + w + 10, width - margin.right + 56)}" y="${y + 17}" font-size="13" fill="#172033">${formatNumber(value)}</text>
          </g>
        `;
      })
      .join("");

    canvas.innerHTML = `
      <svg class="dynamic-chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="统计图表">
        <text x="24" y="28" font-size="18" font-weight="800" fill="#172033">${escapeHtml(title)}</text>
        <text x="24" y="50" font-size="12" fill="#68748a">${escapeHtml(subtitle)}</text>
        <line x1="${margin.left}" y1="${margin.top - 12}" x2="${margin.left}" y2="${height - margin.bottom}" stroke="#dfe6f1"></line>
        <line x1="${margin.left}" y1="${height - margin.bottom}" x2="${width - margin.right}" y2="${height - margin.bottom}" stroke="#dfe6f1"></line>
        ${bars}
      </svg>
    `;
  }

  window.CCFVisualizationRenderer = {
    renderTable,
    renderBarChart,
  };
})();
