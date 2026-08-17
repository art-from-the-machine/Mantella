"""Streaming/action-prefix parser regressions.

Player intent and action obligation belong to ActionAuthorizationContext.  The
legacy parser-side intent suite was superseded when current-turn immutable
authorization became the production architecture; this module now tests only
the parser's actual contract.
"""

from src.conversation.action import Action
from src.llm.output.actions_parser import actions_parser
from src.llm.output.output_parser import sentence_generation_settings
from src.llm.sentence_content import SentenceContent, SentenceTypeEnum


def make_action(identifier: str, keyword: str, *, requires_response: bool = False) -> Action:
    return Action(
        identifier, keyword, keyword, "", "", requires_response, False,
        True, True, False, "item_name" if identifier == "mantella_npc_equip" else "",
        "npc_items", [],
    )


def parse(text: str, actions: list[Action]) -> SentenceContent:
    content = SentenceContent(None, text, SentenceTypeEnum.SPEECH)
    parsed, _ = actions_parser(actions).modify_sentence_content(
        content, None, sentence_generation_settings(None)
    )
    assert parsed is not None
    return parsed


def test_equip_preserves_multiword_item_and_separates_dialogue():
    parsed = parse(
        "Equip: Golden Saint Shield | I shall wear it.",
        [make_action("mantella_npc_equip", "Equip", requires_response=True)],
    )
    assert parsed.text == "I shall wear it."
    assert parsed.actions == [{
        "identifier": "mantella_npc_equip",
        "arguments": {"item": "Golden Saint Shield"},
    }]


def test_streamed_equip_prefix_waits_for_payload():
    parser = actions_parser([make_action("mantella_npc_equip", "Equip", requires_response=True)])
    settings = sentence_generation_settings(None)
    content, remainder = parser.cut_sentence("Equip:", settings)
    assert content is None and remainder == "Equip:"

    content, remainder = parser.cut_sentence(
        "Equip: Stormcloak Cuirass | I shall wear it.", settings
    )
    assert content is not None
    assert content.text == "Equip: Stormcloak Cuirass | I shall wear it."
    assert remainder == ""


def test_action_only_equip_preserves_item_argument():
    parsed = parse(
        "Equip: Ancient Nord Sword",
        [make_action("mantella_npc_equip", "Equip", requires_response=True)],
    )
    assert parsed.text == ""
    assert parsed.actions == [{
        "identifier": "mantella_npc_equip",
        "arguments": {"item": "Ancient Nord Sword"},
    }]


def test_empty_equip_prefix_does_not_create_argumentless_action():
    parsed = parse(
        "Equip:",
        [make_action("mantella_npc_equip", "Equip", requires_response=True)],
    )
    assert parsed.actions == []


def test_action_only_inventory_still_cuts_at_prefix():
    parser = actions_parser([make_action("mantella_npc_inventory", "Inventory")])
    settings = sentence_generation_settings(None)
    content, remainder = parser.cut_sentence("Inventory: trailing", settings)
    assert content is not None and content.text == "Inventory:"
    assert remainder == " trailing"


def test_corrective_parser_preserves_exact_equip_and_action_only_inventory():
    parser = actions_parser([
        make_action("mantella_npc_equip", "Equip", requires_response=True),
        make_action("mantella_npc_inventory", "Inventory"),
    ])
    settings = sentence_generation_settings(None)
    assert parser.parse_corrective_response("Equip: Golden Saint Shield", settings) == [{
        "identifier": "mantella_npc_equip",
        "arguments": {"item": "Golden Saint Shield"},
    }]
    assert parser.parse_corrective_response("Inventory:", settings) == [{
        "identifier": "mantella_npc_inventory"
    }]


def test_corrective_parser_accepts_stable_actor_label_without_rerouting_actor():
    parser = actions_parser([make_action("mantella_npc_equip", "Equip", requires_response=True)])
    result = parser.parse_corrective_response(
        "Wood Elf: Equip: Roughspun Tunic",
        sentence_generation_settings(None),
    )
    assert result == [{
        "identifier": "mantella_npc_equip",
        "arguments": {"item": "Roughspun Tunic"},
    }]
