"""Conditional blocks in prompts: {if shout} ... {else if npc_event} ... {else} ... {end if}.

A merged prompt holds the text of several situations. When it is sent, only the branches whose condition is true are kept.
A condition is a name, optionally combined with not, and, or ('not' binds tightest, then 'and', then 'or'; no parentheses).

The text is handled line by line: a tag alone on its line removes that whole line, and so do the lines of a branch that is left out,
so the text that is sent has no gaps where tags or other branches were. Tags inside a line keep the text around them"""
import re
from dataclasses import dataclass

from src.prompt_errors import PromptConditionError

# A tag: {if X}, {else if X}, {else}, {end if}. Anchored on these words, so a real variable like {name} never matches
TAG_RE = re.compile(r"\{[ \t]*(?:(?P<kind>if|else[ \t]+if)[ \t]+(?P<expression>[^{}]*?)|(?P<else>else)|(?P<end>end[ \t]+if))[ \t]*\}")
# Almost a tag: {endif}, {elif shout}, {If shout}, {if}... Named as a tag in the error, not as an unknown variable
_NEAR_MISS_RE = re.compile(r"\{[ \t]*(?P<word>end[ \t]*if|end|fi|elif|else[ \t]*if|else|if)(?![A-Za-z0-9_])(?P<rest>[^{}]*)\}", re.IGNORECASE)
# Shared section names that would be read as (almost) a tag, so a section can't take them
RESERVED_SECTION_NAMES = {"if", "else", "elif", "elseif", "end", "endif", "fi"}


def near_miss_problem(text: str) -> str | None:
    """The first tag that is almost right, and how to write it"""
    for match in _NEAR_MISS_RE.finditer(text):
        written = match.group(0)
        if TAG_RE.fullmatch(written):
            continue
        word = re.sub(r"[ \t]+", " ", match.group("word").lower())
        rest = match.group("rest").strip()
        if word in ("end if", "endif", "end", "fi"):
            return f"{written}: write {{end if}}."
        if word in ("else if", "elseif", "elif"):
            return f"{written}: write {{else if {rest or 'shout'}}}."
        if word == "else":
            if not rest:
                return f"{written}: write {{else}}."
            return f"{written}: {{else}} takes no condition. For another condition, write {{else if {rest}}}."
        if not rest:
            return f"{written} has no condition. Write one after 'if', e.g. {{if shout}}."
        return f"{written}: write {{if {rest}}}."
    return None


@dataclass
class _Tag:
    kind: str # "if", "else if", "else", "end if"
    expression: str
    original: str # As written, for the error messages


@dataclass
class _Block:
    parent_active: bool
    branch_active: bool
    taken: bool # A branch of this block was chosen already
    has_else: bool
    opening: str


def has_condition_tags(text: str) -> bool:
    return TAG_RE.search(text or "") is not None


def strip_condition_tags(text: str) -> str:
    """The text with the tags removed and every branch kept. For checking the variables of all branches"""
    return TAG_RE.sub("", text or "")


def _tag_from_match(match: re.Match[str]) -> _Tag:
    if match.group("end"):
        return _Tag("end if", "", match.group(0))
    if match.group("else"):
        return _Tag("else", "", match.group(0))
    kind = "if" if match.group("kind") == "if" else "else if"
    return _Tag(kind, match.group("expression").strip(), match.group(0))


def _evaluate(expression: str, active: set[str], allowed: set[str], explanations: dict[str, str], original: str) -> bool:
    """True if the condition holds. Raises PromptConditionError for a condition that can't be read"""
    if "(" in expression or ")" in expression:
        raise PromptConditionError(f"{original}: brackets are not supported. Write the conditions one after another, e.g. {{if shout or npc_event}}.")
    words = expression.split()
    if not words:
        raise PromptConditionError(f"{original} has no condition. Write one after 'if', e.g. {{if shout}}.")
    alternatives: list[list[tuple[bool, str]]] = [[]] # 'or' of 'and's of (negated, name)
    negated = False
    expect_name = True
    for index, word in enumerate(words):
        lowered = word.lower()
        if expect_name:
            if lowered == "not":
                negated = not negated
                continue
            if lowered in ("and", "or"):
                raise PromptConditionError(f"{original}: '{word}' needs a condition before it.")
            if lowered not in allowed:
                if lowered in explanations:
                    raise PromptConditionError(f"{original}: {explanations[lowered]}")
                known = ", ".join(sorted(allowed)) or "none"
                raise PromptConditionError(f"{original}: '{word}' is not a condition this prompt knows. Use one of: {known}.")
            alternatives[-1].append((negated, lowered))
            negated = False
            expect_name = False
        elif lowered == "and":
            expect_name = True
        elif lowered == "or":
            alternatives.append([])
            expect_name = True
        else:
            raise PromptConditionError(f"{original}: put 'and' or 'or' between '{words[index - 1]}' and '{word}'.")
    if expect_name:
        raise PromptConditionError(f"{original}: a condition is missing after '{words[-1]}'.")
    return any(all((name in active) != negated for negated, name in group) for group in alternatives)


class _Evaluator:
    def __init__(self, active: set[str], allowed: set[str], explanations: dict[str, str]):
        self.__active = active
        self.__allowed = allowed
        self.__explanations = explanations
        self.blocks: list[_Block] = []

    @property
    def is_active(self) -> bool:
        return not self.blocks or self.blocks[-1].branch_active

    def apply(self, tag: _Tag):
        """Opens, switches or closes a block. Every condition is checked, also in branches that are left out"""
        if tag.kind == "if":
            holds = _evaluate(tag.expression, self.__active, self.__allowed, self.__explanations, tag.original)
            parent_active = self.is_active
            self.blocks.append(_Block(parent_active, parent_active and holds, holds, False, tag.original))
            return
        if not self.blocks:
            raise PromptConditionError(f"{tag.original} has no {{if ...}} before it.")
        block = self.blocks[-1]
        if tag.kind == "else if":
            if block.has_else:
                raise PromptConditionError(f"{tag.original} comes after the {{else}} of {block.opening}. Put it before the {{else}}.")
            holds = _evaluate(tag.expression, self.__active, self.__allowed, self.__explanations, tag.original)
            block.branch_active = block.parent_active and not block.taken and holds
            block.taken = block.taken or holds
        elif tag.kind == "else":
            if block.has_else:
                raise PromptConditionError(f"{block.opening} has two {{else}}. Keep one.")
            block.branch_active = block.parent_active and not block.taken
            block.taken = True
            block.has_else = True
        else:
            self.blocks.pop()


def apply_conditions(text: str, active: set[str], allowed: set[str], explanations: dict[str, str] | None = None) -> str:
    """Keeps the branches whose condition is true and removes the tags

    Args:
        active (set[str]): the conditions that are true now
        allowed (set[str]): the conditions this prompt knows
        explanations (dict[str, str] | None): by condition name, why a condition this prompt doesn't know can never be true here

    Raises:
        PromptConditionError: the blocks are broken, or use a condition this prompt doesn't know
    """
    text = text or ""
    near_miss = near_miss_problem(text)
    if near_miss:
        raise PromptConditionError(near_miss)
    if not has_condition_tags(text):
        return text
    evaluator = _Evaluator(active, allowed, explanations or {})
    kept_lines: list[str] = []
    for line in text.split("\n"):
        whole_line_tag = TAG_RE.fullmatch(line.strip())
        if whole_line_tag:
            evaluator.apply(_tag_from_match(whole_line_tag)) # The line itself is removed
            continue
        was_active = evaluator.is_active
        parts: list[str] = []
        position = 0
        for match in TAG_RE.finditer(line):
            if evaluator.is_active:
                parts.append(line[position:match.start()])
            evaluator.apply(_tag_from_match(match))
            was_active = was_active or evaluator.is_active
            position = match.end()
        if evaluator.is_active:
            parts.append(line[position:])
        if was_active: # A line that is entirely in a branch left out is removed, line break included
            kept_lines.append("".join(parts))
    if evaluator.blocks:
        raise PromptConditionError(f"{evaluator.blocks[-1].opening} has no matching {{end if}}.")
    return "\n".join(kept_lines)


def find_condition_error(text: str, allowed: set[str], explanations: dict[str, str] | None = None) -> str | None:
    """What is wrong with the prompt's conditional blocks, in plain words. None if nothing is"""
    try:
        apply_conditions(text, set(), allowed, explanations)
    except PromptConditionError as e:
        return e.problem
    return None
