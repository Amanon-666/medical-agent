(function () {
  const { $, escapeHtml, formatNumber, truncate } = window.CCFCommon;
  const COLORS = ["#2563eb", "#0f9d75", "#f59e0b", "#7c3aed", "#e11d48", "#0891b2", "#65a30d", "#ea580c", "#64748b"];

  function renderTable(container, rows, maxLen = 110) {
    if (!rows || rows.length === 0) {
      container.innerHTML = `<div class="empty-state">暂无数据</div>`;
      return;
    }
    const columns = Object.keys(rows[0]);
    container.innerHTML = `
      <table>
        <thead><tr>${columns.map((col) => `<th>${escapeHtml(col)}</th>`).join("")}</tr></thead>
        <tbody>
          ${rows.map((row) => `
            <tr>${columns.map((col) => `<td title="${escapeHtml(row[col])}">${escapeHtml(truncate(row[col], maxLen))}</td>`).join("")}</tr>
          `).join("")}
        </tbody>
      </table>`;
  }

  function chartFrame(chart, body, width, height) {
    const title = chart.title || `${chart.label_key} / ${chart.value_key}`;
    const subtitle = chart.subtitle || "由本轮只读查询结果生成。";
    return `
      <section class="chart-block">
        <svg class="dynamic-chart" viewBox="0 0 ${width} ${height}" role="img" aria-label="${escapeHtml(title)}">
          <text x="24" y="28" font-size="18" font-weight="800" fill="#172033">${escapeHtml(title)}</text>
          <text x="24" y="50" font-size="12" fill="#68748a">${escapeHtml(subtitle)}</text>
          ${body}
        </svg>
      </section>`;
  }

  function barMarkup(chart, canvasWidth) {
    const data = chart.data.slice(0, chart.limit || 20);
    const width = Math.max(560, Math.round(canvasWidth || 760));
    const rowHeight = 36;
    const height = Math.max(330, 94 + data.length * rowHeight);
    const margin = { top: 72, right: 92, bottom: 34, left: 150 };
    const max = Math.max(...data.map((row) => Number(row[chart.value_key] || 0)), 1);
    const innerWidth = width - margin.left - margin.right;
    const bars = data.map((row, index) => {
      const value = Number(row[chart.value_key] || 0);
      const w = Math.max(2, (value / max) * innerWidth);
      const y = margin.top + index * rowHeight;
      return `
        <g>
          <text x="${margin.left - 12}" y="${y + 19}" text-anchor="end" font-size="13" fill="#334155">${escapeHtml(truncate(row[chart.label_key], 16))}</text>
          <rect x="${margin.left}" y="${y}" width="${w}" height="24" rx="5" fill="#2563eb"></rect>
          <text x="${Math.min(margin.left + w + 10, width - 34)}" y="${y + 17}" font-size="13" fill="#172033">${formatNumber(value)}</text>
        </g>`;
    }).join("");
    return chartFrame(chart, `
      <line x1="${margin.left}" y1="${margin.top - 12}" x2="${margin.left}" y2="${height - margin.bottom}" stroke="#dfe6f1"></line>
      <line x1="${margin.left}" y1="${height - margin.bottom}" x2="${width - margin.right}" y2="${height - margin.bottom}" stroke="#dfe6f1"></line>
      ${bars}`, width, height);
  }

  function columnMarkup(chart, canvasWidth) {
    const data = chart.data.slice(0, chart.limit || 12);
    const width = Math.max(560, Math.round(canvasWidth || 760));
    const height = 410;
    const margin = { top: 78, right: 28, bottom: 104, left: 66 };
    const innerWidth = width - margin.left - margin.right;
    const innerHeight = height - margin.top - margin.bottom;
    const max = Math.max(...data.map((row) => Number(row[chart.value_key] || 0)), 1);
    const slot = innerWidth / Math.max(data.length, 1);
    const barWidth = Math.max(14, Math.min(54, slot * 0.64));
    const bars = data.map((row, index) => {
      const value = Number(row[chart.value_key] || 0);
      const h = Math.max(2, (value / max) * innerHeight);
      const x = margin.left + index * slot + (slot - barWidth) / 2;
      const y = margin.top + innerHeight - h;
      const label = escapeHtml(truncate(row[chart.label_key], 10));
      return `
        <g>
          <rect x="${x}" y="${y}" width="${barWidth}" height="${h}" rx="4" fill="#2563eb"></rect>
          <text x="${x + barWidth / 2}" y="${Math.max(70, y - 7)}" text-anchor="middle" font-size="12" fill="#172033">${formatNumber(value)}</text>
          <text x="${x + barWidth / 2}" y="${margin.top + innerHeight + 18}" text-anchor="end" transform="rotate(-35 ${x + barWidth / 2} ${margin.top + innerHeight + 18})" font-size="12" fill="#334155">${label}</text>
        </g>`;
    }).join("");
    return chartFrame(chart, `
      <line x1="${margin.left}" y1="${margin.top}" x2="${margin.left}" y2="${margin.top + innerHeight}" stroke="#dfe6f1"></line>
      <line x1="${margin.left}" y1="${margin.top + innerHeight}" x2="${width - margin.right}" y2="${margin.top + innerHeight}" stroke="#dfe6f1"></line>
      ${bars}`, width, height);
  }

  function donutMarkup(chart, canvasWidth) {
    const data = chart.data.slice(0, chart.limit || 9);
    const width = Math.max(560, Math.round(canvasWidth || 760));
    const height = 430;
    const centerX = Math.min(235, width * 0.32);
    const centerY = 235;
    const radius = 112;
    const circumference = 2 * Math.PI * radius;
    const total = data.reduce((sum, row) => sum + Math.max(0, Number(row[chart.value_key] || 0)), 0) || 1;
    let offset = 0;
    const arcs = data.map((row, index) => {
      const value = Math.max(0, Number(row[chart.value_key] || 0));
      const length = (value / total) * circumference;
      const markup = `
        <circle cx="${centerX}" cy="${centerY}" r="${radius}" fill="none" stroke="${COLORS[index % COLORS.length]}"
          stroke-width="54" stroke-dasharray="${length} ${circumference - length}"
          stroke-dashoffset="${-offset}" transform="rotate(-90 ${centerX} ${centerY})">
          <title>${escapeHtml(row[chart.label_key])}：${formatNumber(value)}（${(value / total * 100).toFixed(1)}%）</title>
        </circle>`;
      offset += length;
      return markup;
    }).join("");
    const legendX = Math.max(390, width * 0.55);
    const legend = data.map((row, index) => {
      const value = Number(row[chart.value_key] || 0);
      const y = 105 + index * 31;
      return `
        <g>
          <rect x="${legendX}" y="${y - 12}" width="13" height="13" rx="3" fill="${COLORS[index % COLORS.length]}"></rect>
          <text x="${legendX + 21}" y="${y}" font-size="13" fill="#334155">${escapeHtml(truncate(row[chart.label_key], 14))}</text>
          <text x="${width - 28}" y="${y}" text-anchor="end" font-size="13" fill="#172033">${(value / total * 100).toFixed(1)}%</text>
        </g>`;
    }).join("");
    return chartFrame(chart, `
      <circle cx="${centerX}" cy="${centerY}" r="${radius}" fill="none" stroke="#e9eef7" stroke-width="54"></circle>
      ${arcs}
      <text x="${centerX}" y="${centerY - 4}" text-anchor="middle" font-size="14" fill="#68748a">合计</text>
      <text x="${centerX}" y="${centerY + 25}" text-anchor="middle" font-size="22" font-weight="800" fill="#172033">${formatNumber(total)}</text>
      ${legend}`, width, height);
  }

  function lineMarkup(chart, canvasWidth) {
    const data = chart.data.slice(0, chart.limit || 16);
    const width = Math.max(560, Math.round(canvasWidth || 760));
    const height = 390;
    const margin = { top: 82, right: 38, bottom: 78, left: 70 };
    const innerWidth = width - margin.left - margin.right;
    const innerHeight = height - margin.top - margin.bottom;
    const values = data.map((row) => Number(row[chart.value_key] || 0));
    const max = Math.max(...values, 1);
    const step = innerWidth / Math.max(data.length - 1, 1);
    const points = values.map((value, index) => `${margin.left + index * step},${margin.top + innerHeight - (value / max) * innerHeight}`).join(" ");
    const marks = data.map((row, index) => {
      const value = values[index];
      const x = margin.left + index * step;
      const y = margin.top + innerHeight - (value / max) * innerHeight;
      return `
        <g>
          <circle cx="${x}" cy="${y}" r="4" fill="#2563eb"><title>${escapeHtml(row[chart.label_key])}：${formatNumber(value)}</title></circle>
          <text x="${x}" y="${margin.top + innerHeight + 22}" text-anchor="middle" font-size="11" fill="#334155">${escapeHtml(truncate(row[chart.label_key], 8))}</text>
        </g>`;
    }).join("");
    return chartFrame(chart, `
      <line x1="${margin.left}" y1="${margin.top}" x2="${margin.left}" y2="${margin.top + innerHeight}" stroke="#dfe6f1"></line>
      <line x1="${margin.left}" y1="${margin.top + innerHeight}" x2="${width - margin.right}" y2="${margin.top + innerHeight}" stroke="#dfe6f1"></line>
      <polyline points="${points}" fill="none" stroke="#2563eb" stroke-width="3" stroke-linejoin="round" stroke-linecap="round"></polyline>
      ${marks}`, width, height);
  }

  function chartMarkup(chart, canvasWidth) {
    const renderers = {
      bar: barMarkup,
      column: columnMarkup,
      donut: donutMarkup,
      pie: donutMarkup,
      line: lineMarkup,
    };
    return (renderers[chart?.type] || barMarkup)(chart, canvasWidth);
  }

  function renderCharts(charts) {
    const canvas = $("#chartCanvas");
    const items = (charts || []).filter((chart) => chart?.data?.length);
    if (!items.length) {
      canvas.innerHTML = `<div class="empty-state">当前结果不适合绘制统计图</div>`;
      return;
    }
    const width = Math.max(560, Math.round(canvas.getBoundingClientRect().width || 760));
    canvas.innerHTML = `<div class="chart-list">${items.map((chart) => chartMarkup(chart, width)).join("")}</div>`;
  }

  function renderBarChart(chart) {
    renderCharts(chart ? [{ ...chart, type: "bar" }] : []);
  }

  window.CCFVisualizationRenderer = { renderTable, renderBarChart, renderCharts };
})();
