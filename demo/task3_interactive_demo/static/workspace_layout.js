// 工作区布局控制：管理三栏页面的拖拽宽度和滚动区域。
(function () {
  const { $ } = window.CCFCommon;

  const LAYOUT_STORAGE_KEY = "task3DemoWorkspaceRatios";
  const LAYOUT_MIN_WIDTHS = [260, 360, 320];

  function normalizeWidths(widths, total, minWidths = LAYOUT_MIN_WIDTHS) {
    if (!Number.isFinite(total) || total <= minWidths.reduce((sum, value) => sum + value, 0)) {
      return null;
    }
    const next = widths.map((value, index) => Math.max(minWidths[index], Number(value) || minWidths[index]));
    let overflow = next.reduce((sum, value) => sum + value, 0) - total;
    let guard = 0;
    while (overflow > 0.5 && guard < 8) {
      const adjustable = next
        .map((value, index) => ({ index, room: value - minWidths[index] }))
        .filter((item) => item.room > 0.5);
      if (!adjustable.length) break;
      const share = overflow / adjustable.length;
      adjustable.forEach((item) => {
        const delta = Math.min(item.room, share);
        next[item.index] -= delta;
      });
      overflow = next.reduce((sum, value) => sum + value, 0) - total;
      guard += 1;
    }
    return next;
  }

  function getWorkspaceAvailableWidth(workspace) {
    const handlesWidth = Array.from(workspace.querySelectorAll(".workspace-resizer"))
      .reduce((sum, node) => sum + node.getBoundingClientRect().width, 0);
    return workspace.getBoundingClientRect().width - handlesWidth;
  }

  function applyWorkspaceWidths(widths, persist = true) {
    const workspace = $(".workspace");
    if (!workspace || window.matchMedia("(max-width: 1280px)").matches) return false;
    const total = getWorkspaceAvailableWidth(workspace);
    const normalized = normalizeWidths(widths, total);
    if (!normalized) return false;
    workspace.style.setProperty("--left-col", `${Math.round(normalized[0])}px`);
    workspace.style.setProperty("--center-col", `${Math.round(normalized[1])}px`);
    workspace.style.setProperty("--right-col", `${Math.round(normalized[2])}px`);
    if (persist) {
      const ratios = normalized.map((value) => value / total);
      localStorage.setItem(LAYOUT_STORAGE_KEY, JSON.stringify(ratios));
    }
    return true;
  }

  function restoreWorkspaceLayout() {
    const workspace = $(".workspace");
    if (!workspace || window.matchMedia("(max-width: 1280px)").matches) return;
    try {
      const ratios = JSON.parse(localStorage.getItem(LAYOUT_STORAGE_KEY) || "null");
      if (!Array.isArray(ratios) || ratios.length !== 3) return;
      const total = getWorkspaceAvailableWidth(workspace);
      applyWorkspaceWidths(ratios.map((ratio) => ratio * total), false);
    } catch {
      localStorage.removeItem(LAYOUT_STORAGE_KEY);
    }
  }

  function initResizableWorkspace() {
    const workspace = $(".workspace");
    if (!workspace) return;
    restoreWorkspaceLayout();
    window.addEventListener("resize", restoreWorkspaceLayout);

    workspace.querySelectorAll(".workspace-resizer").forEach((handle) => {
      handle.addEventListener("pointerdown", (event) => {
        if (window.matchMedia("(max-width: 1280px)").matches) return;
        event.preventDefault();
        const panels = [
          workspace.querySelector(".lineage-panel"),
          workspace.querySelector(".chat-panel"),
          workspace.querySelector(".insight-panel"),
        ];
        const start = {
          x: event.clientX,
          widths: panels.map((panel) => panel.getBoundingClientRect().width),
          mode: handle.dataset.resizer,
        };
        handle.classList.add("active");
        document.body.classList.add("resizing-layout");

        const onMove = (moveEvent) => {
          const dx = moveEvent.clientX - start.x;
          const next = [...start.widths];
          if (start.mode === "left") {
            const pairTotal = start.widths[0] + start.widths[1];
            next[0] = Math.min(Math.max(start.widths[0] + dx, LAYOUT_MIN_WIDTHS[0]), pairTotal - LAYOUT_MIN_WIDTHS[1]);
            next[1] = pairTotal - next[0];
          } else {
            const pairTotal = start.widths[1] + start.widths[2];
            next[1] = Math.min(Math.max(start.widths[1] + dx, LAYOUT_MIN_WIDTHS[1]), pairTotal - LAYOUT_MIN_WIDTHS[2]);
            next[2] = pairTotal - next[1];
          }
          applyWorkspaceWidths(next);
        };

        const onUp = () => {
          handle.classList.remove("active");
          document.body.classList.remove("resizing-layout");
          window.removeEventListener("pointermove", onMove);
          window.removeEventListener("pointerup", onUp);
          window.removeEventListener("pointercancel", onUp);
        };

        window.addEventListener("pointermove", onMove);
        window.addEventListener("pointerup", onUp);
        window.addEventListener("pointercancel", onUp);
      });

      handle.addEventListener("keydown", (event) => {
        if (!["ArrowLeft", "ArrowRight"].includes(event.key)) return;
        event.preventDefault();
        const panels = [
          workspace.querySelector(".lineage-panel"),
          workspace.querySelector(".chat-panel"),
          workspace.querySelector(".insight-panel"),
        ];
        const next = panels.map((panel) => panel.getBoundingClientRect().width);
        const delta = event.key === "ArrowLeft" ? -32 : 32;
        if (handle.dataset.resizer === "left") {
          const pairTotal = next[0] + next[1];
          next[0] = Math.min(Math.max(next[0] + delta, LAYOUT_MIN_WIDTHS[0]), pairTotal - LAYOUT_MIN_WIDTHS[1]);
          next[1] = pairTotal - next[0];
        } else {
          const pairTotal = next[1] + next[2];
          next[1] = Math.min(Math.max(next[1] + delta, LAYOUT_MIN_WIDTHS[1]), pairTotal - LAYOUT_MIN_WIDTHS[2]);
          next[2] = pairTotal - next[1];
        }
        applyWorkspaceWidths(next);
      });
    });
  }

  window.CCFWorkspaceLayout = {
    initResizableWorkspace,
  };
})();
