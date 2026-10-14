"""Path helpers for Bio Editor summary, private-thought, personal-reflection, and note files.

Mirrors the on-disk layout used at runtime:
``{save_folder}/data/{game}/{conversations|thoughts|reflections|notes}/{world_id}/{Name}[- {ref_id}]/{Name}_{kind}_{N}.txt``

Notes are user-only and never read by the runtime.
"""
import os
import re

_TS_MARKER_RE = re.compile(r"^ts=(\d+)$")


def ensure_dash_prefix(text: str) -> str:
    """Prefix a thought/summary body with ``- `` when it does not already have one."""
    stripped = (text or "").strip()
    if not stripped:
        return ""
    if stripped.startswith("-"):
        return stripped
    return "- " + stripped


def ensure_thought_dash_prefixes(raw: str) -> str:
    """Ensure each thought block in a file starts with ``- ``, keeping ``ts=`` markers."""
    if not (raw or "").strip():
        return raw or ""

    blocks: list[list[str]] = []
    current: list[str] = []
    for line in raw.split("\n"):
        stripped = line.strip()
        if stripped == "":
            if current:
                blocks.append(current)
                current = []
            continue
        if _TS_MARKER_RE.match(stripped) and current:
            blocks.append(current)
            current = []
        current.append(stripped)
    if current:
        blocks.append(current)

    rendered: list[str] = []
    for block in blocks:
        if _TS_MARKER_RE.match(block[0]):
            body = "\n".join(block[1:]).strip()
            if body:
                rendered.append(block[0] + "\n" + ensure_dash_prefix(body))
            else:
                rendered.append(block[0])
        else:
            rendered.append(ensure_dash_prefix("\n".join(block)))
    return "\n\n".join(rendered)


def conversations_base_dir(save_folder: str, game_folder: str) -> str:
    return os.path.join(save_folder, "data", game_folder, "conversations")


def thoughts_base_dir(save_folder: str, game_folder: str) -> str:
    return os.path.join(save_folder, "data", game_folder, "thoughts")


def reflections_base_dir(save_folder: str, game_folder: str) -> str:
    return os.path.join(save_folder, "data", game_folder, "reflections")


def notes_base_dir(save_folder: str, game_folder: str) -> str:
    return os.path.join(save_folder, "data", game_folder, "notes")


def pick_world_id(base_dir: str) -> str:
    """Prefer ``default``, otherwise the most recently modified world folder."""
    try:
        if not os.path.isdir(base_dir):
            return "default"
        world_ids = [d for d in os.listdir(base_dir) if os.path.isdir(os.path.join(base_dir, d))]
        if not world_ids:
            return "default"
        if "default" in world_ids:
            return "default"
        world_ids_sorted = sorted(
            world_ids,
            key=lambda d: os.path.getmtime(os.path.join(base_dir, d)),
            reverse=True,
        )
        return world_ids_sorted[0]
    except Exception:
        return "default"


def find_npc_folder(base_dir: str, world_id: str, base_name: str) -> str | None:
    """Return the newest ``Name`` or ``Name - ref`` folder under *world_id*."""
    try:
        world_path = os.path.join(base_dir, world_id)
        if not os.path.isdir(world_path):
            return None
        candidates: list[tuple[float, str]] = []
        for entry in os.listdir(world_path):
            entry_path = os.path.join(world_path, entry)
            if not os.path.isdir(entry_path):
                continue
            if entry == base_name or entry.startswith(f"{base_name} - "):
                try:
                    candidates.append((os.path.getmtime(entry_path), entry_path))
                except Exception:
                    continue
        if not candidates:
            return None
        candidates.sort(key=lambda item: item[0], reverse=True)
        return candidates[0][1]
    except Exception:
        return None


def latest_numbered_file(folder_path: str, base_name: str, kind: str) -> tuple[str | None, int]:
    """Return ``(path, n)`` for the highest ``{base_name}_{kind}_{n}.txt`` file."""
    try:
        if not folder_path or not os.path.isdir(folder_path):
            return None, 1
        prefix = f"{base_name}_{kind}_"
        max_n = 0
        for filename in os.listdir(folder_path):
            if not filename.endswith(".txt") or not filename.startswith(prefix):
                continue
            try:
                n = int(os.path.splitext(filename)[0].split("_")[-1])
                if n > max_n:
                    max_n = n
            except Exception:
                continue
        if max_n == 0:
            return None, 1
        return os.path.join(folder_path, f"{base_name}_{kind}_{max_n}.txt"), max_n
    except Exception:
        return None, 1


def load_latest_text(base_dir: str, world_id: str, base_name: str, kind: str) -> str:
    """Read the latest numbered file as raw text (no thought wrappers)."""
    try:
        folder = find_npc_folder(base_dir, world_id, base_name)
        if not folder:
            return ""
        latest_path, _ = latest_numbered_file(folder, base_name, kind)
        if latest_path and os.path.exists(latest_path):
            with open(latest_path, "r", encoding="utf-8") as handle:
                return handle.read().strip()
        return ""
    except Exception:
        return ""


def save_latest_text(base_dir: str, world_id: str, base_name: str, kind: str, text: str) -> str:
    """Write raw text to the latest numbered file, creating a name-only folder if needed.

    Returns the saved path with forward slashes, or ``""`` on failure.
    """
    try:
        world_path = os.path.join(base_dir, world_id)
        os.makedirs(world_path, exist_ok=True)
        folder = find_npc_folder(base_dir, world_id, base_name)
        if not folder:
            folder = os.path.join(world_path, base_name)
        os.makedirs(folder, exist_ok=True)
        latest_path, n = latest_numbered_file(folder, base_name, kind)
        target_path = latest_path or os.path.join(folder, f"{base_name}_{kind}_{n}.txt")
        if kind == "thoughts":
            text = ensure_thought_dash_prefixes(text)
        content = (text or "").rstrip() + "\n"
        with open(target_path, "w", encoding="utf-8") as handle:
            handle.write(content)
        return target_path.replace("\\", "/")
    except Exception:
        return ""
