"""Tidies the in-game events of one player message before they are sent to the LLM.

A fight with a big party produces dozens of lines that differ only by who was affected ('Yulia hit Gorr with MassHealing',
'Yulia hit Kak with MassHealing', ...). tidy_events merges those into one line each and drops repeats, without losing who did what.
The sentences matched here are the ones written by MantellaListenerScript.psc and MantellaTargetListenerScript.psc in Mantella-Spell,
plus the combat notices of context.py. Any other event is passed on as it is.
"""
import re

# Kinds of events that can be merged. The combat kinds describe a state, so their order per person has to be kept
_HIT = "hit"
_USED = "used"
_PUNCHED = "punched"
_CAST = "cast"
_ENTERED_COMBAT = "entered_combat"
_NOW_IN_COMBAT = "now_in_combat"
_LEFT_COMBAT = "left_combat"
_SEARCHING = "searching"
_COMBAT_KINDS = (_ENTERED_COMBAT, _NOW_IN_COMBAT, _LEFT_COMBAT, _SEARCHING)

_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (_HIT, re.compile(r"^(?P<who>.+?) hit (?P<member>.+?) with (?P<what>.+)$")),
    (_USED, re.compile(r"^(?P<who>.+?) used (?P<what>.+) on (?P<member>.+)$")),
    (_PUNCHED, re.compile(r"^(?P<who>.+?) punched (?P<member>.+?)\s*\.?$")),
    (_CAST, re.compile(r"^(?P<who>.+?) casted the spell (?P<what>/ consumed )?(?P<member>.+)$")),
    (_ENTERED_COMBAT, re.compile(r"^(?P<member>.+?) has entered combat with (?P<what>.+)$")),
    (_NOW_IN_COMBAT, re.compile(r"^(?P<member>.+?) is now in combat!$")),
    (_LEFT_COMBAT, re.compile(r"^(?P<member>.+?) is no longer in combat\.?$")),
    (_SEARCHING, re.compile(r"^(?P<member>.+?) is searching for (?P<what>.+)$")),
]


class _Group:
    """Events of one kind that only differ by one name (the member), e.g. everyone hit by the same spell of the same caster"""
    def __init__(self, kind: str, who: str, what: str):
        self.kind = kind
        self.who = who
        self.what = what
        self.members: dict[str, str] = {} # Member name -> the event as it came in, in the order they were first seen

    def text(self) -> str | None:
        if not self.members:
            return None
        if len(self.members) == 1:
            return next(iter(self.members.values()))
        names = _join_names(list(self.members))
        if self.kind == _HIT:
            return f"{self.who} hit {names} with {self.what}"
        if self.kind == _USED:
            return f"{self.who} used {self.what} on {names}"
        if self.kind == _PUNCHED:
            return f"{self.who} punched {names}"
        if self.kind == _CAST:
            return f"{self.who} casted the spells {self.what}{names}"
        if self.kind == _ENTERED_COMBAT:
            return f"{names} have entered combat with {self.what}"
        if self.kind == _NOW_IN_COMBAT:
            return f"{names} are now in combat!"
        if self.kind == _LEFT_COMBAT:
            return f"{names} are no longer in combat."
        return f"{names} are searching for {self.what}"


def _join_names(names: list[str]) -> str:
    return ", ".join(names[:-1]) + " and " + names[-1]


def tidy_events(events: list[str]) -> list[str]:
    """Merges events that only differ by who was affected, and drops repeats.

    - 'A hit B with X' + 'A hit C with X' -> 'A hit B and C with X'. Same for 'used X on', 'punched' and the combat notices
    - Several spells cast by the same person become one line
    - 'A casted the spell X' is dropped when the same events already say who A hit with X
    - A merged line stands where its first event stood. Events that are not recognised keep their place and text

    Args:
        events (list[str]): the events since the previous player message, oldest first

    Returns:
        list[str]: the tidied events, oldest first
    """
    lines: list[str | _Group] = []
    open_groups: dict[tuple[str, str, str], int] = {} # The group new events of the same kind are merged into -> its index in lines
    last_combat_line: dict[str, int] = {} # Person -> index in lines of the latest combat notice about them

    for event in events:
        if not isinstance(event, str):
            lines.append(event)
            continue
        event = event.strip()
        if not event:
            continue

        parsed = _parse(event)
        if not parsed:
            if not (lines and lines[-1] == event): # The same line twice in a row says nothing new
                lines.append(event)
            continue

        kind, who, what, member = parsed
        key = (kind, who, what)
        index = open_groups.get(key)
        # 'A left combat' may stand between 'A, B entered combat' and a later 'A entered combat'. Then the later one can't be
        # merged into the earlier line, or the events would end with A out of combat
        if index is not None and kind in _COMBAT_KINDS and last_combat_line.get(member, -1) > index:
            index = None
        if index is None:
            lines.append(_Group(kind, who, what))
            index = len(lines) - 1
            open_groups[key] = index
        group: _Group = lines[index] # type: ignore[assignment]
        group.members.setdefault(member, event)
        if kind in _COMBAT_KINDS:
            last_combat_line[member] = index

    _drop_casts_covered_by_hits(lines)

    result: list[str] = []
    for line in lines:
        text = line.text() if isinstance(line, _Group) else line
        if text:
            result.append(text)
    return result


def _parse(event: str) -> tuple[str, str, str, str] | None:
    """Returns the kind of the event, who did it, what with, and the name that differs between events that can be merged"""
    if " rested on / used " in event: # Sitting down, not a spell used on someone
        return None
    for kind, pattern in _PATTERNS:
        match = pattern.match(event)
        if match:
            parts = match.groupdict()
            return kind, parts.get("who") or "", parts.get("what") or "", parts["member"]
    return None


def _drop_casts_covered_by_hits(lines: list):
    """'A casted the spell X' adds nothing when another line says who A hit with X (or used X on)"""
    hits: set[tuple[str, str]] = set()
    for line in lines:
        if isinstance(line, _Group) and line.kind in (_HIT, _USED):
            hits.add((line.who.lower(), line.what.lower()))
    for line in lines:
        if isinstance(line, _Group) and line.kind == _CAST:
            for spell in list(line.members):
                if (line.who.lower(), spell.lower()) in hits:
                    del line.members[spell]
