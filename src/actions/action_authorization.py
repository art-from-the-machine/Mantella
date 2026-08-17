"""Conservative current-turn authorization for LLM-originated actions."""

from dataclasses import dataclass, field, replace
from enum import Enum
import re
from typing import Iterable

from src import utils

logger = utils.get_logger()


class ActionPolicy(str, Enum):
    EXPLICIT_CURRENT_REQUEST = "explicit_current_request"
    REACTIVE_CONTEXTUAL = "reactive_contextual"
    SPECIAL = "special"


EXPLICIT_ACTIONS = frozenset({
    "mantella_npc_equip",
    "mantella_npc_follow",
    "mantella_npc_inventory",
    "mantella_npc_moveto",
    "mantella_npc_teleport",
    "mantella_npc_unfollow",
    "mantella_npc_barter",
    "mantella_npc_wait",
})

REACTIVE_ACTIONS = frozenset({
    "mantella_npc_offended",       # Attack
    "mantella_npc_flee",
    "mantella_npc_forgiven",       # StandDown
    "mantella_end_conversation",
    "mantella_npc_brawl",
    "mantella_npc_reportcrime",
    "mantella_npc_absolvecrime",
    "mantella_npc_castspell",
    "mantella_npc_emote",
    "mantella_npc_collectingredients",
    "mantella_npc_loot",
    "mantella_npc_addtoconversation",
    "mantella_npc_leadto",
    "mantella_npc_travelto",
    "mantella_npc_canceltravel",
})


def action_policy(identifier: str) -> ActionPolicy:
    if identifier in EXPLICIT_ACTIONS:
        return ActionPolicy.EXPLICIT_CURRENT_REQUEST
    if identifier in REACTIVE_ACTIONS:
        return ActionPolicy.REACTIVE_CONTEXTUAL
    # Look may be automatic when vision is configured that way; Listen has a
    # direct player-keyword path. Barter and Wait are explicit-current-request
    # actions (see EXPLICIT_ACTIONS above).
    return ActionPolicy.SPECIAL


def _normalise(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").casefold()).strip()


def _boundary_pattern(body: str) -> str:
    # Allow imperative clauses after conjunctions, commas, or "then", while
    # excluding embedded historical/question wording such as "you said you'd".
    return rf"(?:^|(?:,|;|\band\b|\bthen\b)\s*)(?:please\s+)?{body}"


def _polite_request_pattern(body: str) -> str:
    """Match a direct, present-tense request without accepting history/questions."""
    return rf"(?:^|(?:,|;|\band\b|\bthen\b)\s*)(?:please\s+)?(?:can|could|would)\s+you\s+{body}(?!\s+(?:yesterday|earlier|before|later|someday|ever)\b)"


def _polite_self_request_pattern(body: str) -> str:
    return rf"(?:^|(?:,|;|\band\b|\bthen\b)\s*)(?:please\s+)?(?:can|could|would)\s+i\s+{body}(?!\s+(?:yesterday|earlier|before|later|someday|ever)\b)"


def _find_actions(text: str) -> frozenset[str]:
    value = _normalise(text)
    patterns = {
        "mantella_npc_inventory": [
            _boundary_pattern(r"(?:check|show(?:\s+me)?|open)\s+(?:your\s+)?inventory\b"),
            _polite_request_pattern(r"(?:check|show|open)\s+your\s+inventory\b"),
            _polite_self_request_pattern(r"see\s+(?:your\s+inventory|what\s+you(?:'re|\s+are)\s+carrying)\b"),
            _boundary_pattern(r"let\s+me\s+see\s+(?:your\s+)?inventory\b"),
            _boundary_pattern(r"let\s+me\s+see\s+what\s+you(?:'re|\s+are)\s+carrying\b"),
            _boundary_pattern(r"(?:give|hand)\s+me\s+(?:your|the)\s+\w+"),
            _boundary_pattern(r"take\s+(?:the|your)\s+\w+\s+from\s+you\b"),
        ],
        "mantella_npc_follow": [
            _boundary_pattern(r"follow\s+(?:me|us)\b"),
            _polite_request_pattern(r"follow\s+(?:me|us)\b"),
            _polite_request_pattern(r"come\s+(?:with\s+(?:me|us)|along)\b"),
            _polite_request_pattern(r"accompany\s+(?:me|us)\b"),
            _boundary_pattern(r"come\s+(?:with\s+(?:me|us)|along)\b"),
            _boundary_pattern(r"join\s+(?:me|us)\b"),
            _boundary_pattern(r"accompany\s+(?:me|us)\b"),
            _boundary_pattern(r"walk\s+with\s+(?:me|us)\b"),
        ],
        "mantella_npc_unfollow": [
            _boundary_pattern(r"stop\s+following\s+(?:me|us)\b"),
            _boundary_pattern(r"(?:don'?t|do\s+not|no\s+longer)\s+follow\s+(?:me|us)\b"),
            _polite_request_pattern(r"stop\s+following\s+(?:me|us)\b"),
        ],
        "mantella_npc_equip": [
            _boundary_pattern(r"(?:put|wear)\s+(?:your\s+)?(?:clothes|armor|armour)\s+back\s+on\b"),
            _polite_request_pattern(r"(?:put|wear)\s+(?:your\s+)?(?:clothes|armor|armour)\s+back\s+on\b"),
            _boundary_pattern(r"get\s+dressed\b"),
            _polite_request_pattern(r"get\s+dressed\b"),
            _boundary_pattern(r"put\s+(?:some\s+)?(?:clothes|armor|armour)\s+on\b"),
            _polite_request_pattern(r"put\s+(?:some\s+)?(?:clothes|armor|armour)\s+on\b"),
            _boundary_pattern(r"(?:equip|put\s+on|wear|use|draw|ready)\s+(?:(?:the|your|this|that)\s+)?(?:it|[\w'’]+)"),
            _polite_request_pattern(r"(?:equip|put\s+on|wear|use|draw|ready)\s+(?:(?:the|your|this|that)\s+)?(?:it|[\w'’]+)"),
            _boundary_pattern(r"put\s+(?:(?:the|your|this|that)\s+)?(?:it|[\w'’]+)\s+on\b"),
            _polite_request_pattern(r"put\s+(?:(?:the|your|this|that)\s+)?(?:it|[\w'’]+)\s+on\b"),
            r"(?:^|[.,;:]\s*)(?:please\s+)?(?:i\s+(?:need|want)\s+you\s+to|i['’]d\s+like\s+you\s+to)\s+(?:equip|put\s+on|wear|use|draw|ready)\s+(?:(?:the|your|this|that)\s+)?(?:it|[\w'’]+)",
            r"(?:^|[.,;:]\s*)please\s+(?:equip|put\s+on|wear|use|draw|ready)\s+(?:(?:the|your|this|that)\s+)?(?:it|[\w'’]+)",
            # Permit an explicit corrective command after a complaint or
            # correction clause without authorizing descriptive mentions.
            r"(?:not\s+actually\s+equipping\s+it|still\s+aren['’]t\s+wearing\s+it)[.,;:]?\s*(?:equip|put\s+on|use|draw)\s+(?:the|your|this|that)\s+\w+",
            r"(?:^|\bno\s*,\s*)(?:equip|put\s+on|use|draw)\s+(?:the|your|this|that)\s+\w+",
            r"\buse\s+(?:the|your|this|that)\s+\w+\s+i\s+just\s+gave\s+you\b",
        ],
        "mantella_npc_moveto": [
            _boundary_pattern(r"move\s+to\s+me\b"),
            _boundary_pattern(r"move\s+here\b"),
            _boundary_pattern(r"come\s+over\s+here\b"),
            _boundary_pattern(r"go\s+to\s+me\b"),
            _polite_request_pattern(r"move\s+(?:to\s+me|here)\b"),
            _polite_request_pattern(r"come\s+over\s+here\b"),
            _polite_request_pattern(r"go\s+to\s+me\b"),
        ],
        "mantella_npc_teleport": [
            _boundary_pattern(r"teleport\s+(?:to\s+me|here|to\s+us)\b"),
            _polite_request_pattern(r"teleport\s+(?:to\s+me|here|to\s+us)\b"),
        ],
        "mantella_npc_barter": [
            # Commerce requests are intentionally narrow: historical/item
            # mentions and negated statements must not authorize Barter.
            r"(?:^|[,;]\s*)(?:please\s+)?(?:show(?:\s+me)?|tell\s+me)\s+what\s+you(?:\s+have|['’]re)\s+for\s+sale\b",
            r"(?:^|[,;]\s*)what\s+are\s+you\s+selling\b",
            r"(?:^|[,;]\s*)(?:i['’]d|i\s+would)\s+like\s+to\s+(?:buy|sell)\b",
            r"(?:^|[,;]\s*)can\s+i\s+(?:buy|sell)\b",
            r"(?:^|[,;]\s*)(?:please\s+)?(?:let\s+me|i\s+want\s+to)\s+(?:buy|sell)\b",
            r"(?:^|[,;]\s*)(?:can\s+we|let['’]s|i['’]d\s+like\s+to|i\s+would\s+like\s+to)\s+(?:barter|trade)\b",
            _polite_request_pattern(r"(?:show|tell)\s+me\s+what\s+you(?:\s+have|['’]re)\s+for\s+sale\b"),
            _polite_request_pattern(r"what\s+are\s+you\s+selling\b"),
            _polite_request_pattern(r"tell\s+me\s+what\s+you(?:\s+are|['’]re)\s+selling\b"),
            _polite_self_request_pattern(r"(?:buy|sell)\b"),
            _polite_self_request_pattern(r"see\s+what\s+you(?:\s+have|['’]re)\s+for\s+sale\b"),
        ],
        "mantella_npc_wait": [
            _boundary_pattern(r"wait(?:\s+(?:here|there|for\s+(?:me|us)))?(?:\s*[.!?]|$)"),
            _boundary_pattern(r"stay\s+here\b"),
            _boundary_pattern(r"hold\s+position\b"),
            _polite_request_pattern(r"wait(?:\s+(?:here|there|for\s+(?:me|us)))?\b"),
            _polite_request_pattern(r"stay\s+here\b"),
        ],
        "mantella_npc_vision": [
            _boundary_pattern(r"look\s+at\s+(?:this|that|what\s+i(?:'m|\s+am)\s+showing\s+you)\b"),
            _boundary_pattern(r"see\s+what\s+i\s+see\b"),
            _boundary_pattern(r"check\s+this\s+out\b"),
            _polite_request_pattern(r"look\s+at\s+(?:this|that)\b"),
            _polite_request_pattern(r"check\s+this\s+out\b"),
        ],
    }
    found = {identifier for identifier, candidates in patterns.items() if any(re.search(candidate, value) for candidate in candidates)}
    return frozenset(found)


def _find_unresolved_followup_actions(text: str, unresolved_actions: Iterable[str]) -> frozenset[str]:
    """Resolve only tightly-scoped immediate references to a failed action."""
    value = _normalise(text)
    unresolved = set(unresolved_actions)
    if "mantella_npc_inventory" not in unresolved:
        return frozenset()
    inventory_followup = (
        r"^(?:no,\s*)?(?:actually\s+)?open\s+it(?:\s+properly|\s+so\s+i\s+can\s+see\s+it)?[.!?]?$",
        r"^(?:no,\s*)?let\s+me\s+see\s+it[.!?]?$",
    )
    if any(re.fullmatch(pattern, value) for pattern in inventory_followup):
        return frozenset({"mantella_npc_inventory"})
    return frozenset()


def _extract_equip_target(text: str) -> str | None:
    value = _normalise(text)
    if re.search(r"\bget\s+dressed\b", value) or re.search(r"\b(?:put\s+(?:your\s+)?clothes(?:\s+back)?\s+on|wear\s+(?:your\s+)?clothes)\b", value):
        return "owned clothes"
    if re.search(r"\b(?:put\s+(?:some\s+|your\s+)?(?:armor|armour)(?:\s+back)?\s+on|wear\s+(?:your\s+)?(?:armor|armour))\b", value):
        return "owned armor"
    if re.search(r"\b(?:equip|put\s+on|wear|use|draw|ready)\s+it\b", value):
        return "recent transferred item"
    put_on = re.search(r"\bput\s+(?:the|your|this|that)?\s*(it|[\w'’]+)\s+on\b", value)
    if put_on:
        return "recent transferred item" if put_on.group(1) == "it" else put_on.group(1)
    match = re.search(r"\b(?:equip|put\s+on|wear|use|draw|ready)\s+(?:(?:the|your|this|that)\s+)?(.+?)(?:[.!?]|$)", value)
    if not match:
        if re.search(r"\b(?:best|some)\s+(?:armor|armour|weapon)\b", value):
            return "best " + re.search(r"\b(?:armor|armour|weapon)\b", value).group(0)
        return None
    target = match.group(1).strip()
    target = re.split(r"\s+(?:now|please)\b", target, maxsplit=1)[0].strip()
    if re.search(r"\barmor\s+i\s+just\s+gave\s+you\b", target):
        return "recent transferred armor"
    if target in {"armor", "armour"}:
        return "owned armor"
    if target == "weapon":
        return "recent transferred weapon"
    if target in {"shield", "helmet", "boots", "gauntlets", "sword", "bow", "mace", "axe"}:
        return "recent transferred " + target
    if target == "something":
        return "recent transferred item"
    return target


def _identity_pairs(participant_identities: Iterable[str | tuple[str, str]]) -> list[tuple[str, str]]:
    result = []
    for identity in participant_identities:
        if isinstance(identity, tuple):
            result.append((_normalise(identity[0]), str(identity[1])))
        else:
            result.append(("", str(identity)))
    return result


def _resolve_equip_target(extracted: str | None, recent_items: Iterable[str]) -> str | None:
    recent = tuple(dict.fromkeys(item.strip() for item in recent_items if item and item.strip()))
    if extracted in {"shield", "helmet", "boots", "gauntlets", "sword", "bow", "mace", "axe"}:
        compatible = tuple(item for item in recent if extracted in item.casefold())
        if len(compatible) == 1:
            return compatible[0]
        return "recent transferred " + extracted
    if extracted in {"owned clothes", "owned armor"}:
        clothes_words = ("tunic", "robe", "clothes", "clothing", "outfit", "dress")
        armor_words = ("armor", "armour", "cuirass", "tunic", "robe", "helmet", "shield", "boots", "gauntlets")
        words = clothes_words if extracted == "owned clothes" else armor_words
        compatible = tuple(item for item in recent if any(word in item.casefold() for word in words))
        return compatible[0] if len(compatible) == 1 else extracted
    if extracted and " " not in extracted:
        compatible = tuple(item for item in recent if extracted in item.casefold())
        if len(compatible) == 1:
            return compatible[0]
    if not extracted or not extracted.startswith("recent transferred "):
        return extracted
    compatible = recent
    if extracted == "recent transferred armor":
        armor_words = ("armor", "armour", "cuirass", "tunic", "robe", "helmet", "shield", "boots", "gauntlets")
        compatible = tuple(item for item in recent if any(word in item.casefold() for word in armor_words))
    elif extracted == "recent transferred weapon":
        weapon_words = ("sword", "bow", "mace", "axe", "dagger", "staff", "weapon")
        compatible = tuple(item for item in recent if any(word in item.casefold() for word in weapon_words))
    elif extracted.startswith("recent transferred ") and extracted != "recent transferred item":
        category = extracted.removeprefix("recent transferred ")
        compatible = tuple(item for item in recent if category in item.casefold())
    return compatible[0] if len(compatible) == 1 else extracted


def _equip_item_matches_category(category: str, item: str) -> bool:
    """Return whether a concrete item fits an unresolved owned-item request."""
    value = item.casefold()
    if category == "owned clothes":
        words = ("tunic", "robe", "clothes", "clothing", "outfit", "dress")
    elif category == "owned armor":
        words = ("armor", "armour", "cuirass", "tunic", "robe", "helmet", "shield", "boots", "gauntlets")
    else:
        return False
    return any(word in value for word in words)


@dataclass(frozen=True)
class ActionAuthorizationContext:
    """Immutable authorization snapshot for one player-turn generation."""

    turn_id: int
    player_text: str
    participant_ref_ids: frozenset[str]
    participant_identities: tuple[tuple[str, str], ...]
    requested_actions: frozenset[str]
    requested_actions_by_actor: tuple[tuple[str, frozenset[str]], ...] = ()
    ambiguous_unscoped_request: bool = False
    enforce: bool = True
    stale: bool = False
    automatic_vision: bool = False
    equip_target: str | None = None
    equip_targets_by_actor: tuple[tuple[str, str], ...] = ()
    owned_equip_items_by_actor: tuple[tuple[str, tuple[str, ...]], ...] = ()
    authoritative_inventory_actor_refs: frozenset[str] = frozenset()

    @classmethod
    def for_player_turn(
        cls,
        turn_id: int,
        player_text: str,
        participant_identities: Iterable[str | tuple[str, str]] = (),
        *,
        automatic_vision: bool = False,
        unresolved_actions: Iterable[str] = (),
        recent_equip_item: str | None = None,
        recent_equip_items: Iterable[str] = (),
        recent_equip_items_by_actor: dict[str, Iterable[str]] | None = None,
        owned_equip_items_by_actor: dict[str, Iterable[str]] | None = None,
        authoritative_inventory_actor_refs: Iterable[str] = (),
    ) -> "ActionAuthorizationContext":
        identities = _identity_pairs(participant_identities)
        value = _normalise(player_text)
        addressed: list[tuple[str, frozenset[str]]] = []
        addressed_equip_targets: list[tuple[str, str]] = []
        address_spans: list[tuple[int, int]] = []
        ambiguous_address = False
        for name, ref_id in identities:
            if not name:
                continue
            for match in re.finditer(rf"\b{re.escape(name)}\s*[,;:]", value):
                address_spans.append((match.start(), match.end()))

        # Resolve each addressed name to exactly one stable actor. Duplicate
        # display names are deliberately ambiguous and cannot authorize a
        # targeted action without a stronger identity signal.
        for match in re.finditer(r"([^,;:]+?)\s*[,;:]", value):
            name = _normalise(match.group(1))
            matches = [ref_id for candidate, ref_id in identities if candidate == name]
            if not matches:
                continue
            next_starts = [start for start, _ in address_spans if start > match.start()]
            end = min(next_starts) if next_starts else len(value)
            clause = value[match.end():end]
            if len(matches) == 1:
                clause_actions = _find_actions(clause)
                addressed.append((matches[0], clause_actions))
                if "mantella_npc_equip" in clause_actions:
                    extracted = _extract_equip_target(clause)
                    recent_actor_items = (recent_equip_items_by_actor or {}).get(matches[0], ())
                    use_owned = (
                        extracted != "recent transferred item"
                        and str(matches[0]) in {str(ref) for ref in authoritative_inventory_actor_refs}
                    )
                    actor_items = (
                        (owned_equip_items_by_actor or {}).get(matches[0], recent_actor_items)
                        if use_owned else recent_actor_items
                    )
                    target = _resolve_equip_target(
                        extracted,
                        actor_items,
                    )
                    if target:
                        addressed_equip_targets.append((matches[0], target))
            elif _find_actions(clause):
                ambiguous_address = True

        has_addressed_action = any(actions for _, actions in addressed)
        global_actions = frozenset() if has_addressed_action else _find_actions(value)
        if not has_addressed_action and len(identities) == 1:
            global_actions = frozenset(
                set(global_actions) | set(_find_unresolved_followup_actions(value, unresolved_actions))
            )
        ambiguous = ambiguous_address or bool(re.search(r"\bone\s+of\s+you\b", value) and global_actions)
        recent_items = tuple(recent_equip_items) + ((recent_equip_item,) if recent_equip_item else ())
        extracted_equip_target = _extract_equip_target(value) if "mantella_npc_equip" in global_actions else None
        if (
            len(identities) == 1
            and extracted_equip_target != "recent transferred item"
            and str(identities[0][1]) in {str(ref) for ref in authoritative_inventory_actor_refs}
        ):
            recent_items = tuple((owned_equip_items_by_actor or {}).get(identities[0][1], recent_items))
        extracted_equip_target = _resolve_equip_target(extracted_equip_target, recent_items)
        return cls(
            turn_id,
            player_text,
            frozenset(ref_id for _, ref_id in identities),
            tuple(identities),
            global_actions,
            tuple(addressed),
            ambiguous,
            True,
            False,
            automatic_vision,
            extracted_equip_target,
            tuple(addressed_equip_targets),
            tuple(
                (str(ref_id), tuple(dict.fromkeys(item.strip() for item in items if item and item.strip())))
                for ref_id, items in (owned_equip_items_by_actor or {}).items()
            ),
            frozenset(str(ref_id) for ref_id in authoritative_inventory_actor_refs),
        )

    @classmethod
    def permissive(cls) -> "ActionAuthorizationContext":
        """Compatibility context for direct callers outside Conversation."""
        return cls(
            turn_id=0,
            player_text="",
            participant_ref_ids=frozenset(),
            participant_identities=(),
            requested_actions=frozenset(),
            enforce=False,
        )

    def as_stale(self) -> "ActionAuthorizationContext":
        return replace(self, stale=True)

    def for_continuation(self) -> "ActionAuthorizationContext":
        """Continue a turn after a game result without re-authorizing actions."""
        return replace(self, requested_actions=frozenset(), requested_actions_by_actor=(), equip_target=None, equip_targets_by_actor=())

    def _owned_items_for_actor(self, actor_ref_id: str | None) -> tuple[str, ...]:
        return next((items for ref_id, items in self.owned_equip_items_by_actor if ref_id == actor_ref_id), ())

    def resolve_actor_ref(self, display_name: str | None) -> str | None:
        if not display_name:
            return None
        matches = [ref_id for name, ref_id in self.participant_identities if name == _normalise(display_name)]
        return matches[0] if len(matches) == 1 else None

    def _requested_for_actor(self, identifier: str, actor_ref_id: str | None) -> bool:
        if self.ambiguous_unscoped_request:
            return False
        for ref_id, actions in self.requested_actions_by_actor:
            if ref_id == actor_ref_id:
                return identifier in actions
        # An unaddressed request can be used for a single participant or for
        # an explicitly collective request. "One of you" is rejected above.
        return identifier in self.requested_actions

    def authorize(self, identifier: str, actor_ref_id: str | None = None, arguments: dict | None = None) -> tuple[bool, str]:
        if not self.enforce:
            return True, "compatibility_context"
        if self.stale or self.turn_id < 0:
            return False, "stale_turn"
        if actor_ref_id and self.participant_ref_ids and actor_ref_id not in self.participant_ref_ids:
            return False, "actor_not_in_turn_snapshot"
        policy = action_policy(identifier)
        if policy == ActionPolicy.EXPLICIT_CURRENT_REQUEST and not self._requested_for_actor(identifier, actor_ref_id):
            return False, "current_turn_not_authorized"
        equip_target = self.equip_target
        for ref_id, target in self.equip_targets_by_actor:
            if ref_id == actor_ref_id:
                equip_target = target
                break
        if identifier == "mantella_npc_equip":
            supplied = (arguments or {}).get("item") or (arguments or {}).get("target")
            logger.debug(
                "Equip authorization context: turn=%s actor=%s requested_target=%s",
                self.turn_id,
                actor_ref_id,
                equip_target,
            )
            category_target = equip_target in {"owned clothes", "owned armor"}
            if category_target:
                # Category requests may legitimately have several owned
                # candidates.  Let the model select a concrete item, then
                # validate that selection against this immutable turn's
                # authoritative inventory snapshot and category.
                if supplied is None or actor_ref_id not in self.authoritative_inventory_actor_refs:
                    return False, "equip_target_missing"
                owned = self._owned_items_for_actor(actor_ref_id)
                supplied_text = str(supplied)
                if not any(supplied_text.casefold() == item.casefold() for item in owned):
                    return False, "equip_target_not_owned"
                if not _equip_item_matches_category(equip_target, supplied_text):
                    return False, "equip_target_not_authorized"
            elif not equip_target or equip_target.startswith("recent transferred ") or equip_target.startswith("owned "):
                return False, "equip_target_missing"
            elif supplied is None:
                return False, "equip_target_missing"
            if not category_target and supplied and equip_target.casefold() not in str(supplied).casefold() and str(supplied).casefold() not in equip_target.casefold():
                return False, "equip_target_not_authorized"
            if not category_target and actor_ref_id in self.authoritative_inventory_actor_refs:
                owned = self._owned_items_for_actor(actor_ref_id)
                if not any(str(supplied).casefold() == item.casefold() for item in owned):
                    return False, "equip_target_not_owned"
            logger.debug("Equip target validation: authorized=%s generated=%s result=accepted", equip_target, supplied)
        if identifier == "mantella_npc_vision" and not self.automatic_vision and not self._requested_for_actor(identifier, actor_ref_id):
            return False, "current_turn_not_authorized"
        return True, "authorized"

    def missing_requested_action_targets(self, emitted_actions: set[tuple[str, str | None]], actor_ref_id: str | None = None) -> frozenset[tuple[str, str | None]]:
        if not self.enforce or self.stale:
            return frozenset()
        missing: list[tuple[str, str | None]] = []
        if self.requested_actions:
            for identifier in self.requested_actions:
                if not any(emitted_identifier == identifier for emitted_identifier, _ in emitted_actions):
                    missing.append((identifier, actor_ref_id))
        for ref_id, actions in self.requested_actions_by_actor:
            for identifier in actions:
                if (identifier, ref_id) not in emitted_actions:
                    missing.append((identifier, ref_id))
        return frozenset(missing)

    def missing_requested_actions(self, emitted_actions: set[tuple[str, str | None]], actor_ref_id: str | None = None) -> frozenset[str]:
        return frozenset(identifier for identifier, _ in self.missing_requested_action_targets(emitted_actions, actor_ref_id))

    def log_missing_requested_actions(self, emitted_actions: set[tuple[str, str | None]], actor_ref_id: str | None = None) -> None:
        missing = self.missing_requested_action_targets(emitted_actions, actor_ref_id)
        for identifier, target_ref_id in sorted(missing, key=lambda item: (item[0], item[1] or "")):
            logger.warning(
                f"Requested action not emitted: {identifier} turn={self.turn_id} actor={target_ref_id or 'unknown'}"
            )

    def corrective_prompt(self, missing: frozenset[tuple[str, str | None]]) -> str:
        """Build one mechanical retry instruction without inferring an action from prose."""
        identifiers = sorted({identifier for identifier, _ in missing})
        names = [identifier.removeprefix("mantella_npc_") for identifier in identifiers]
        lines = [
            "CORRECTION: The player's CURRENT request explicitly requires: " + ", ".join(names) + ".",
            "Your previous response did not emit the required executable action prefix.",
            "Respond again using only the required action prefix or prefixes. Do not claim the action occurred without them.",
        ]
        equip_target = self.equip_target
        target_refs = {actor_ref_id for _, actor_ref_id in missing if actor_ref_id}
        if len(target_refs) == 1:
            target_ref = next(iter(target_refs))
            equip_target = next(
                (target for ref_id, target in self.equip_targets_by_actor if ref_id == target_ref),
                equip_target,
            )
        if "mantella_npc_equip" in identifiers and equip_target and equip_target not in {"recent transferred item", "recent transferred armor"}:
            lines.append(f"Authorized Equip item: {equip_target}. Emit exactly: Equip: {equip_target}")
        return "\n".join(lines)


@dataclass
class ActionTurnLifecycle:
    """Observed pipeline state for one immutable authorization context."""

    context: ActionAuthorizationContext
    generated: set[tuple[str, str | None]] = field(default_factory=set)
    rejected: dict[tuple[str, str | None], str] = field(default_factory=dict)
    authorized: set[tuple[str, str | None]] = field(default_factory=set)
    queued: set[tuple[str, str | None]] = field(default_factory=set)
    protocol_dispatched: set[tuple[str, str | None]] = field(default_factory=set)
    game_result_received: set[tuple[str, str | None]] = field(default_factory=set)
    correction_attempted: bool = False

    def key(self, identifier: str, actor_ref_id: str | None) -> tuple[str, str | None]:
        return identifier, actor_ref_id

    def record_generated(self, identifier: str, actor_ref_id: str | None) -> None:
        self.generated.add(self.key(identifier, actor_ref_id))

    def record_rejected(self, identifier: str, actor_ref_id: str | None, reason: str) -> None:
        self.rejected[self.key(identifier, actor_ref_id)] = reason

    def record_authorized(self, identifier: str, actor_ref_id: str | None) -> None:
        self.authorized.add(self.key(identifier, actor_ref_id))

    def record_queued(self, identifier: str, actor_ref_id: str | None) -> None:
        self.queued.add(self.key(identifier, actor_ref_id))

    def record_protocol_dispatched(self, identifier: str, actor_ref_id: str | None) -> None:
        self.protocol_dispatched.add(self.key(identifier, actor_ref_id))

    def record_game_result(self) -> None:
        self.game_result_received.update(self.protocol_dispatched)

    def missing_generated(self, actor_ref_id: str | None) -> frozenset[tuple[str, str | None]]:
        return self.context.missing_requested_action_targets(self.generated, actor_ref_id)

    def authorized_not_queued(self) -> set[tuple[str, str | None]]:
        return self.authorized - self.queued
