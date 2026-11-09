PROMPT_PROFILES_TAB = "Prompt Profiles"
LIVE_CONVERSATION_TAB = "Live Conversation"
BIO_EDITOR_TAB = "Bio Editor"
TAG_EDITOR_TAB = "Tag Editor"
DOCUMENTATION_TAB = "Documentation"

TAB_REORDER_JS = r"""
(function () {
  if (window.__mantellaTabReorderInit) {
    return;
  }
  window.__mantellaTabReorderInit = true;
  const STORAGE_KEY = "mantella-tab-order";
  const DRAG_THRESHOLD_PX = 24;
  let applying = false;
  let setupTimer = null;
  let drag = null;

  function isMainTabNav(nav) {
    if (!nav || !nav.classList || !nav.classList.contains("tab-nav")) {
      return false;
    }
    const labels = buttonLabels(nav);
    return labels.indexOf("Game") !== -1
      || labels.indexOf("Bio Editor") !== -1
      || labels.indexOf("Documentation") !== -1;
  }

  function mainTabNavs() {
    return Array.prototype.filter.call(document.querySelectorAll(".tab-nav"), isMainTabNav);
  }

  function buttons(nav) {
    return Array.prototype.slice.call(nav.querySelectorAll(":scope > button"));
  }

  function buttonLabels(nav) {
    return buttons(nav).map(function (btn) {
      return (btn.textContent || "").trim();
    });
  }

  function ordersMatch(current, desired) {
    if (!current || !desired || current.length !== desired.length) {
      return false;
    }
    for (let i = 0; i < current.length; i++) {
      if (current[i] !== desired[i]) {
        return false;
      }
    }
    return true;
  }

  function desiredOrder(current, saved) {
    const currentSet = {};
    current.forEach(function (name) {
      currentSet[name] = true;
    });
    const ordered = [];
    const seen = {};
    (saved || []).forEach(function (name) {
      if (currentSet[name] && !seen[name]) {
        ordered.push(name);
        seen[name] = true;
      }
    });
    // A tab the saved order doesn't know goes right after the tab before it in the page's own order, not at the end
    current.forEach(function (name, index) {
      if (seen[name]) {
        return;
      }
      let position = 0;
      for (let i = index - 1; i >= 0; i--) {
        if (seen[current[i]]) {
          position = ordered.indexOf(current[i]) + 1;
          break;
        }
      }
      ordered.splice(position, 0, name);
      seen[name] = true;
    });
    return ordered;
  }

  function readSavedOrder() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) {
        return null;
      }
      const parsed = JSON.parse(raw);
      return Array.isArray(parsed) ? parsed : null;
    } catch (e) {
      return null;
    }
  }

  function saveOrder(order) {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(order));
    } catch (e) {}
    try {
      fetch("/tab-order", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ order: order })
      }).catch(function () {});
    } catch (e) {}
  }

  function applyOrder(nav) {
    const current = buttons(nav);
    const labels = current.map(function (btn) {
      return (btn.textContent || "").trim();
    });
    const desired = desiredOrder(labels, readSavedOrder());
    if (ordersMatch(labels, desired)) {
      return;
    }
    const byLabel = {};
    current.forEach(function (btn) {
      const label = (btn.textContent || "").trim();
      if (!byLabel[label]) {
        byLabel[label] = [];
      }
      byLabel[label].push(btn);
    });
    applying = true;
    desired.forEach(function (name, index) {
      const list = byLabel[name];
      if (!list || !list.length) {
        return;
      }
      const btn = list.shift();
      const reference = nav.children[index];
      if (reference !== btn) {
        nav.insertBefore(btn, reference || null);
      }
    });
    queueMicrotask(function () {
      applying = false;
    });
  }

  function bindNav(nav) {
    if (nav.dataset.mantellaReorder === "1") {
      return;
    }
    nav.dataset.mantellaReorder = "1";
    nav.addEventListener("pointerdown", function (e) {
      if (e.button !== 0) {
        return;
      }
      const btn = e.target.closest("button");
      if (!btn || btn.parentElement !== nav) {
        return;
      }
      drag = {
        nav: nav,
        btn: btn,
        startX: e.clientX,
        startY: e.clientY,
        started: false,
        pointerId: e.pointerId
      };
    });
  }

  function onPointerMove(e) {
    if (!drag) {
      return;
    }
    const dx = e.clientX - drag.startX;
    const dy = e.clientY - drag.startY;
    if (!drag.started) {
      if ((dx * dx + dy * dy) < DRAG_THRESHOLD_PX * DRAG_THRESHOLD_PX) {
        return;
      }
      drag.started = true;
      drag.btn.classList.add("mantella-tab-dragging");
      try {
        drag.btn.setPointerCapture(drag.pointerId);
      } catch (err) {}
    }
    e.preventDefault();
    const siblings = buttons(drag.nav).filter(function (btn) {
      return btn !== drag.btn;
    });
    let target = null;
    let placeAfter = false;
    for (let i = 0; i < siblings.length; i++) {
      const rect = siblings[i].getBoundingClientRect();
      const mid = rect.left + rect.width / 2;
      if (e.clientX < mid) {
        target = siblings[i];
        placeAfter = false;
        break;
      }
      target = siblings[i];
      placeAfter = true;
    }
    if (!target) {
      return;
    }
    if (placeAfter) {
      if (target.nextSibling !== drag.btn) {
        target.after(drag.btn);
      }
    } else if (target.previousSibling !== drag.btn) {
      target.before(drag.btn);
    }
  }

  function suppressClick(btn) {
    const suppress = function (ev) {
      ev.preventDefault();
      ev.stopImmediatePropagation();
      btn.removeEventListener("click", suppress, true);
    };
    btn.addEventListener("click", suppress, true);
    setTimeout(function () {
      btn.removeEventListener("click", suppress, true);
    }, 0);
  }

  function onPointerUp() {
    if (!drag) {
      return;
    }
    if (drag.started) {
      drag.btn.classList.remove("mantella-tab-dragging");
      try {
        drag.btn.releasePointerCapture(drag.pointerId);
      } catch (err) {}
      saveOrder(buttonLabels(drag.nav));
      suppressClick(drag.btn);
    }
    drag = null;
  }

  function setup() {
    mainTabNavs().forEach(function (nav) {
      bindNav(nav);
      if (!drag) {
        applyOrder(nav);
      }
    });
  }

  function scheduleSetup() {
    if (applying || (drag && drag.started)) {
      return;
    }
    if (setupTimer) {
      clearTimeout(setupTimer);
    }
    setupTimer = setTimeout(setup, 50);
  }

  function mutationTouchesTabNav(mutations) {
    for (let i = 0; i < mutations.length; i++) {
      const mutation = mutations[i];
      if (mutation.target && mutation.target.classList && mutation.target.classList.contains("tab-nav")) {
        return true;
      }
      const lists = [mutation.addedNodes, mutation.removedNodes];
      for (let j = 0; j < lists.length; j++) {
        for (let k = 0; k < lists[j].length; k++) {
          const node = lists[j][k];
          if (!node) {
            continue;
          }
          if (node.classList && node.classList.contains("tab-nav")) {
            return true;
          }
          if (node.querySelector && node.querySelector(".tab-nav")) {
            return true;
          }
        }
      }
    }
    return false;
  }

  document.addEventListener("pointermove", onPointerMove, { passive: false });
  document.addEventListener("pointerup", onPointerUp);
  document.addEventListener("pointercancel", onPointerUp);

  const observer = new MutationObserver(function (mutations) {
    if (applying) {
      return;
    }
    if (!mutationTouchesTabNav(mutations)) {
      return;
    }
    scheduleSetup();
  });
  observer.observe(document.documentElement, { childList: true, subtree: true });

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", setup);
  } else {
    setup();
  }
})();
"""


def default_tab_names(base_groups) -> list[str]:
    names: list[str] = []
    for group in base_groups:
        if group.is_hidden:
            continue
        names.append(group.name)
        if group.name == PROMPT_PROFILES_TAB:
            names.append(LIVE_CONVERSATION_TAB)
    names.append(BIO_EDITOR_TAB)
    names.append(TAG_EDITOR_TAB)
    names.append(DOCUMENTATION_TAB)
    return names


def merge_tab_order(defaults: list[str], saved: list[str]) -> list[str]:
    """The saved order, with tabs it doesn't know (e.g. added by an update) placed right after the tab that comes
    before them by default, not at the end. Keep in sync with desiredOrder() in TAB_REORDER_JS"""
    default_set = set(defaults)
    ordered: list[str] = []
    for name in saved:
        if name in default_set and name not in ordered:
            ordered.append(name)
    for index, name in enumerate(defaults):
        if name in ordered:
            continue
        previous = next((defaults[i] for i in range(index - 1, -1, -1) if defaults[i] in ordered), None)
        ordered.insert(ordered.index(previous) + 1 if previous is not None else 0, name)
    return ordered


def tab_order_needs_apply(current: list[str], saved: list[str] | None) -> bool:
    if not saved:
        return False
    return merge_tab_order(current, saved) != list(current)
