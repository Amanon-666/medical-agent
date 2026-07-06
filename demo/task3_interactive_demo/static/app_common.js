// 浏览器通用工具：提供 DOM 查询、转义、数字格式化等基础函数。
(function () {
  function $(selector) {
    return document.querySelector(selector);
  }

  async function api(path, options = {}) {
    const response = await fetch(path, {
      headers: { "Content-Type": "application/json" },
      ...options,
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || `请求失败：${response.status}`);
    }
    return data;
  }

  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");
  }

  function formatNumber(value) {
    const n = Number(value);
    return Number.isFinite(n) ? n.toLocaleString("zh-CN") : String(value ?? "");
  }

  function formatPercent(value) {
    const n = Number(value);
    return Number.isFinite(n) ? `${(n * 100).toFixed(1)}%` : "-";
  }

  function formatClock(date = new Date()) {
    return date.toLocaleTimeString("zh-CN", {
      hour12: false,
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  }

  function truncate(value, max = 18) {
    const text = String(value ?? "");
    return text.length > max ? `${text.slice(0, max)}...` : text;
  }

  function setHealth(ok, text) {
    const node = $("#healthStatus");
    node.classList.toggle("ok", ok);
    node.classList.toggle("error", !ok);
    node.textContent = text;
  }

  window.CCFCommon = {
    $,
    api,
    escapeHtml,
    formatNumber,
    formatPercent,
    formatClock,
    truncate,
    setHealth,
  };
})();
