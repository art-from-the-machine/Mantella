"""Colours the prompt text boxes like an IDE: the conditional blocks ({if shout} ... {else} ... {end if}), their conditions,
variables and shared sections. Mistakes in the blocks are underlined in red, the lines inside a block get a tinted band
for each level of nesting, and with the cursor on a tag its whole block ({if}, {else if}, {else}, {end if}) lights up.

How: a coloured copy of the text sits behind the text box, and the box's own text is made transparent (its cursor and
selection stay visible). Only the display changes: what is typed, saved and sent is the plain text. If the script fails,
the plain text box is left as it was.

The colours use only colour and backgrounds, never bold or other widths, so the copy lines up with the typed text.
Each box knows its prompt type (prompt_box_classes), so a condition that prompt doesn't know is underlined, and so is any tag
in a prompt without conditional blocks. A shared section can go into any prompt, so its box knows every condition"""
import json

from src.config.definitions.prompt_definitions import PromptDefinitions
from src.prompt_profile_manager import PromptProfileManager

# Text boxes with this class are coloured (the class goes on the Gradio component)
PROMPT_HIGHLIGHT_CLASS = "prompt-highlight"
# Then the box's prompt type: ph-type-<prompt type>, or this for a shared section's text
_TYPE_PREFIX = "ph-type-"
_SECTION_TYPE = "section"


def prompt_box_classes(prompt_type: str | None) -> list[str]:
    """The classes of a coloured prompt text box

    Args:
        prompt_type (str | None): the prompt it holds, for the conditions it may use. None for a shared section's text
    """
    return [PROMPT_HIGHLIGHT_CLASS, _TYPE_PREFIX + (prompt_type or _SECTION_TYPE)]


def highlight_data() -> dict:
    """The names the colouring knows: the conditions of each merged prompt, every condition (for a shared section), and
    the built-in variables (any other {name} is a shared section)"""
    conditions = sorted({condition for conditions in PromptDefinitions.PROMPT_CONDITIONS.values() for condition in conditions})
    return {"conditions": conditions,
            "prompt_conditions": {prompt_type: list(conditions) for prompt_type, conditions in PromptDefinitions.PROMPT_CONDITIONS.items()},
            "variables": sorted(PromptProfileManager.builtin_variables())}


_JS = r"""
(function () {
  if (window.__mantellaPromptHighlight) {
    return;
  }
  const DATA = __MANTELLA_PROMPT_HIGHLIGHT_DATA__;
  const ALL_CONDITIONS = new Set(DATA.conditions);
  const VARIABLES = new Set(DATA.variables);
  const TYPE_PREFIX = "__MANTELLA_PROMPT_HIGHLIGHT_TYPE_PREFIX__";
  const SECTION_TYPE = "__MANTELLA_PROMPT_HIGHLIGHT_SECTION_TYPE__";

  // The conditions a prompt type knows: its own for a merged prompt, none for any other prompt, all of them for a shared section
  function conditionsFor(promptType) {
    if (promptType === undefined || promptType === null || promptType === SECTION_TYPE) {
      return ALL_CONDITIONS;
    }
    return new Set(DATA.prompt_conditions[promptType] || []);
  }
  // The same tags as TAG_RE and _NEAR_MISS_RE in src/prompt_conditions.py
  const TAG_RE = /^\{[ \t]*(?:(if|else[ \t]+if)[ \t]+([^{}]*?)|(else)|(end[ \t]+if))[ \t]*\}$/;
  const NEAR_MISS_RE = /^\{[ \t]*(end[ \t]*if|end|fi|elif|else[ \t]*if|else|if)(?![A-Za-z0-9_])[^{}]*\}$/i;
  const NAME_RE = /^\{([A-Za-z_][A-Za-z0-9_]*)\}$/;
  const BRACES_RE = /\{[^{}\n]*\}/g;
  const WORD_RE = /([A-Za-z_][A-Za-z0-9_]*)/;

  function escapeHtml(text) {
    return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }

  // Whether a condition can be read: names joined by 'and' / 'or', each optionally after 'not' (as _evaluate in prompt_conditions.py)
  function isReadableCondition(expression, conditions) {
    if (/[()]/.test(expression)) {
      return false;
    }
    const words = expression.split(/\s+/).filter(Boolean);
    if (!words.length) {
      return false;
    }
    let expectName = true;
    for (const word of words) {
      const lowered = word.toLowerCase();
      if (expectName) {
        if (lowered === "not") {
          continue;
        }
        if (lowered === "and" || lowered === "or" || !conditions.has(lowered)) {
          return false;
        }
        expectName = false;
      } else if (lowered === "and" || lowered === "or") {
        expectName = true;
      } else {
        return false;
      }
    }
    return !expectName;
  }

  // The tags, variables and sections of the text, in order. Each tag has its block ('group') and whether it is a mistake.
  // promptType: which prompt the text is, for the conditions it may use (see conditionsFor)
  function analyze(text, promptType) {
    const conditions = conditionsFor(promptType);
    const tagsAllowed = conditions.size > 0; // A prompt without conditional blocks takes no tag at all
    const tokens = [];
    BRACES_RE.lastIndex = 0;
    let match;
    while ((match = BRACES_RE.exec(text)) !== null) {
      const raw = match[0];
      const start = match.index;
      const end = start + raw.length;
      const tag = TAG_RE.exec(raw);
      if (tag) {
        const kind = tag[4] ? "end" : tag[3] ? "else" : (tag[1] === "if" ? "if" : "elseif");
        const error = !tagsAllowed || ((kind === "if" || kind === "elseif") && !isReadableCondition(tag[2] || "", conditions));
        tokens.push({ type: "tag", kind: kind, start: start, end: end, raw: raw, error: error, group: null, conditions: conditions });
      } else if (NEAR_MISS_RE.test(raw)) {
        tokens.push({ type: "tag", kind: "typo", start: start, end: end, raw: raw, error: true, group: null });
      } else {
        const name = NAME_RE.exec(raw);
        if (name) {
          tokens.push({ type: VARIABLES.has(name[1]) ? "variable" : "section", start: start, end: end, raw: raw });
        }
      }
    }
    const open = [];
    let nextGroup = 0;
    for (const token of tokens) {
      if (token.type !== "tag" || token.kind === "typo") {
        continue;
      }
      if (token.kind === "if") {
        token.group = nextGroup++;
        open.push({ group: token.group, hasElse: false, opening: token });
        continue;
      }
      const block = open[open.length - 1];
      if (!block) {
        token.error = true; // No {if} before it
        continue;
      }
      token.group = block.group;
      if (token.kind === "elseif") {
        token.error = token.error || block.hasElse; // After the {else}
      } else if (token.kind === "else") {
        token.error = token.error || block.hasElse; // A second {else}
        block.hasElse = true;
      } else {
        open.pop();
      }
    }
    for (const block of open) {
      block.opening.error = true; // No matching {end if}
    }
    return tokens;
  }

  function tokenHtml(token, matchGroup) {
    if (token.type === "variable") {
      return '<span class="ph-variable">' + escapeHtml(token.raw) + "</span>";
    }
    if (token.type === "section") {
      return '<span class="ph-section">' + escapeHtml(token.raw) + "</span>";
    }
    let classes = "ph-tag";
    if (token.error) {
      classes += " ph-error";
    }
    if (matchGroup !== null && token.group === matchGroup) {
      classes += " ph-match";
    }
    const parts = token.raw.split(WORD_RE);
    const html = parts.map(function (part, index) {
      if (index % 2 === 0) {
        return escapeHtml(part);
      }
      const lowered = part.toLowerCase();
      if (token.kind === "typo") {
        return escapeHtml(part);
      }
      if (lowered === "if" || lowered === "else" || lowered === "end") {
        return '<span class="ph-keyword">' + escapeHtml(part) + "</span>";
      }
      if (lowered === "and" || lowered === "or" || lowered === "not") {
        return '<span class="ph-operator">' + escapeHtml(part) + "</span>";
      }
      return '<span class="ph-condition' + (token.conditions.has(lowered) ? "" : " ph-unknown") + '">' + escapeHtml(part) + "</span>";
    }).join("");
    return '<span class="' + classes + '">' + html + "</span>";
  }

  // The coloured copy: one line per line of the text, with the nesting depth of the blocks it is in.
  // caret: where the cursor is, to light up the block of the tag it is on (null for none). promptType: as for analyze
  function render(text, caret, promptType) {
    const tokens = analyze(text, promptType);
    let matchGroup = null;
    if (caret !== null && caret !== undefined) {
      for (const token of tokens) {
        if (token.type === "tag" && token.group !== null && caret >= token.start && caret <= token.end) {
          matchGroup = token.group;
          break;
        }
      }
    }
    const lines = text.split("\n");
    const html = [];
    let offset = 0;
    let index = 0;
    let depth = 0;
    for (const line of lines) {
      const lineEnd = offset + line.length;
      let content = "";
      let position = offset;
      let deepest = depth;
      while (index < tokens.length && tokens[index].start < lineEnd) {
        const token = tokens[index++];
        content += escapeHtml(text.slice(position, token.start)) + tokenHtml(token, matchGroup);
        position = token.end;
        if (token.type === "tag" && token.group !== null) {
          if (token.kind === "if") {
            depth++;
          } else if (token.kind === "end") {
            depth--;
          }
          deepest = Math.max(deepest, depth);
        }
      }
      content += escapeHtml(text.slice(position, lineEnd));
      const band = deepest > 0 ? " ph-depth-" + (((deepest - 1) % 4) + 1) : "";
      html.push('<div class="ph-line' + band + '">' + (content || "​") + "</div>");
      offset = lineEnd + 1;
    }
    return html.join("");
  }

  // The page part below draws through this object, so a test can make drawing fail and see the box go back to plain text
  const api = { analyze: analyze, render: render };
  window.__mantellaPromptHighlight = api;
  if (typeof document === "undefined") {
    return;
  }

  const COPIED_STYLES = ["fontFamily", "fontSize", "fontWeight", "fontStyle", "fontVariant", "fontStretch", "letterSpacing", "wordSpacing",
    "lineHeight", "textTransform", "textIndent", "tabSize", "textAlign", "direction", "whiteSpace", "overflowWrap", "wordBreak",
    "paddingTop", "paddingBottom", "paddingLeft", "borderTopWidth", "borderRightWidth", "borderBottomWidth", "borderLeftWidth",
    "borderTopLeftRadius", "borderTopRightRadius", "borderBottomLeftRadius", "borderBottomRightRadius"];
  const states = [];
  // What the colouring needs to work, set on the elements themselves: it works the same if style.css didn't load
  const BACKDROP_STYLES = { position: "absolute", overflow: "hidden", pointerEvents: "none", zIndex: "0", boxSizing: "border-box", margin: "0" };
  const HIDDEN_TEXT_STYLES = [["background", "transparent"], ["color", "transparent"], ["-webkit-text-fill-color", "transparent"]];

  // The prompt type of a box, from its ph-type-<prompt type> class. The profile editor changes it with the chosen prompt type
  function promptTypeOf(textarea) {
    const box = textarea.closest(".__MANTELLA_PROMPT_HIGHLIGHT_CLASS__");
    const typeClass = box ? Array.prototype.find.call(box.classList, function (name) { return name.indexOf(TYPE_PREFIX) === 0; }) : null;
    return typeClass ? typeClass.slice(TYPE_PREFIX.length) : SECTION_TYPE;
  }

  function attach(textarea) {
    if (textarea.__mantellaHighlight) {
      return; // Also a box whose colouring failed: it stays plain
    }
    const parent = textarea.parentElement;
    if (!parent) {
      return;
    }
    const style = getComputedStyle(textarea);
    const backdrop = document.createElement("div");
    backdrop.className = "ph-backdrop";
    backdrop.setAttribute("aria-hidden", "true");
    Object.keys(BACKDROP_STYLES).forEach(function (name) { backdrop.style[name] = BACKDROP_STYLES[name]; });
    backdrop.style.backgroundColor = style.backgroundColor;
    backdrop.style.color = style.color;
    const content = document.createElement("div");
    content.className = "ph-content";
    content.style.whiteSpace = "pre-wrap";
    content.style.overflowWrap = "break-word";
    backdrop.appendChild(content);
    const state = { textarea: textarea, backdrop: backdrop, content: content, key: null, sizeKey: null, parentPosition: null, failed: false };
    textarea.__mantellaHighlight = state;
    try {
      // Drawn once before the box's own text is hidden: if this fails, the box is left exactly as it was
      content.innerHTML = api.render(textarea.value, null, promptTypeOf(textarea));
    } catch (error) {
      fail(state, error);
      return;
    }
    if (getComputedStyle(parent).position === "static") {
      state.parentPosition = parent.style.position;
      parent.style.position = "relative";
    }
    parent.insertBefore(backdrop, textarea);
    textarea.classList.add("ph-textarea");
    HIDDEN_TEXT_STYLES.forEach(function (pair) { textarea.style.setProperty(pair[0], pair[1], "important"); });
    textarea.style.position = "relative";
    textarea.style.zIndex = "1";
    textarea.style.caretColor = style.color;
    states.push(state);
    const refresh = function () { update(state); };
    ["input", "keyup", "click", "select", "focus", "blur"].forEach(function (name) { textarea.addEventListener(name, refresh); });
    textarea.addEventListener("input", function () { requestAnimationFrame(refresh); }); // After Gradio resizes the box
    textarea.addEventListener("scroll", function () { scroll(state); });
    update(state);
  }

  // Back to the plain text box for good, so a failure never leaves the text hidden
  function fail(state, error) {
    const textarea = state.textarea;
    state.failed = true;
    state.backdrop.remove();
    textarea.classList.remove("ph-textarea");
    HIDDEN_TEXT_STYLES.forEach(function (pair) { textarea.style.removeProperty(pair[0]); });
    ["position", "z-index", "caret-color"].forEach(function (name) { textarea.style.removeProperty(name); });
    if (state.parentPosition !== null && textarea.parentElement) {
      textarea.parentElement.style.position = state.parentPosition;
    }
    if (window.console) {
      console.warn("Mantella: prompt colouring turned off for this text box.", error);
    }
  }

  function layout(state) {
    const textarea = state.textarea;
    const sizeKey = [textarea.offsetWidth, textarea.offsetHeight, textarea.clientWidth, textarea.offsetTop, textarea.offsetLeft].join(",");
    if (sizeKey === state.sizeKey) {
      return;
    }
    state.sizeKey = sizeKey;
    const style = getComputedStyle(textarea);
    const backdrop = state.backdrop.style;
    COPIED_STYLES.forEach(function (name) { backdrop[name] = style[name]; });
    backdrop.borderStyle = "solid";
    backdrop.borderColor = "transparent";
    // The text box's scroll bar takes width from its text: the copy leaves the same room, so its lines wrap at the same words
    const scrollBar = textarea.offsetWidth - textarea.clientWidth - parseFloat(style.borderLeftWidth) - parseFloat(style.borderRightWidth);
    backdrop.paddingRight = (parseFloat(style.paddingRight) + Math.max(0, scrollBar)) + "px";
    backdrop.top = textarea.offsetTop + "px";
    backdrop.left = textarea.offsetLeft + "px";
    backdrop.width = textarea.offsetWidth + "px";
    backdrop.height = textarea.offsetHeight + "px";
  }

  function scroll(state) {
    state.content.style.transform = "translateY(" + (-state.textarea.scrollTop) + "px)";
  }

  // False once the text box is gone from the page, or its colouring failed
  function update(state) {
    if (state.failed) {
      return false;
    }
    const textarea = state.textarea;
    if (!textarea.isConnected) {
      state.backdrop.remove();
      return false;
    }
    if (textarea.offsetParent === null) {
      return true; // On a tab that isn't shown
    }
    try {
      const editing = document.activeElement === textarea && textarea.selectionStart === textarea.selectionEnd;
      const caret = editing ? textarea.selectionStart : null;
      const promptType = promptTypeOf(textarea);
      const key = promptType + "\u0000" + caret + "\u0000" + textarea.value;
      if (key !== state.key) {
        state.key = key;
        state.content.innerHTML = api.render(textarea.value, caret, promptType);
      }
      layout(state);
      scroll(state);
    } catch (error) {
      fail(state, error);
      return false;
    }
    return true;
  }

  function scan() {
    document.querySelectorAll(".__MANTELLA_PROMPT_HIGHLIGHT_CLASS__ textarea").forEach(attach);
    for (let i = states.length - 1; i >= 0; i--) {
      if (!update(states[i])) {
        states.splice(i, 1);
      }
    }
  }

  // Gradio sets the text without an input event (loading a profile), and boxes appear as tabs open: checked a few times a second
  setInterval(scan, 250);
  document.addEventListener("selectionchange", function () {
    const state = document.activeElement && document.activeElement.__mantellaHighlight;
    if (state) {
      update(state);
    }
  });
  if (document.fonts && document.fonts.ready) {
    document.fonts.ready.then(function () { states.forEach(function (state) { state.sizeKey = null; }); });
  }
})();
"""

# Added to the page's scripts in start_ui.py
PROMPT_HIGHLIGHT_JS = (_JS.replace("__MANTELLA_PROMPT_HIGHLIGHT_DATA__", json.dumps(highlight_data()))
                       .replace("__MANTELLA_PROMPT_HIGHLIGHT_CLASS__", PROMPT_HIGHLIGHT_CLASS)
                       .replace("__MANTELLA_PROMPT_HIGHLIGHT_TYPE_PREFIX__", _TYPE_PREFIX)
                       .replace("__MANTELLA_PROMPT_HIGHLIGHT_SECTION_TYPE__", _SECTION_TYPE))
