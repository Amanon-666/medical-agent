// 关系图渲染：展示以疾病为中心的知识图谱子图。
(function () {
  const { $, escapeHtml } = window.CCFCommon;
  const { renderBarChart } = window.CCFVisualizationRenderer;

  const SVG_NS = "http://www.w3.org/2000/svg";

  function relationName(type) {
    const names = {
      has_symptom: "症状",
      uses_drug: "药物治疗",
      needs_test: "检查",
      has_department: "就诊科室",
      has_procedure: "治疗方式",
      has_cause: "病因",
      has_prevention: "预防",
      has_complication: "并发症",
      belongs_to_category: "所属类别",
      belongs_to_department: "所属科室",
      requires_test: "检查",
      treated_by_drug: "药物治疗",
      treated_by_procedure: "治疗方式",
      visit_department: "就诊科室",
      susceptible_population: "易感人群",
      affects_body_part: "发病部位",
      transmission_way: "传播途径",
      differential_diagnosis: "鉴别诊断",
      alias_of: "别名",
      disease: "疾病",
    };
    return names[type] || type || "其他";
  }

  function graphColor(type) {
    if (type === "disease") return "#2563eb";
    if (type === "has_symptom") return "#14804a";
    if (type === "uses_drug") return "#b7791f";
    if (type === "needs_test") return "#6d28d9";
    if (type === "has_department") return "#c2413b";
    if (type === "has_procedure") return "#0891b2";
    if (type === "has_cause") return "#7c2d12";
    if (type === "has_prevention") return "#0f766e";
    return "#64748b";
  }

  function svgEl(tag, attrs = {}) {
    const node = document.createElementNS(SVG_NS, tag);
    Object.entries(attrs).forEach(([key, value]) => {
      if (value !== undefined && value !== null) node.setAttribute(key, String(value));
    });
    return node;
  }

  function setWrappedSvgText(textEl, value, maxChars = 8, maxLines = 2) {
    textEl.textContent = "";
    const raw = String(value || "");
    const lines = [];
    for (let index = 0; index < raw.length && lines.length < maxLines; index += maxChars) {
      let line = raw.slice(index, index + maxChars);
      if (index + maxChars < raw.length && lines.length === maxLines - 1) {
        line = `${line.slice(0, Math.max(1, maxChars - 1))}…`;
      }
      lines.push(line);
    }
    if (!lines.length) lines.push("-");
    lines.forEach((line, index) => {
      const tspan = svgEl("tspan", { x: textEl.getAttribute("x"), dy: index === 0 ? 0 : 14 });
      tspan.textContent = line;
      textEl.appendChild(tspan);
    });
  }

  function computeGraphLayout(nodes, edges, width, height) {
    const center = { x: width / 2, y: height / 2 + 10 };
    const outer = nodes.filter((node) => node.id !== "disease");
    const byRelation = new Map();
    outer.forEach((node) => {
      const edge = edges.find((item) => item.target === node.id);
      const key = edge?.label || relationName(node.type);
      if (!byRelation.has(key)) byRelation.set(key, []);
      byRelation.get(key).push(node);
    });

    const groups = Array.from(byRelation.entries()).sort((a, b) => a[0].localeCompare(b[0], "zh-CN"));
    const positions = { disease: { ...center, labelX: center.x, labelY: center.y + 48, anchor: "middle" } };
    const rx = Math.min(300, Math.max(150, width * 0.32));
    const ry = Math.min(205, Math.max(145, height * 0.31));
    let cursor = 0;
    const totalSlots = Math.max(outer.length + groups.length * 0.7, 1);

    groups.forEach(([, group], groupIndex) => {
      const span = (Math.PI * 2 * Math.max(group.length, 1)) / totalSlots;
      const base = -Math.PI / 2 + (Math.PI * 2 * cursor) / totalSlots + span / 2;
      group.forEach((node, index) => {
        const offset = group.length === 1 ? 0 : (index - (group.length - 1) / 2) * Math.min(0.24, span / group.length);
        const angle = base + offset + groupIndex * 0.025;
        const ringOffset = index % 2 === 0 ? 0 : 26;
        const cos = Math.cos(angle);
        const sin = Math.sin(angle);
        const x = center.x + cos * (rx + ringOffset);
        const y = center.y + sin * (ry + ringOffset * 0.45);
        const side = cos > 0.2 ? "right" : cos < -0.2 ? "left" : "middle";
        positions[node.id] = {
          x,
          y,
          labelX: Math.min(width - 18, Math.max(18, x + (side === "right" ? 28 : side === "left" ? -28 : 0))),
          labelY: Math.min(height - 28, Math.max(28, y + (sin > 0 ? 29 : -24))),
          anchor: side === "right" ? "start" : side === "left" ? "end" : "middle",
          side,
        };
      });
      cursor += group.length + 0.7;
    });

    ["left", "right", "middle"].forEach((side) => {
      const items = outer
        .map((node) => ({ node, pos: positions[node.id] }))
        .filter((item) => item.pos?.side === side)
        .sort((a, b) => a.pos.labelY - b.pos.labelY);
      let lastY = 42;
      items.forEach((item) => {
        item.pos.labelY = Math.max(item.pos.labelY, lastY + 22);
        item.pos.labelY = Math.min(item.pos.labelY, height - 28);
        lastY = item.pos.labelY;
      });
    });

    return positions;
  }

  function renderGraphSummary(payload, selectedNode = null) {
    const nodes = payload.nodes || [];
    const edges = payload.edges || [];
    const selected = selectedNode
      ? `
        <div class="selected-node">
          <strong>当前选中：${escapeHtml(selectedNode.label)}</strong>
          <span>${escapeHtml(relationName(selectedNode.type))}${selectedNode.source ? ` / 来源：${escapeHtml(selectedNode.source)}` : ""}</span>
        </div>
      `
      : "";
    $("#graphSummary").innerHTML = `
      <strong>${escapeHtml(payload.disease)}</strong>
      <div>${escapeHtml(payload.description || "暂无简介。")}</div>
      ${selected}
      <div class="hint">节点 ${nodes.length} 个，关系 ${edges.length} 条。可拖拽节点、滚轮缩放、拖动画布平移；点击节点高亮关系，双击节点可尝试展开为新的疾病子图。</div>
    `;
  }

  function renderDiseaseChart(payload) {
    const counts = payload.relation_counts || {};
    const rows = Object.entries(counts)
      .map(([type, count]) => ({ 关系类型: relationName(type), 数量: count, 编码: type }))
      .sort((a, b) => Number(b.数量) - Number(a.数量));
    if (!rows.length) {
      renderBarChart(null);
      return;
    }
    renderBarChart({
      type: "bar",
      title: `${payload.disease || "当前疾病"} 关系类型分布`,
      subtitle: "由当前关系子图实时汇总，点击/返回不同实体时会同步变化。",
      label_key: "关系类型",
      value_key: "数量",
      data: rows,
    });
  }

  function renderGraph(payload, options = {}) {
    const canvas = $("#graphCanvas");
    const nodes = payload.nodes || [];
    const edges = payload.edges || [];
    if (nodes.length === 0) {
      canvas.innerHTML = `<div class="empty-state">暂无关系子图</div>`;
      return;
    }

    const width = Math.max(520, Math.round(canvas.getBoundingClientRect().width || 760));
    const height = 520;
    const positions = computeGraphLayout(nodes, edges, width, height);
    const nodeById = new Map(nodes.map((node) => [node.id, node]));

    canvas.innerHTML = `
      <div class="graph-toolbar">
        <button type="button" data-graph-action="back">返回上一个</button>
        <button type="button" data-graph-action="reset">重置视图</button>
        <button type="button" data-graph-action="toggle-relations">显示关系名</button>
      </div>
    `;
    const svg = svgEl("svg", { viewBox: `0 0 ${width} ${height}`, role: "img", "aria-label": "疾病关系子图" });
    const viewport = svgEl("g", { class: "graph-viewport" });
    const bg = svgEl("rect", { class: "graph-bg", x: 0, y: 0, width, height });
    const edgeLayer = svgEl("g", { class: "edge-layer" });
    const labelLayer = svgEl("g", { class: "label-layer" });
    const nodeLayer = svgEl("g", { class: "node-layer" });
    viewport.append(bg, edgeLayer, labelLayer, nodeLayer);
    svg.appendChild(viewport);
    canvas.appendChild(svg);

    const view = { scale: 1, tx: 0, ty: 0, showRelations: false, selectedId: null, draggingNode: false };

    function applyView() {
      viewport.setAttribute("transform", `translate(${view.tx} ${view.ty}) scale(${view.scale})`);
    }

    function pointerToGraph(event) {
      const rect = svg.getBoundingClientRect();
      const x = ((event.clientX - rect.left) / rect.width) * width;
      const y = ((event.clientY - rect.top) / rect.height) * height;
      return { x: (x - view.tx) / view.scale, y: (y - view.ty) / view.scale };
    }

    function updateEdge(edge, line, label) {
      const a = positions[edge.source];
      const b = positions[edge.target];
      if (!a || !b) return;
      line.setAttribute("x1", a.x);
      line.setAttribute("y1", a.y);
      line.setAttribute("x2", b.x);
      line.setAttribute("y2", b.y);
      label.setAttribute("x", (a.x + b.x) / 2);
      label.setAttribute("y", (a.y + b.y) / 2 - 8);
    }

    function updateNode(node, group, circle, text, guide) {
      const p = positions[node.id];
      group.setAttribute("transform", `translate(${p.x} ${p.y})`);
      const radius = node.id === "disease" ? 30 : 17;
      circle.setAttribute("r", radius);
      const hit = group.querySelector(".node-hit-area");
      if (hit) hit.setAttribute("r", node.id === "disease" ? radius + 24 : radius + 16);
      guide.setAttribute("x1", 0);
      guide.setAttribute("y1", 0);
      guide.setAttribute("x2", p.labelX - p.x);
      guide.setAttribute("y2", p.labelY - p.y);
      text.setAttribute("x", p.labelX - p.x);
      text.setAttribute("y", p.labelY - p.y);
      text.setAttribute("text-anchor", p.anchor);
      Array.from(text.children).forEach((tspan) => tspan.setAttribute("x", p.labelX - p.x));
    }

    const edgeDom = edges.map((edge) => {
      const group = svgEl("g", { class: "graph-edge", "data-source": edge.source, "data-target": edge.target });
      const line = svgEl("line");
      const label = svgEl("text", { class: "edge-label", "text-anchor": "middle" });
      label.textContent = edge.label || relationName(nodeById.get(edge.target)?.type);
      group.append(line, label);
      edgeLayer.appendChild(group);
      updateEdge(edge, line, label);
      return { edge, group, line, label };
    });

    const nodeDom = nodes.map((node) => {
      const p = positions[node.id];
      const group = svgEl("g", { class: "graph-node", "data-id": node.id, tabindex: 0 });
      const guide = svgEl("line", { class: "node-label-guide" });
      const hit = svgEl("circle", { class: "node-hit-area" });
      const circle = svgEl("circle", { fill: graphColor(node.type) });
      const text = svgEl("text", { class: "node-label" });
      const title = svgEl("title");
      title.textContent = `${node.label}${node.source ? ` / ${node.source}` : ""}`;
      setWrappedSvgText(text, node.label, node.id === "disease" ? 12 : 8, node.id === "disease" ? 2 : 2);
      group.append(guide, hit, circle, text, title);
      nodeLayer.appendChild(group);
      updateNode(node, group, circle, text, guide);
      group.addEventListener("click", (event) => {
        event.stopPropagation();
        selectNode(node.id);
      });
      group.addEventListener("dblclick", (event) => {
        event.stopPropagation();
        Promise.resolve(options.onExpand?.(node.label)).catch((error) => {
          $("#graphSummary").innerHTML = `<div class="empty-state">展开失败：${escapeHtml(error.message)}</div>`;
        });
      });
      group.addEventListener("pointerdown", (event) => {
        event.stopPropagation();
        event.preventDefault();
        view.draggingNode = true;
        canvas.classList.add("dragging-node");
        group.setPointerCapture(event.pointerId);
        selectNode(node.id);
        const start = pointerToGraph(event);
        const origin = { x: p.x, y: p.y, labelX: p.labelX, labelY: p.labelY };
        const move = (moveEvent) => {
          const current = pointerToGraph(moveEvent);
          const dx = current.x - start.x;
          const dy = current.y - start.y;
          p.x = origin.x + dx;
          p.y = origin.y + dy;
          p.labelX = origin.labelX + dx;
          p.labelY = origin.labelY + dy;
          updateNode(node, group, circle, text, guide);
          edgeDom.forEach((item) => {
            if (item.edge.source === node.id || item.edge.target === node.id) updateEdge(item.edge, item.line, item.label);
          });
        };
        const up = () => {
          view.draggingNode = false;
          canvas.classList.remove("dragging-node");
          window.removeEventListener("pointermove", move);
          window.removeEventListener("pointerup", up);
          window.removeEventListener("pointercancel", up);
        };
        window.addEventListener("pointermove", move);
        window.addEventListener("pointerup", up);
        window.addEventListener("pointercancel", up);
      });
      return { node, group, circle, text, guide };
    });

    function selectNode(id) {
      view.selectedId = id;
      nodeDom.forEach((item) => item.group.classList.toggle("selected", item.node.id === id));
      edgeDom.forEach((item) => {
        const active = id !== "disease" && (item.edge.source === id || item.edge.target === id);
        item.group.classList.toggle("active", active);
      });
      renderGraphSummary(payload, nodeById.get(id));
    }

    function toggleRelationLabels() {
      view.showRelations = !view.showRelations;
      canvas.classList.toggle("show-relation-labels", view.showRelations);
      canvas.querySelector('[data-graph-action="toggle-relations"]').textContent = view.showRelations ? "隐藏关系名" : "显示关系名";
    }

    function resetView() {
      view.scale = 1;
      view.tx = 0;
      view.ty = 0;
      applyView();
    }

    canvas.querySelector('[data-graph-action="reset"]').addEventListener("click", resetView);
    canvas.querySelector('[data-graph-action="toggle-relations"]').addEventListener("click", toggleRelationLabels);
    const backButton = canvas.querySelector('[data-graph-action="back"]');
    backButton.disabled = Number(options.historyCount || 0) === 0;
    backButton.addEventListener("click", () => options.onBack?.());
    svg.addEventListener("click", () => selectNode("disease"));
    svg.addEventListener("wheel", (event) => {
      event.preventDefault();
      const before = pointerToGraph(event);
      const factor = event.deltaY < 0 ? 1.12 : 0.9;
      view.scale = Math.min(2.2, Math.max(0.65, view.scale * factor));
      const rect = svg.getBoundingClientRect();
      const sx = ((event.clientX - rect.left) / rect.width) * width;
      const sy = ((event.clientY - rect.top) / rect.height) * height;
      view.tx = sx - before.x * view.scale;
      view.ty = sy - before.y * view.scale;
      applyView();
    }, { passive: false });
    svg.addEventListener("pointerdown", (event) => {
      if (view.draggingNode) return;
      if (event.target.closest(".graph-node")) return;
      svg.setPointerCapture(event.pointerId);
      const start = { x: event.clientX, y: event.clientY, tx: view.tx, ty: view.ty };
      const rect = svg.getBoundingClientRect();
      const move = (moveEvent) => {
        view.tx = start.tx + ((moveEvent.clientX - start.x) / rect.width) * width;
        view.ty = start.ty + ((moveEvent.clientY - start.y) / rect.height) * height;
        applyView();
      };
      const up = () => {
        svg.removeEventListener("pointermove", move);
        svg.removeEventListener("pointerup", up);
        svg.removeEventListener("pointercancel", up);
      };
      svg.addEventListener("pointermove", move);
      svg.addEventListener("pointerup", up);
      svg.addEventListener("pointercancel", up);
    });

    renderGraphSummary(payload);
    selectNode("disease");
    options.onChart?.(payload);
  }

  window.CCFGraphRenderer = {
    relationName,
    renderDiseaseChart,
    renderGraph,
  };
})();
