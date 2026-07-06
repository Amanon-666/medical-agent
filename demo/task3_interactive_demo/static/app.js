// 页面主编排：负责数据流、问答请求和右侧图谱/图表面板刷新。
const {
  $,
  api,
  escapeHtml,
  formatNumber,
  formatPercent,
  formatClock,
  truncate,
  setHealth,
} = window.CCFCommon;

const { initResizableWorkspace } = window.CCFWorkspaceLayout;
const { renderMarkdown } = window.CCFMarkdown;
const { renderQuality: renderQualityPanel, updateQualityDetails: updateQualityDetailsPanel } = window.CCFQualityRenderer;
const { renderTable, renderBarChart } = window.CCFVisualizationRenderer;
const { renderGraph: renderGraphPanel, renderDiseaseChart } = window.CCFGraphRenderer;

const state = {
  overview: null,
  evaluation: null,
  lastQuery: null,
  graph: null,
  currentDisease: "",
  graphHistory: [],
  quality: null,
  qualityDetailsOpen: false,
  lastRefreshAt: null,
  sourceDeleteEnabled: false,
};

async function refreshOverviewAndLineage() {
  const [overview, lineage, evaluation] = await Promise.all([
    api("/api/overview"),
    api("/api/lineage"),
    api("/api/evaluation"),
  ]);
  state.overview = overview;
  state.evaluation = evaluation;
  state.lastRefreshAt = new Date();
  renderMetrics(overview);
  renderEvaluation(evaluation);
  renderLineage(lineage);
  setHealth(true, `已刷新：${formatClock(state.lastRefreshAt)}`);
}

function renderLineage(payload) {
  const container = $("#lineageCanvas");
  const totalSources = payload.source_total_count ?? (payload.sources || []).length;
  const returnedSources = payload.source_returned_count ?? (payload.sources || []).length;
  const refreshed = state.lastRefreshAt ? `<div class="lineage-refresh-note">最近刷新：${escapeHtml(formatClock(state.lastRefreshAt))}，已登记来源 ${formatNumber(totalSources)} 项，当前展示 ${formatNumber(returnedSources)} 项</div>` : "";
  const nodeHtml = payload.nodes
    .map(
      (node, index) => `
      <div class="lineage-node" data-type="${escapeHtml(node.type)}" title="${escapeHtml(node.detail)}">
        <div class="node-index">${index + 1}</div>
        <div>
          <div class="lineage-title">${escapeHtml(node.label)}</div>
          <div class="lineage-detail">${escapeHtml(node.detail)}</div>
        </div>
      </div>
    `,
    )
    .join("");
  const sources = payload.sources || [];
  const sourceHtml = sources.length
    ? `
      <div class="lineage-source-list">
        <div class="lineage-source-title">最近登记来源</div>
        ${sources
          .map(
            (source) => `
              <div class="lineage-source-item">
                <div class="lineage-source-main">
                  <strong>${escapeHtml(source.source_name)}</strong>
                  <span>${escapeHtml(source.source_type || "-")} / ${formatNumber(source.record_count || 0)} 条</span>
                </div>
                <button type="button" class="source-delete-button" data-source-id="${escapeHtml(source.source_id || "")}" data-source-name="${escapeHtml(source.source_name || "")}" title="删除前会自动备份 KG 和分析库">删除来源</button>
              </div>
            `,
          )
          .join("")}
      </div>
    `
    : "";
  container.innerHTML = nodeHtml + sourceHtml + refreshed;
  container.querySelectorAll(".source-delete-button").forEach((button) => {
    button.addEventListener("click", async () => {
      const name = button.dataset.sourceName || "该来源";
      const sourceId = Number(button.dataset.sourceId || 0);
      if (!sourceId) return;
      const confirmed = window.confirm(`将删除数据来源：${name}\n\n系统会先备份 KG 与分析库，再删除该来源关联的三元组、质量记录和孤立实体。是否继续？`);
      if (!confirmed) return;
      const token = window.prompt("请输入维护口令：");
      if (!token) return;
      const forceProtected = name.startsWith("QASystemOnMedicalKG:") || name.startsWith("CBLUE:")
        ? window.confirm("这是初始基线来源。确认已有可恢复备份，并强制删除该基线来源？")
        : false;
      button.disabled = true;
      button.textContent = "删除中...";
      try {
        const result = await api("/api/delete_source", {
          method: "POST",
          body: JSON.stringify({
            source_id: sourceId,
            source_name: name,
            token,
            force_protected: forceProtected,
          }),
        });
        window.alert(`已删除来源：${result.source?.source_name || name}\nKG 备份：${result.kg_backup}\n分析库刷新：${result.refresh_analytics?.status || "-"}`);
        await refreshOverviewAndLineage();
        const graph = await api(`/api/disease_graph?disease=${encodeURIComponent(state.currentDisease || "肺泡蛋白质沉积症")}`);
        renderGraph(graph);
        await loadQuality(state.currentDisease || "");
      } catch (error) {
        window.alert(error.message);
      } finally {
        button.disabled = false;
        button.textContent = "删除来源";
      }
    });
  });
}

function renderMetrics(overview) {
  const analytics = overview.analytics_counts || {};
  const kg = overview.kg_counts || {};
  const metrics = [
    ["疾病", analytics.diseases],
    ["知识事实", analytics.disease_facts],
    ["图谱实体", kg.kg_entities],
    ["图谱关系", kg.kg_triples],
    ["症状事实", analytics.disease_symptoms],
    ["药物事实", analytics.disease_drugs],
    ["检查事实", analytics.disease_tests],
    ["已拦截噪声", kg.kg_quality_issues],
    ["登记来源", kg.kg_sources],
  ];
  $("#overviewMetrics").innerHTML = metrics
    .map(
      ([label, value]) => `
      <div class="metric">
        <strong>${formatNumber(value || 0)}</strong>
        <span>${escapeHtml(label)}</span>
      </div>
    `,
    )
    .join("");
}

function renderEvaluation(evaluation) {
  const container = $("#evaluationPanel");
  if (!container) return;
  const task2 = evaluation.task2 || {};
  const cmeee = task2.cmeee_baseline || {};
  const cmeie = task2.cmeie_selfcheck || {};
  const nl2sql = (evaluation.task3 || {}).nl2sql || {};
  const npu = evaluation.npu || {};
  const cards = [
    {
      label: "任务二抽取链",
      value: task2.extractor_label || "本地知识抽取链",
      detail: "用于实体识别、关系抽取和三元组生成",
    },
    {
      label: "实体识别评测",
      value: formatPercent(cmeee.f1),
      detail: cmeee.exists ? `样本 ${formatNumber(cmeee.sample_count || 0)}；精确率 ${formatPercent(cmeee.precision)} / 召回率 ${formatPercent(cmeee.recall)}` : "未找到报告",
    },
    {
      label: "关系抽取自检",
      value: formatPercent(cmeie.f1),
      detail: cmeie.exists ? `诊断样本 ${formatNumber(cmeie.sample_count || 0)} 条` : "未找到报告",
    },
    {
      label: "NL2SQL 准确率",
      value: formatPercent(nl2sql.accuracy),
      detail: nl2sql.exists ? `${formatNumber(nl2sql.passed || 0)}/${formatNumber(nl2sql.total || 0)} 通过；85% 阈值 ${nl2sql.meets_85_percent ? "已满足" : "未满足"}` : "未找到报告",
    },
    {
      label: "任务二运行效率",
      value: "随任务返回",
      detail: task2.runtime_metric_label || "展示吞吐量、平均耗时和入库数量",
    },
    {
      label: "NPU 状态",
      value: npu.status || "-",
      detail: npu.note || "",
    },
  ];
  container.innerHTML = `
    <div class="section-title">评测概览</div>
    <div class="eval-grid">
      ${cards
        .map(
          (card) => `
            <div class="eval-card">
              <span>${escapeHtml(card.label)}</span>
              <strong>${escapeHtml(card.value)}</strong>
              <small>${escapeHtml(card.detail)}</small>
            </div>
          `,
        )
        .join("")}
    </div>
  `;
}

function renderSamples(questions) {
  const container = $("#sampleQuestions");
  container.innerHTML = questions
    .map((question) => `<button type="button" title="${escapeHtml(question)}">${escapeHtml(question)}</button>`)
    .join("");
  container.querySelectorAll("button").forEach((button) => {
    button.addEventListener("click", () => {
      $("#questionInput").value = button.textContent;
      $("#queryForm").requestSubmit();
    });
  });
}

function addMessage(role, content, extraHtml = "") {
  const log = $("#chatLog");
  const message = document.createElement("div");
  message.className = `message ${role}`;
  const body = role === "assistant" ? renderMarkdown(content) : escapeHtml(content);
  message.innerHTML = `<div class="bubble">${body}${extraHtml}</div>`;
  log.appendChild(message);
  log.scrollTop = log.scrollHeight;
  return message;
}

function renderSteps(steps = []) {
  if (!steps.length) return "";
  return `
    <div class="steps">
      ${steps
        .map(
          (step) => `
            <div class="step ${escapeHtml(step.status || "done")}">
              <span class="step-dot"></span>
              <span><strong>${escapeHtml(step.name)}</strong>：${escapeHtml(step.detail || "")}</span>
            </div>
          `,
        )
        .join("")}
    </div>
  `;
}

function renderAgentSummary(summary) {
  if (!summary) return "";
  const records = summary.tool_records || [];
  return `
    <div class="agent-summary">
      <div><strong>处理事件</strong>：${formatNumber(summary.event_count || 0)} 条</div>
      ${
        records.length
          ? `<ul>${records
              .slice(0, 4)
              .map((item) => `<li>${escapeHtml(truncate(item.detail || item.tool || "", 90))}</li>`)
              .join("")}</ul>`
          : ""
      }
    </div>
  `;
}

function activateTab(name) {
  document.querySelectorAll(".tab").forEach((tab) => {
    tab.classList.toggle("active", tab.dataset.tab === name);
  });
  document.querySelectorAll(".tab-pane").forEach((pane) => {
    pane.classList.toggle("active", pane.id === `tab-${name}`);
  });
}

async function loadQuality(query = "") {
  const path = query ? `/api/quality?query=${encodeURIComponent(query)}` : "/api/quality";
  const payload = await api(path);
  state.quality = payload;
  renderQualityPanel(payload, renderTable, state.qualityDetailsOpen);
}

async function loadInitialData() {
  try {
    const health = await api("/api/health");
    state.sourceDeleteEnabled = Boolean(health.source_delete_enabled);
    setHealth(Boolean(health.analytics_db_exists && health.kg_db_exists), health.analytics_db_exists && health.kg_db_exists ? "已连接" : "数据库缺失");

    const [overview, lineage, evaluation, graph, quality] = await Promise.all([
      api("/api/overview"),
      api("/api/lineage"),
      api("/api/evaluation"),
      api(`/api/disease_graph?disease=${encodeURIComponent("肺泡蛋白质沉积症")}`),
      api("/api/quality"),
    ]);

    state.overview = overview;
    state.evaluation = evaluation;
    state.quality = quality;
    renderMetrics(overview);
    renderEvaluation(evaluation);
    renderSamples(overview.sample_questions || []);
    renderLineage(lineage);
    renderGraph(graph);
    renderQualityPanel(quality, renderTable, state.qualityDetailsOpen);
    renderBarChart({
      type: "bar",
      title: "科室关联疾病 Top 10",
      subtitle: "来自任务三分析库 v_department_disease_counts，反映图谱中科室和疾病的关联覆盖度。",
      label_key: "科室",
      value_key: "疾病数量",
      data: (overview.top_departments || []).map((row) => ({
        科室: row.department,
        疾病数量: row.disease_count,
      })),
    });
    addMessage(
      "assistant",
      "已载入本地医学知识图谱和分析库。你可以直接询问某个疾病的症状、检查、治疗、用药、科室，也可以问实体或关系统计。",
    );
    setHealth(true, `已刷新：${formatClock(new Date())}`);
  } catch (error) {
    setHealth(false, "连接失败");
    addMessage("assistant", `初始化失败：${error.message}`);
  }
}

async function submitQuestion(question) {
  addMessage("user", question);
  const useAgent = $("#agentModeToggle")?.checked;
  const loading = addMessage(
    "assistant",
    useAgent ? "正在调用 Nexent 任务三智能体..." : "正在处理问题...",
    renderSteps([
      { name: "接收问题", status: "done", detail: "准备识别意图" },
      {
        name: useAgent ? "Nexent 智能体编排" : "查询知识库",
        status: "warn",
        detail: "等待后端返回",
      },
    ]),
  );

  try {
    const result = await api(useAgent ? "/api/agent_query" : "/api/query", {
      method: "POST",
      body: JSON.stringify({ question }),
    });
    state.lastQuery = result;
    loading.querySelector(".bubble").innerHTML = `
      ${renderMarkdown(result.answer || "查询完成。")}
      ${renderSteps(result.steps || [])}
      ${renderAgentSummary(result.events_summary)}
      <div class="hint">模板：${escapeHtml(result.template || "-")}；返回 ${formatNumber(result.row_count || 0)} 行</div>
    `;
    renderTable($("#evidenceTable"), result.rows || [], 120);
    renderBarChart(result.chart);
    if (result.disease) {
      $("#diseaseInput").value = result.disease;
      api(`/api/disease_graph?disease=${encodeURIComponent(result.disease)}`)
        .then((payload) => {
          state.currentDisease = payload.disease || result.disease;
          renderGraph(payload);
        })
        .catch(() => {});
      loadQuality(result.disease).catch(() => {});
    } else {
      loadQuality(question).catch(() => {});
    }
    if (result.rows && result.rows.length) {
      activateTab(result.chart ? "chart" : "evidence");
    }
  } catch (error) {
    loading.querySelector(".bubble").innerHTML = renderMarkdown(`处理失败：${error.message}`);
  }
}

function renderGraph(payload) {
  state.graph = payload;
  if (payload?.disease) state.currentDisease = payload.disease;
  renderGraphPanel(payload, {
    historyCount: state.graphHistory.length,
    onBack: goBackGraph,
    onExpand: async (disease) => {
      $("#diseaseInput").value = disease;
      await loadGraph({ source: "graph-node" });
    },
    onChart: renderDiseaseChart,
  });
}

async function loadGraph(options = {}) {
  const disease = $("#diseaseInput").value.trim() || "肺泡蛋白质沉积症";
  if (!options.replaceHistory && state.currentDisease && state.currentDisease !== disease) {
    state.graphHistory.push(state.currentDisease);
  }
  const payload = await api(`/api/disease_graph?disease=${encodeURIComponent(disease)}`);
  state.currentDisease = payload.disease || disease;
  $("#diseaseInput").value = state.currentDisease;
  renderGraph(payload);
  renderTable($("#evidenceTable"), payload.facts || [], 120);
  await loadQuality(state.currentDisease);
  activateTab("graph");
}

async function goBackGraph() {
  const previous = state.graphHistory.pop();
  if (!previous) return;
  $("#diseaseInput").value = previous;
  await loadGraph({ replaceHistory: true });
}

document.addEventListener("DOMContentLoaded", () => {
  initResizableWorkspace();

  document.querySelectorAll(".tab").forEach((tab) => {
    tab.addEventListener("click", () => activateTab(tab.dataset.tab));
  });

  $("#queryForm").addEventListener("submit", (event) => {
    event.preventDefault();
    const input = $("#questionInput");
    const question = input.value.trim();
    if (!question) return;
    input.value = "";
    submitQuestion(question);
  });

  $("#loadGraph").addEventListener("click", () => {
    loadGraph().catch((error) => {
      $("#graphCanvas").innerHTML = `<div class="empty-state">加载失败：${escapeHtml(error.message)}</div>`;
    });
  });

  $("#refreshLineage").addEventListener("click", () => {
    const button = $("#refreshLineage");
    const originalText = button.textContent;
    button.disabled = true;
    button.textContent = "刷新中...";
    refreshOverviewAndLineage()
      .catch((error) => setHealth(false, error.message))
      .finally(() => {
        button.disabled = false;
        button.textContent = originalText;
      });
  });

  $("#toggleQualityDetails").addEventListener("click", () => {
    state.qualityDetailsOpen = !state.qualityDetailsOpen;
    updateQualityDetailsPanel(state.qualityDetailsOpen);
  });

  loadInitialData();
});
