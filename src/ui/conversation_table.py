"""Readable table view of the live conversation JSON.

Each row is one line of the conversation: a player message, one NPC sentence
(speech, narration or thought), or an NPC joining/leaving. Only the Text column
is written back; everything else stays as it is in the JSON.
"""
import json

HEADERS = ["#", "Who", "Kind", "Text"]

TABLE_ELEM_ID = "live-conversation-table"
DELETE_BUTTON_ELEM_ID = "live-delete-selected"

# Fixes for Gradio 4.28's table, for the live conversation table only:
# - It starts editing a selected cell on any one-character key, even with Ctrl held, and clears it first.
#   So Ctrl+C would wipe the cell. Copy the selected cell's text instead.
# - It edits a cell in a one-line <input> laid over it, so long text no longer wraps. Edit in a textarea laid over
#   the input instead. Each change is passed on to the input, so Gradio saves the value as usual.
# - Clicking a row's # selects it for deletion. The selection is kept here, not in the table, as a trip to the server
#   on each click makes the table flash. Clicking outside the table clears it.
TABLE_JS = r"""
(function () {
  if (window.__mantellaTableInit) {
    return;
  }
  window.__mantellaTableInit = true;
  const TABLE_ID = "%s";
  const DELETE_BUTTON_ID = "%s";
  let editor = null; // {input, textarea} of the cell being edited in a textarea
  const closingInputs = new WeakSet(); // Inputs given the focus back to end the edit, which must not get a textarea again
  const selectedRows = new Set(); // The # of each row selected for deletion

  function inTable(element) {
    const table = document.getElementById(TABLE_ID);
    return !!(table && element && table.contains(element));
  }

  document.addEventListener("keydown", function (event) {
    if (!(event.ctrlKey || event.metaKey) || (event.key || "").toLowerCase() !== "c") {
      return;
    }
    const target = event.target;
    if (target && (target.tagName === "INPUT" || target.tagName === "TEXTAREA")) {
      return; // The cell is being edited: the browser copies the selected text
    }
    if (!inTable(target)) {
      return;
    }
    if (window.getSelection && window.getSelection().toString()) {
      return; // Text selected with the mouse: the browser copies it
    }
    const cell = document.getElementById(TABLE_ID).querySelector("td.focus");
    if (!cell) {
      return;
    }
    event.preventDefault();
    event.stopPropagation();
    navigator.clipboard.writeText((cell.innerText || "").trim());
  }, true);

  function editInTextarea(input) {
    const textarea = document.createElement("textarea");
    textarea.className = "mantella-cell-editor";
    // Replies often start with a space. The cell hides it, so the textarea does too, or the text would shift right
    textarea.value = input.value.trim();
    input.parentNode.insertBefore(textarea, input.nextSibling);
    editor = {input: input, textarea: textarea};
    textarea.focus();
    textarea.setSelectionRange(textarea.value.length, textarea.value.length);
    input.style.opacity = "0";
    textarea.addEventListener("input", function () {
      input.value = textarea.value;
      input.dispatchEvent(new Event("input", {bubbles: true}));
    });
    textarea.addEventListener("keydown", function (event) {
      if (event.key === "Enter") {
        event.preventDefault(); // No line breaks, as in Gradio's input
      }
      if ((event.key === "Enter" && !event.shiftKey) || event.key === "Tab" || event.key === "Escape") {
        // Gradio ends the edit on these keys by removing the input, and saves the value as the removed input loses focus.
        // So the input needs the focus back before the key reaches Gradio
        closingInputs.add(input);
        input.focus();
      }
    });
    textarea.addEventListener("blur", function () {
      if (editor && editor.textarea === textarea) {
        editor = null;
      }
      textarea.remove();
      const isClosedByKey = closingInputs.has(input);
      closingInputs.add(input); // Gradio may focus the input once more as the edit ends
      if (!isClosedByKey && input.isConnected) {
        input.dispatchEvent(new FocusEvent("blur")); // Gradio saves the value and ends the edit when the input loses focus
      }
    });
  }

  document.addEventListener("focusin", function (event) {
    const input = event.target;
    if (!input || input.tagName !== "INPUT" || closingInputs.has(input) || !input.closest("td") || !inTable(input)) {
      return;
    }
    // After Gradio has set up the input, which may clear it, but before the browser shows the one-line input
    queueMicrotask(function () {
      if (input.isConnected && document.activeElement === input) {
        editInTextarea(input);
      }
    });
  }, true);

  function rowNumber(row) {
    const cell = row.querySelector("td");
    return cell ? (cell.innerText || "").trim() : "";
  }

  function showSelection() {
    const table = document.getElementById(TABLE_ID);
    if (!table) {
      return;
    }
    table.querySelectorAll("tbody tr").forEach(function (row) {
      row.classList.toggle("mantella-row-selected", selectedRows.has(rowNumber(row)));
    });
  }

  function clearSelection() {
    if (selectedRows.size) {
      selectedRows.clear();
      showSelection();
    }
  }

  // Called by the Delete selected button. The row numbers change after a deletion, so the selection is cleared
  window.__mantellaTakeSelectedRows = function () {
    const rows = Array.from(selectedRows);
    clearSelection();
    return JSON.stringify(rows);
  };

  document.addEventListener("click", function (event) {
    const target = event.target;
    if (inTable(target)) {
      const cell = target.closest && target.closest("td");
      if (cell && cell.parentElement.firstElementChild === cell) {
        const number = rowNumber(cell.parentElement);
        if (selectedRows.has(number)) {
          selectedRows.delete(number);
        } else if (number) {
          selectedRows.add(number);
        }
        showSelection();
      }
      return;
    }
    if (!(target.closest && target.closest("#" + DELETE_BUTTON_ID))) {
      clearSelection();
    }
  });

  new MutationObserver(function () {
    // Gradio can end an edit by removing the input without it losing focus
    if (editor && !editor.input.isConnected) {
      editor.textarea.remove();
      editor = null;
    }
    // Gradio reuses the rows while scrolling, so the highlight follows the row numbers
    if (selectedRows.size) {
      showSelection();
    }
  }).observe(document.documentElement, {childList: true, subtree: true, characterData: true});

  // Moving the focus to the textarea would end the edit, as Gradio ends it when the input loses focus
  document.addEventListener("blur", function (event) {
    if (editor && event.target === editor.input && event.relatedTarget === editor.textarea) {
      event.stopPropagation();
    }
  }, true);
})();
""" % (TABLE_ELEM_ID, DELETE_BUTTON_ELEM_ID)

_SENTENCE_KINDS = {
    "SPEECH": "Speech",
    "NARRATION": "Narration",
    "THOUGHT": "💭 Thought",
}


def _user_kind(item: dict) -> str:
    if item.get("is_director"):
        return "Director"
    if item.get("is_system_generated"):
        return "System"
    return "Player"


def _rows_with_targets(messages: list) -> list[tuple[list[str], dict]]:
    """Pairs each table row with the JSON dict holding its text."""
    result = []
    for i, item in enumerate(messages, start=1):
        msg_type = item.get("type")
        if msg_type == "user":
            who = item.get("player_character_name") or "Player"
            result.append(([str(i), who, _user_kind(item), item.get("text", "")], item))
        elif msg_type == "assistant":
            for j, sentence in enumerate(item.get("sentences", []), start=1):
                kind = _SENTENCE_KINDS.get(str(sentence.get("sentence_type", "SPEECH")).upper(), "Speech")
                result.append(([f"{i}.{j}", sentence.get("speaker_name", ""), kind, sentence.get("text", "")], sentence))
        elif msg_type in ("join", "leave"):
            who = item.get("character", {}).get("name", "")
            kind = "Joined" if msg_type == "join" else "Left"
            result.append(([str(i), who, kind, item.get("content", "")], item))
    return result


def _text_key(target: dict) -> str:
    return "content" if target.get("type") in ("join", "leave") else "text"


def json_to_rows(json_str: str) -> list[list[str]]:
    """Builds the table rows from conversation JSON. Empty input gives no rows."""
    if not json_str or not json_str.strip():
        return []
    return [row for row, _ in _rows_with_targets(json.loads(json_str))]


def _load_with_targets(json_str: str, rows: list[list]) -> tuple[list, list[tuple[list, dict]]]:
    """Parses the JSON and pairs each table row with the JSON dict holding its text.

    Raises ValueError if rows were added, removed or reordered, since the table
    only supports editing text and deleting rows.
    """
    try:
        messages = json.loads(json_str)
    except json.JSONDecodeError as e:
        raise ValueError(f"Raw JSON is invalid: {e}") from e
    rows = [row for row in rows if any(str(cell).strip() for cell in row)]
    pairs = _rows_with_targets(messages)
    if [str(row[0]) for row in rows] != [row[0] for row, _ in pairs]:
        raise ValueError("Rows were added, removed or reordered. Only the Text column can be edited here; click Reload to start over.")
    return messages, [(row, target) for row, (_, target) in zip(rows, pairs)]


def apply_rows_to_json(json_str: str, rows: list[list]) -> str:
    """Writes the Text column of the edited rows back into the conversation JSON.

    Raises ValueError if rows were added, removed or reordered.
    """
    messages, pairs = _load_with_targets(json_str, rows)
    for row, target in pairs:
        target[_text_key(target)] = str(row[3])
    return json.dumps(messages, indent=2, ensure_ascii=False)


def delete_selected_rows(json_str: str, rows: list[list], selected_numbers: list[str]) -> str:
    """Writes the Text column back, then removes the rows with the selected # from the conversation JSON.

    An NPC message whose sentences are all deleted is removed. NPC messages left
    next to each other by a deletion are merged, as the conversation never holds two in a row.

    Raises:
        ValueError: if rows were added, removed or reordered, or a Joined/Left row is selected
    """
    messages, pairs = _load_with_targets(json_str, rows)
    for row, target in pairs:
        target[_text_key(target)] = str(row[3])
    selected = [target for row, target in pairs if str(row[0]) in selected_numbers]
    if any(target.get("type") in ("join", "leave") for target in selected):
        raise ValueError("Joined and Left rows can't be deleted: they tell the conversation who is in it.")
    selected_ids = {id(target) for target in selected}
    kept: list[dict] = []
    removed_since_last_kept = False
    for item in messages:
        if id(item) in selected_ids:
            removed_since_last_kept = True
            continue
        if item.get("type") == "assistant":
            sentences = item.get("sentences", [])
            remaining = [sentence for sentence in sentences if id(sentence) not in selected_ids]
            if len(remaining) < len(sentences):
                item["sentences"] = remaining
                if not remaining:
                    removed_since_last_kept = True
                    continue
            if removed_since_last_kept and kept and kept[-1].get("type") == "assistant":
                kept[-1]["sentences"].extend(item["sentences"])
                continue
        kept.append(item)
        removed_since_last_kept = False
    return json.dumps(kept, indent=2, ensure_ascii=False)
