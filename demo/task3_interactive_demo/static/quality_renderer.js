// 质量审计渲染：展示噪声拦截、证据表和处理状态。
(function () {
  const { $, escapeHtml, formatNumber } = window.CCFCommon;

  function renderQuality(payload, renderTable, detailsOpen) {
    const summary = payload.summary || [];
    const total = payload.display_issues ?? payload.total_issues ?? 0;
    const filterText = payload.filtered ? `当前筛选：${payload.query}` : "全库质量审计";
    $("#qualityNote").innerHTML = `
      <strong>已拦截 ${formatNumber(total)} 条可疑噪声。</strong>
      <em>${escapeHtml(filterText)}</em>
      <span>${escapeHtml(payload.explanation || "这些记录用于审计，不属于最终医学知识。")}</span>
    `;
    $("#qualitySummary").innerHTML = summary.length
      ? summary
          .map(
            (item) => `
            <div class="quality-item">
              <strong>${formatNumber(item["拦截数量"])}</strong>
              <span>${escapeHtml(item["噪声类型"])} / ${escapeHtml(item["来源字段"])}</span>
              <em>${escapeHtml(item["处理状态"])}</em>
            </div>
          `,
          )
          .join("")
      : `<div class="empty-state">暂无拦截噪声</div>`;
    renderTable($("#qualityTopValues"), payload.top_values || [], 80);
    renderTable($("#qualityTable"), payload.issues || [], 90);
    updateQualityDetails(detailsOpen);
  }

  function updateQualityDetails(detailsOpen) {
    const table = $("#qualityTable");
    const button = $("#toggleQualityDetails");
    if (!table || !button) return;
    table.classList.toggle("collapsed", !detailsOpen);
    button.textContent = detailsOpen ? "收起拦截明细" : "展开拦截明细";
  }

  window.CCFQualityRenderer = {
    renderQuality,
    updateQualityDetails,
  };
})();
