"""Reads the `code_N` conditions of bio template tags and evaluates them against answers from the game.

A condition is written like a Skyrim console command, e.g. ``getstagedone CWObj 100=1 AND "0D7505".getdead=1``.
Each function call in a condition becomes a check: one question the game answers with a plain number.
The game only answers checks; comparing, combining and picking each tag's outcome happens here.
See docs/quest_tags_1_user_edits.md, Parts 4 and 5.
"""
import hashlib
import json
import logging
import re
from dataclasses import dataclass, field
from typing import Union

import pandas as pd

# Reserved answers. Integers this small are exact in Papyrus' 32-bit floats
ANSWER_MISSING = -9999901.0     # What the check is about doesn't exist in this game: not true
ANSWER_NOT_LOADED = -9999902.0  # Exists, but isn't in memory right now (e.g. an NPC far away): unknown

PLAYER = "player"

# Load order prefixes of the master files every Skyrim install has
_MASTER_FILES = {0x00: "Skyrim.esm", 0x01: "Update.esm", 0x02: "Dawnguard.esm", 0x03: "HearthFires.esm", 0x04: "Dragonborn.esm"}

# Console skill names -> the game's actor value names
_SKILLS = {
    "onehanded": "OneHanded", "twohanded": "TwoHanded", "archery": "Marksman", "marksman": "Marksman",
    "block": "Block", "smithing": "Smithing", "heavyarmor": "HeavyArmor", "lightarmor": "LightArmor",
    "pickpocket": "Pickpocket", "lockpicking": "Lockpicking", "sneak": "Sneak", "alchemy": "Alchemy",
    "speech": "Speechcraft", "speechcraft": "Speechcraft", "alteration": "Alteration", "conjuration": "Conjuration",
    "destruction": "Destruction", "illusion": "Illusion", "restoration": "Restoration", "enchanting": "Enchanting",
}

# How each console function is written: what comes before the dot, and what its arguments are.
# "ref": an NPC in quotes before the dot. "ref_or_player": the same, or the player when left out.
# Argument kinds: "quest" (editor ID), "int", "form", "skill"
_FUNCTIONS: dict[str, tuple[str | None, list[str]]] = {
    "getstagedone": (None, ["quest", "int"]),
    "getquestcompleted": (None, ["quest"]),
    "getstage": (None, ["quest"]),
    "getdead": ("ref", []),
    "getav": ("ref", ["skill"]),
    "getfactionrank": ("ref_or_player", ["form"]),
    "getinfaction": ("ref_or_player", ["form"]),
    "getkeyworddataforlocation": (None, ["form", "form"]),
    "show": (None, ["form"]),
    "getrelationshiprank": ("ref", ["form"]),
    "ishostiletoactor": ("ref", ["form"]),
    "hasspell": ("ref", ["form"]),
}

_ATOM_RE = re.compile(
    r'^(?:"(?P<ref>[^"]*)"\s*\.\s*)?(?P<func>[A-Za-z]+)(?P<args>(?:\s+[^\s<>=]+)*)\s*(?:(?P<op><=|>=|=|<|>)\s*(?P<value>-?\d+(?:\.\d+)?))?$'
)
_TOKEN_RE = re.compile(r'(\(|\)|\bAND\b|\bOR\b)', re.IGNORECASE)
_HEX_RE = re.compile(r'^[0-9A-Fa-f]{1,8}$')


class UnreadableCondition(ValueError):
    pass


@dataclass(frozen=True)
class Check:
    """One question for the game. `subject` and `argument` are a form ("Skyrim.esm|0D7505"), `player`, a quest editor ID, a number or a skill name"""
    function: str
    subject: str
    argument: str = ""


@dataclass(frozen=True)
class Atom:
    check: Check
    op: str
    value: float
    is_death: bool  # A `getdead` check, used to find outcomes that only check deaths


@dataclass(frozen=True)
class Junction:
    is_and: bool
    parts: tuple["Expression", ...]


Expression = Union[Atom, Junction]


def _compare(answer: float, op: str, value: float) -> bool:
    if op == "=":
        return answer == value
    if op == "<":
        return answer < value
    if op == "<=":
        return answer <= value
    if op == ">":
        return answer > value
    return answer >= value


def evaluate_expression(expression: Expression, answers: dict[Check, float]) -> bool | None:
    """True, False, or None when unknown. A missing form is not true; a form that isn't loaded is unknown"""
    if isinstance(expression, Atom):
        answer = answers[expression.check]
        if answer == ANSWER_MISSING:
            return False
        if answer == ANSWER_NOT_LOADED:
            return None
        if expression.check.function == "getdeadcount":
            answer = 1.0 if answer > 0 else 0.0  # The condition said `getdead`: dead or not, however often
        return _compare(answer, expression.op, expression.value)
    results = [evaluate_expression(part, answers) for part in expression.parts]
    if expression.is_and:
        if False in results:
            return False
        return None if None in results else True
    if True in results:
        return True
    return None if None in results else False


def _is_death_only(expression: Expression) -> bool:
    if isinstance(expression, Atom):
        return expression.is_death
    return all(_is_death_only(part) for part in expression.parts)


def _parse_form(text: str) -> str:
    """A FormID as the console shows it -> "File.esm|XXXXXX", or `player`"""
    if text.lower() == PLAYER:
        return PLAYER
    if not _HEX_RE.match(text):
        if re.match(r'^[A-Za-z_]\w*$', text):
            raise UnreadableCondition(f"'{text}' is a name, not a FormID; the game can't look up factions, keywords or globals by name")
        raise UnreadableCondition(f"'{text}' is not a FormID")
    form_id = int(text, 16)
    load_order = form_id >> 24
    if load_order not in _MASTER_FILES:
        raise UnreadableCondition(f"FormID '{text}' is not from Skyrim or its DLCs")
    local_id = form_id & 0xFFFFFF
    if load_order == 0 and local_id == 0x14:
        return PLAYER
    return f"{_MASTER_FILES[load_order]}|{local_id:06X}"


def normalize_local_id(value) -> int | None:
    """An ID from the characters CSV (e.g. "0D7505", 87750, "FE001ABC") -> its FormID within its plugin"""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip().upper()
    if text.endswith(".0"):
        text = text[:-2]
    if not text or not _HEX_RE.match(text):
        return None
    if text.startswith("FE") and len(text) == 8:
        return int(text[-3:], 16)
    return int(text[-6:], 16)


def build_ref_to_base_map(character_df: pd.DataFrame) -> dict[int, int]:
    """ref_id -> base_id from the characters CSV, only for references that map to exactly one base"""
    if "ref_id" not in character_df.columns or "base_id" not in character_df.columns:
        return {}
    bases: dict[int, set[int]] = {}
    for ref_value, base_value in zip(character_df["ref_id"], character_df["base_id"]):
        ref_id = normalize_local_id(ref_value)
        base_id = normalize_local_id(base_value)
        if ref_id is None or base_id is None:
            continue
        bases.setdefault(ref_id, set()).add(base_id)
    return {ref_id: next(iter(found)) for ref_id, found in bases.items() if len(found) == 1}


class _ConditionParser:
    """Turns one condition into an expression. `AND` binds tighter than `OR`; brackets group"""

    def __init__(self, text: str, ref_to_base: dict[int, int]):
        self.__tokens = [t.strip() for t in _TOKEN_RE.split(text) if t.strip()]
        self.__position = 0
        self.__ref_to_base = ref_to_base

    def parse(self) -> Expression:
        if not self.__tokens:
            raise UnreadableCondition("empty condition")
        expression = self.__parse_or()
        if self.__position != len(self.__tokens):
            raise UnreadableCondition(f"unexpected '{self.__tokens[self.__position]}'")
        return expression

    def __peek(self) -> str | None:
        return self.__tokens[self.__position] if self.__position < len(self.__tokens) else None

    def __parse_or(self) -> Expression:
        parts = [self.__parse_and()]
        while (self.__peek() or "").upper() == "OR":
            self.__position += 1
            parts.append(self.__parse_and())
        return parts[0] if len(parts) == 1 else Junction(False, tuple(parts))

    def __parse_and(self) -> Expression:
        parts = [self.__parse_primary()]
        while (self.__peek() or "").upper() == "AND":
            self.__position += 1
            parts.append(self.__parse_primary())
        return parts[0] if len(parts) == 1 else Junction(True, tuple(parts))

    def __parse_primary(self) -> Expression:
        token = self.__peek()
        if token is None:
            raise UnreadableCondition("condition ends too early")
        self.__position += 1
        if token == "(":
            expression = self.__parse_or()
            if self.__peek() != ")":
                raise UnreadableCondition("missing ')'")
            self.__position += 1
            return expression
        if token == ")" or token.upper() in ("AND", "OR"):
            raise UnreadableCondition(f"unexpected '{token}'")
        return self.__parse_atom(token)

    def __parse_atom(self, text: str) -> Atom:
        match = _ATOM_RE.match(text)
        if not match:
            raise UnreadableCondition(f"can't read '{text}'")
        function = match.group("func").lower()
        if function not in _FUNCTIONS:
            raise UnreadableCondition(f"unknown function {match.group('func')}")
        subject_kind, argument_kinds = _FUNCTIONS[function]
        ref = match.group("ref")
        arguments = match.group("args").split()
        if len(arguments) != len(argument_kinds):
            raise UnreadableCondition(f"{function} takes {len(argument_kinds)} argument(s), got {len(arguments)}")
        if subject_kind is None and ref is not None:
            raise UnreadableCondition(f"{function} doesn't take a reference before the dot")
        if subject_kind == "ref" and ref is None:
            raise UnreadableCondition(f"{function} needs a reference before the dot")

        values: list[str] = []
        if ref is not None:
            values.append(_parse_form(ref))
        elif subject_kind == "ref_or_player":
            values.append(PLAYER)
        for argument, kind in zip(arguments, argument_kinds):
            if kind == "quest":
                values.append(argument)
            elif kind == "int":
                if not argument.isdigit():
                    raise UnreadableCondition(f"'{argument}' is not a number")
                values.append(str(int(argument)))
            elif kind == "skill":
                if argument.lower() not in _SKILLS:
                    raise UnreadableCondition(f"unknown skill '{argument}'")
                values.append(_SKILLS[argument.lower()])
            else:
                values.append(_parse_form(argument))

        if function == "show":
            function = "getglobalvalue"
        is_death = function == "getdead"
        if is_death:
            values[0] = self.__to_death_count(values[0])
            if values[0].startswith("deadcount:"):
                function, values[0] = "getdeadcount", values[0][len("deadcount:"):]

        check = Check(function, values[0], values[1] if len(values) > 1 else "")
        op = match.group("op") or "="
        value = float(match.group("value")) if match.group("value") is not None else 1.0
        return Atom(check, op, value, is_death)

    def __to_death_count(self, reference: str) -> str:
        """Deaths are checked on the base NPC's death count, which works wherever the player is (Part 4)"""
        if reference == PLAYER:
            return reference
        file_name, local_id = reference.split("|")
        base_id = self.__ref_to_base.get(int(local_id, 16))
        if base_id is None:
            return reference
        return f"deadcount:{file_name}|{base_id:06X}"


@dataclass
class TagConditions:
    """The readable conditions of one tag, by outcome number"""
    outcomes: dict[int, Expression] = field(default_factory=dict)
    death_only: set[int] = field(default_factory=set)

    def evaluate(self, answers: dict[Check, float]) -> int | None:
        """The highest true outcome, 0 if none is true, or None when unknown (Part 4)"""
        for slot in sorted(self.outcomes, reverse=True):
            result = evaluate_expression(self.outcomes[slot], answers)
            if result is None:
                return None
            if result:
                return slot
        return 0


@dataclass(frozen=True)
class UnreadableOutcome:
    tag: str
    slot: int
    code: str
    reason: str


class CheckList:
    """Every check the game has to answer, listed once, plus each tag's conditions in terms of that list"""

    def __init__(self, tag_codes: dict[str, dict[int, str]], ref_to_base: dict[int, int] | None = None):
        self.checks: list[Check] = []
        self.tags: dict[str, TagConditions] = {}
        self.unreadable: list[UnreadableOutcome] = []
        self.__index: dict[Check, int] = {}
        for tag, codes in tag_codes.items():
            conditions = TagConditions()
            for slot, code in codes.items():
                try:
                    expression = _ConditionParser(code, ref_to_base or {}).parse()
                except UnreadableCondition as e:
                    self.unreadable.append(UnreadableOutcome(tag, slot, code, str(e)))
                    continue
                conditions.outcomes[slot] = expression
                self.__add_checks(expression)
                if _is_death_only(expression):
                    conditions.death_only.add(slot)
            if conditions.outcomes:
                self.tags[tag] = conditions
        self.version = self.__make_version()

    def __add_checks(self, expression: Expression):
        if isinstance(expression, Junction):
            for part in expression.parts:
                self.__add_checks(part)
        elif expression.check not in self.__index:
            self.__index[expression.check] = len(self.checks)
            self.checks.append(expression.check)

    def __make_version(self) -> str:
        payload = json.dumps([[c.function, c.subject, c.argument] for c in self.checks])
        return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:8]

    def evaluate(self, answers: list[float]) -> dict[str, int | None]:
        """Each tag's outcome. Every tag is unknown when the answers don't match this list"""
        if len(answers) != len(self.checks):
            return {tag: None for tag in self.tags}
        by_check = dict(zip(self.checks, answers))
        return {tag: conditions.evaluate(by_check) for tag, conditions in self.tags.items()}

    def log_unreadable(self):
        total = sum(len(c.outcomes) for c in self.tags.values()) + len(self.unreadable)
        if total:
            logging.info(f"Quest tags: {total - len(self.unreadable)} of {total} conditions readable")
        for outcome in self.unreadable:
            code = " ".join(outcome.code.split())
            logging.warning(f'Quest tag {outcome.tag} slot {outcome.slot}: can\'t read "{code}" ({outcome.reason})')
