import pytest

from src.actions.action_authorization import (
    ActionAuthorizationContext,
    ActionTurnLifecycle,
    ActionPolicy,
    action_policy,
)
from src.actions.function_manager import FunctionManager
from src.conversation.action import Action
from src.llm.output.actions_parser import actions_parser
from src.llm.output.output_parser import sentence_generation_settings
from src.llm.sentence_content import SentenceContent, SentenceTypeEnum
from unittest.mock import MagicMock


def context(text: str, turn: int = 1) -> ActionAuthorizationContext:
    return ActionAuthorizationContext.for_player_turn(turn, text, ["actor-a", "actor-b"])


def test_inventory_is_authorized_only_by_the_current_turn():
    assert context("Check your inventory, you're obviously a drug dealer.").authorize("mantella_npc_inventory", "actor-a")[0]
    assert context("Show me your inventory.").authorize("mantella_npc_inventory", "actor-a")[0]
    assert context("Let me see what you're carrying.").authorize("mantella_npc_inventory", "actor-a")[0]
    assert not context("Either you confess and get better, or I leave you.").authorize("mantella_npc_inventory", "actor-a")[0]


def test_polite_inventory_questions_are_current_requests():
    for utterance in (
        "Can you open your inventory?",
        "Could you open your inventory?",
        "Would you open your inventory?",
        "Can I see your inventory?",
        "Could I see what you're carrying?",
    ):
        assert context(utterance).authorize("mantella_npc_inventory", "actor-a")[0]


def test_historical_inventory_mention_does_not_authorize():
    assert not context("You checked your inventory earlier.").authorize("mantella_npc_inventory", "actor-a")[0]
    assert not context("I think you're a drug dealer.").authorize("mantella_npc_inventory", "actor-a")[0]
    assert not context("Don't open your inventory.").authorize("mantella_npc_inventory", "actor-a")[0]
    assert not context("I don't need to see your inventory.").authorize("mantella_npc_inventory", "actor-a")[0]
    assert not context("Could you open your inventory yesterday?").authorize("mantella_npc_inventory", "actor-a")[0]
    assert not context("Why did you open your inventory?").authorize("mantella_npc_inventory", "actor-a")[0]
    assert not context("Can you not open your inventory?").authorize("mantella_npc_inventory", "actor-a")[0]


def test_follow_requires_an_explicit_current_request():
    assert context("Come with us and follow me.").authorize("mantella_npc_follow", "actor-a")[0]
    assert not context("You said you'd follow us.").authorize("mantella_npc_follow", "actor-a")[0]
    assert not context("Don't follow me.").authorize("mantella_npc_follow", "actor-a")[0]
    assert context("Stop following me.").authorize("mantella_npc_unfollow", "actor-a")[0]
    assert context("Can you follow me?").authorize("mantella_npc_follow", "actor-a")[0]
    assert context("Could you come with us?").authorize("mantella_npc_follow", "actor-a")[0]
    assert context("Would you accompany me?").authorize("mantella_npc_follow", "actor-a")[0]
    assert not context("Why are you following me?").authorize("mantella_npc_follow", "actor-a")[0]
    assert not context("Could you ever follow someone like me?").authorize("mantella_npc_follow", "actor-a")[0]


def test_other_explicit_actions_are_current_turn_scoped():
    current = context("Equip the Imperial Shield, then teleport to me and move here.")
    assert current.authorize("mantella_npc_equip", "actor-a", {"item": "Imperial Shield"})[0]
    for identifier in ("mantella_npc_teleport", "mantella_npc_moveto"):
        assert current.authorize(identifier, "actor-a")[0]
    assert not context("That shield looks good; we may need to teleport later.").authorize("mantella_npc_equip", "actor-a")[0]
    assert "mantella_npc_equip" in context("Use the sword and draw the bow.").requested_actions
    assert not context("Don't equip the shield.").authorize("mantella_npc_equip", "actor-a")[0]
    assert "mantella_npc_equip" in context("Can you equip the shield?").requested_actions
    assert "mantella_npc_equip" in context("Could you put on the helmet?").requested_actions
    assert "mantella_npc_equip" in context("Would you use this sword?").requested_actions
    assert not context("You said you could equip that earlier.").authorize("mantella_npc_equip", "actor-a")[0]


def test_equip_correction_clauses_authorize_the_current_command():
    for utterance in (
        "Equip the shield.",
        "Equip the shield now.",
        "You're not actually equipping it, equip the shield.",
        "You still aren't wearing it. Equip the shield.",
        "No, equip the Golden Saint Shield.",
        "Put the shield on now.",
        "Use the shield I just gave you.",
    ):
        assert "mantella_npc_equip" in context(utterance).requested_actions, utterance
    for utterance in (
        "You're not actually wearing the shield.",
        "You said you equipped the shield.",
        "Why didn't you equip the shield?",
        "Don't equip the shield.",
        "You don't need to equip the shield.",
    ):
        assert not context(utterance).authorize("mantella_npc_equip", "actor-a")[0], utterance


def test_live_equip_request_forms_are_current_commands():
    for utterance in (
        "I need you to equip the shield.",
        "I want you to equip the shield.",
        "I want you to equip it.",
        "Please equip the shield.",
        "Please equip it.",
        "Could you equip the shield?",
        "Can you equip the shield?",
        "Put the shield on.",
        "Use the shield.",
        "Ready the shield.",
        "You're not actually equipping it, equip the shield.",
        "You still aren't wearing it. Equip the armor.",
        "No, equip the Golden Saint Shield.",
    ):
        requested = ActionAuthorizationContext.for_player_turn(
            2,
            utterance,
            [("Wood Elf", "actor-a")],
            recent_equip_items=("Golden Saint Shield",),
        )
        assert requested.authorize("mantella_npc_equip", "actor-a", {"item": "Golden Saint Shield"})[0], utterance


def test_live_non_request_equip_forms_remain_rejected():
    for utterance in (
        "You equipped the shield earlier.",
        "Why did you equip the shield?",
        "You're holding a shield.",
        "Don't equip the shield.",
        "You don't need to equip it.",
        "I was thinking about whether you should equip it.",
        "You said you would equip it.",
    ):
        assert not context(utterance).authorize("mantella_npc_equip", "actor-a")[0], utterance


def test_equip_authorizes_only_the_requested_target():
    requested = context("Equip the Golden Saint Shield.")
    assert requested.authorize("mantella_npc_equip", "actor-a", {"item": "Golden Saint Shield"})[0]
    assert requested.authorize("mantella_npc_equip", "actor-a", {"item": "Roughspun Tunic"}) == (False, "equip_target_not_authorized")
    assert requested.authorize("mantella_npc_equip", "actor-a") == (False, "equip_target_missing")
    assert context("Equip your best armor.").authorize(
        "mantella_npc_equip", "actor-a", {"item": "best armor"}
    )[0]


def test_recent_transfer_equip_does_not_allow_an_arbitrary_item_guess():
    requested = context("Equip the armor I just gave you.")
    assert requested.authorize("mantella_npc_equip", "actor-a", {"item": "Roughspun Tunic"}) == (False, "equip_target_missing")


def test_immediate_equip_referent_uses_one_authoritative_recent_transfer():
    requested = ActionAuthorizationContext.for_player_turn(
        2,
        "I want you to equip it.",
        ["actor-a"],
        recent_equip_item="Golden Saint Shield",
    )
    assert requested.authorize(
        "mantella_npc_equip", "actor-a", {"item": "Golden Saint Shield"}
    )[0]
    assert requested.authorize(
        "mantella_npc_equip", "actor-a", {"item": "Roughspun Tunic"}
    )[0] is False


def test_immediate_equip_referent_requires_one_unambiguous_authoritative_item():
    exact = ActionAuthorizationContext.for_player_turn(
        3,
        "Please equip it.",
        [("Wood Elf", "wood-ref")],
        recent_equip_items=("Golden Saint Shield",),
    )
    assert exact.equip_target == "Golden Saint Shield"
    assert exact.authorize("mantella_npc_equip", "wood-ref", {"item": "Golden Saint Shield"})[0]

    ambiguous = ActionAuthorizationContext.for_player_turn(
        3,
        "Please equip it.",
        [("Wood Elf", "wood-ref")],
        recent_equip_items=("Golden Saint Shield", "Steel Sword"),
    )
    assert ambiguous.authorize(
        "mantella_npc_equip", "wood-ref", {"item": "Golden Saint Shield"}
    ) == (False, "equip_target_missing")

    shield_request = ActionAuthorizationContext.for_player_turn(
        3,
        "I need you to equip the shield.",
        [("Wood Elf", "wood-ref")],
        recent_equip_items=("Golden Saint Shield",),
    )
    assert shield_request.equip_target == "Golden Saint Shield"
    assert not shield_request.authorize(
        "mantella_npc_equip", "wood-ref", {"item": "Ebony Shield"}
    )[0]


def test_recent_armor_referent_filters_non_armor_items_but_never_guesses():
    exact = ActionAuthorizationContext.for_player_turn(
        4,
        "Equip the armor I just gave you.",
        [("Wood Elf", "wood-ref")],
        recent_equip_items=("Steel Sword", "Stormcloak Cuirass"),
    )
    assert exact.equip_target == "Stormcloak Cuirass"
    assert exact.authorize("mantella_npc_equip", "wood-ref", {"item": "Stormcloak Cuirass"})[0]

    missing = ActionAuthorizationContext.for_player_turn(
        4, "Equip the armor I just gave you.", [("Wood Elf", "wood-ref")]
    )
    assert missing.authorize(
        "mantella_npc_equip", "wood-ref", {"item": "Roughspun Tunic"}
    ) == (False, "equip_target_missing")


def test_bare_equipment_category_resolves_one_recent_transfer():
    shield = ActionAuthorizationContext.for_player_turn(
        5, "Equip the shield.", [("Wood Elf", "wood-ref")],
        recent_equip_items=("Golden Saint Shield",),
    )
    assert shield.equip_target == "Golden Saint Shield"
    assert shield.authorize(
        "mantella_npc_equip", "wood-ref", {"item": "Golden Saint Shield"}
    )[0]

    armor = ActionAuthorizationContext.for_player_turn(
        5, "Equip the armor.", [("Wood Elf", "wood-ref")],
        recent_equip_items=("Stormcloak Cuirass",),
    )
    assert armor.equip_target == "Stormcloak Cuirass"
    assert armor.authorize(
        "mantella_npc_equip", "wood-ref", {"item": "Stormcloak Cuirass"}
    )[0]


def test_bare_equipment_category_fails_closed_when_ambiguous_or_missing():
    ambiguous = ActionAuthorizationContext.for_player_turn(
        5, "Equip the shield.", [("Wood Elf", "wood-ref")],
        recent_equip_items=("Golden Saint Shield", "Steel Shield"),
    )
    assert ambiguous.authorize(
        "mantella_npc_equip", "wood-ref", {"item": "Golden Saint Shield"}
    ) == (False, "equip_target_missing")

    missing = ActionAuthorizationContext.for_player_turn(
        5, "Equip the armor.", [("Wood Elf", "wood-ref")]
    )
    assert missing.authorize(
        "mantella_npc_equip", "wood-ref", {"item": "Roughspun Tunic"}
    ) == (False, "equip_target_missing")


def test_immediate_unresolved_inventory_followup_is_narrowly_authorized():
    assert ActionAuthorizationContext.for_player_turn(
        2, "No, open it so I can see it.", ["actor-a"], unresolved_actions={"mantella_npc_inventory"}
    ).authorize("mantella_npc_inventory", "actor-a")[0]
    assert not context("No, open it so I can see it.").authorize("mantella_npc_inventory", "actor-a")[0]
    assert not ActionAuthorizationContext.for_player_turn(
        2, "No, open it so I can see it.", ["actor-a"], unresolved_actions={"mantella_npc_equip"}
    ).authorize("mantella_npc_inventory", "actor-a")[0]


def test_move_teleport_wait_and_unfollow_reject_history_and_questions():
    assert context("Move here, then teleport to me.").authorize("mantella_npc_moveto", "actor-a")[0]
    assert context("Move here, then teleport to me.").authorize("mantella_npc_teleport", "actor-a")[0]
    assert action_policy("mantella_npc_wait") == ActionPolicy.EXPLICIT_CURRENT_REQUEST
    assert context("Wait here.").authorize("mantella_npc_wait", "actor-a")[0]
    assert context("Stay here and hold position.").authorize("mantella_npc_wait", "actor-a")[0]
    assert not context("You waited here earlier.").authorize("mantella_npc_wait", "actor-a")[0]
    assert not context("Don't wait here.").authorize("mantella_npc_wait", "actor-a")[0]
    assert not context("Wait, what do you mean?").authorize("mantella_npc_wait", "actor-a")[0]
    assert context("Would you move to me?").authorize("mantella_npc_moveto", "actor-a")[0]
    assert not context("You teleported here earlier.").authorize("mantella_npc_teleport", "actor-a")[0]
    assert not context("Why are you following me?").authorize("mantella_npc_unfollow", "actor-a")[0]


def test_actor_must_be_in_the_immutable_turn_snapshot():
    allowed = context("Check your inventory.").authorize("mantella_npc_inventory", "actor-a")
    rejected = context("Check your inventory.").authorize("mantella_npc_inventory", "actor-c")
    assert allowed[0] is True
    assert rejected == (False, "actor_not_in_turn_snapshot")


def test_reactive_actions_remain_contextual():
    for identifier in ("mantella_npc_offended", "mantella_npc_flee", "mantella_npc_forgiven", "mantella_end_conversation"):
        assert action_policy(identifier) == ActionPolicy.REACTIVE_CONTEXTUAL
        assert context("That is enough.").authorize(identifier, "actor-a")[0]


def test_special_actions_retain_existing_behavior():
    for identifier in ("mantella_npc_inventory_unused", "mantella_npc_vision", "mantella_npc_listen"):
        assert action_policy(identifier) == ActionPolicy.SPECIAL


def test_barter_requires_a_current_commerce_request():
    for utterance in (
        "Show me what you have for sale.",
        "What are you selling?",
        "I'd like to buy something.",
        "Can I sell you some gear?",
    ):
        assert context(utterance).authorize("mantella_npc_barter", "actor-a")[0]
    for utterance in (
        "You sold me this earlier.",
        "I don't want to buy anything.",
        "We're not here to trade.",
        "That sword you sell is impressive.",
    ):
        assert not context(utterance).authorize("mantella_npc_barter", "actor-a")[0]
    assert context("Could you tell me what you're selling?").authorize("mantella_npc_barter", "actor-a")[0]
    assert not context("Can I see your inventory?").authorize("mantella_npc_barter", "actor-a")[0]


def test_barter_authorization_does_not_survive_to_an_unrelated_turn():
    assert context("What are you selling?", turn=1).authorize("mantella_npc_barter", "actor-a")[0]
    assert not context("Either you confess or I leave.", turn=2).authorize("mantella_npc_barter", "actor-a")[0]


def test_look_is_explicit_when_vision_is_on_demand_and_automatic_when_always_on():
    assert context("Look at this mountain.").authorize("mantella_npc_vision", "actor-a")[0]
    assert not context("I saw that mountain earlier.").authorize("mantella_npc_vision", "actor-a")[0]
    automatic = ActionAuthorizationContext.for_player_turn(
        1, "Tell me about the road.", ["actor-a"], automatic_vision=True
    )
    assert automatic.authorize("mantella_npc_vision", "actor-a")[0]


def test_missing_requested_action_is_not_synthesized():
    requested = context("Follow me to Riverwood.")
    # Authorization only records intent; it never creates an action object.
    assert "mantella_npc_follow" in requested.requested_actions
    assert requested.requested_actions - set() == {"mantella_npc_follow"}


def test_turn_context_is_immutable_and_not_reused_for_later_turns():
    first = context("Check your inventory.", turn=1)
    second = context("Either you confess and get better, or I leave you.", turn=2)
    assert first.turn_id == 1
    assert second.turn_id == 2
    assert first.authorize("mantella_npc_inventory", "actor-a")[0]
    assert not second.authorize("mantella_npc_inventory", "actor-a")[0]


def test_stale_generation_and_action_result_continuation_cannot_reauthorize_inventory():
    current = context("Check your inventory.", turn=10)
    assert current.authorize("mantella_npc_inventory", "actor-a")[0]
    assert current.as_stale().authorize("mantella_npc_inventory", "actor-a") == (False, "stale_turn")
    assert not current.for_continuation().authorize("mantella_npc_inventory", "actor-a")[0]


def test_structured_tool_calls_use_the_same_gate(example_characters_pc_to_npc):
    FunctionManager.load_all_actions()
    tool_call = [{"function": {"name": "Inventory", "arguments": '{"source": "Guard"}'}}]
    guard = example_characters_pc_to_npc.get_non_player_characters()[0]
    allowed_context = ActionAuthorizationContext.for_player_turn(
        1, "Show me your inventory.", [(guard.name, guard.ref_id)]
    )
    lifecycle = ActionTurnLifecycle(allowed_context)
    allowed = FunctionManager.parse_function_calls(
        tool_call,
        characters=example_characters_pc_to_npc,
        authorization_context=allowed_context,
        actor_ref_id=guard.ref_id,
        action_lifecycle=lifecycle,
    )
    rejected = FunctionManager.parse_function_calls(
        tool_call,
        characters=example_characters_pc_to_npc,
        authorization_context=ActionAuthorizationContext.for_player_turn(
            2, "Either you confess and get better, or I leave you.", [(guard.name, guard.ref_id)]
        ),
        actor_ref_id=guard.ref_id,
    )
    assert [item["identifier"] for item in allowed] == ["mantella_npc_inventory"]
    assert rejected == []
    assert lifecycle.generated == {("mantella_npc_inventory", guard.ref_id)}
    assert lifecycle.authorized == {("mantella_npc_inventory", guard.ref_id)}


def test_reactive_attack_and_flee_are_not_blocked_by_literal_request_matching():
    current = context("The insult was unforgivable.")
    assert current.authorize("mantella_npc_offended", "actor-a")[0]
    assert current.authorize("mantella_npc_flee", "actor-a")[0]


@pytest.mark.xfail(
    strict=True,
    reason="Known multi-NPC limitation: the addressed-clause scanner misses a second '<name>,' clause after prose",
)
def test_multi_npc_direct_addresses_are_scoped_to_stable_actor_ids():
    current = ActionAuthorizationContext.for_player_turn(
        3,
        "Lydia, equip the shield. Wood Elf, follow me.",
        [("Lydia", "lydia-ref"), ("Wood Elf", "wood-ref")],
        recent_equip_items_by_actor={"lydia-ref": ("Golden Saint Shield",)},
    )
    assert current.authorize("mantella_npc_equip", "lydia-ref", {"item": "Golden Saint Shield"})[0]
    assert not current.authorize("mantella_npc_follow", "lydia-ref")[0]
    assert current.authorize("mantella_npc_follow", "wood-ref")[0]
    assert not current.authorize("mantella_npc_equip", "wood-ref")[0]


def test_multi_npc_equip_target_constraint_is_actor_scoped():
    current = ActionAuthorizationContext.for_player_turn(
        3,
        "Lydia, equip it. Wood Elf, follow me.",
        [("Lydia", "lydia-ref"), ("Wood Elf", "wood-ref")],
        recent_equip_items_by_actor={"lydia-ref": ("Golden Saint Shield",)},
    )
    assert current.authorize(
        "mantella_npc_equip", "lydia-ref", {"item": "Golden Saint Shield"}
    )[0]
    assert not current.authorize(
        "mantella_npc_equip", "lydia-ref", {"item": "Roughspun Tunic"}
    )[0]
    assert not current.authorize(
        "mantella_npc_equip", "wood-ref", {"item": "Golden Saint Shield"}
    )[0]


def test_duplicate_display_name_cannot_select_an_arbitrary_actor():
    current = ActionAuthorizationContext.for_player_turn(
        4,
        "Stormcloak Soldier, follow me.",
        [("Stormcloak Soldier", "actor-a"), ("Stormcloak Soldier", "actor-b")],
    )
    assert not current.authorize("mantella_npc_follow", "actor-a")[0]
    assert not current.authorize("mantella_npc_follow", "actor-b")[0]


def test_one_of_you_does_not_guess_a_target():
    current = ActionAuthorizationContext.for_player_turn(
        5, "One of you follow me.", [("Lydia", "lydia-ref"), ("Wood Elf", "wood-ref")]
    )
    assert not current.authorize("mantella_npc_follow", "lydia-ref")[0]
    assert not current.authorize("mantella_npc_follow", "wood-ref")[0]


def test_action_only_prefix_is_cut_for_the_same_downstream_gate():
    action = Action("mantella_npc_inventory", "Inventory", "Inventory", "", "", False, False, True, True, False)
    speaker = MagicMock()
    settings = sentence_generation_settings(speaker)
    parsed, rest = actions_parser([action]).cut_sentence("Inventory:", settings)
    assert parsed is not None
    assert parsed.text == "Inventory:"
    assert rest == ""
    parsed, _ = actions_parser([action]).modify_sentence_content(parsed, None, settings)
    assert parsed.actions == [{"identifier": "mantella_npc_inventory"}]
    assert context("Can you open your inventory?").authorize(parsed.actions[0]["identifier"], "actor-a")[0]


def test_legacy_equip_prefix_preserves_item_argument():
    action = Action("mantella_npc_equip", "Equip", "Equip", "", "", False, False, True, True, False)
    speaker = MagicMock()
    settings = sentence_generation_settings(speaker)
    parsed, _ = actions_parser([action]).modify_sentence_content(
        SentenceContent(speaker, "Equip: Golden Saint Shield | I have done it.", SentenceTypeEnum.SPEECH, False),
        None,
        settings,
    )
    assert parsed.actions == [{"identifier": "mantella_npc_equip", "arguments": {"item": "Golden Saint Shield"}}]


def test_corrective_parser_preserves_exact_equip_and_action_only_inventory():
    equip = Action("mantella_npc_equip", "Equip", "Equip", "", "", True, True, True, True, False)
    inventory = Action("mantella_npc_inventory", "Inventory", "Inventory", "", "", True, True, True, True, False)
    speaker = MagicMock()
    parser = actions_parser([equip, inventory])
    assert parser.parse_corrective_response(
        "Equip: Golden Saint Shield", sentence_generation_settings(speaker)
    ) == [{"identifier": "mantella_npc_equip", "arguments": {"item": "Golden Saint Shield"}}]
    assert parser.parse_corrective_response(
        "Inventory:", sentence_generation_settings(speaker)
    ) == [{"identifier": "mantella_npc_inventory"}]


def test_successfully_authorized_action_is_not_missing():
    requested = context("Open your inventory.")
    emitted = {("mantella_npc_inventory", "actor-a")}
    assert requested.missing_requested_actions(emitted, "actor-a") == frozenset()
    assert requested.missing_requested_actions(set(), "actor-a") == frozenset({"mantella_npc_inventory"})


def test_lifecycle_diagnostics_separate_rejection_from_missing_generation():
    requested = context("Equip the shield.")
    assert requested.missing_requested_actions(set(), "actor-a") == frozenset({"mantella_npc_equip"})
    assert requested.authorize("mantella_npc_equip", "actor-a", {"item": "Roughspun Tunic"}) == (False, "equip_target_missing")
    # The caller records this as generated/rejected, not missing generation.
    assert requested.missing_requested_actions({("mantella_npc_equip", "actor-a")}, "actor-a") == frozenset()


def test_action_lifecycle_states_are_mutually_exclusive():
    requested = context("Open your inventory.")
    lifecycle = ActionTurnLifecycle(requested)
    assert lifecycle.missing_generated("actor-a") == frozenset({("mantella_npc_inventory", "actor-a")})

    lifecycle.record_generated("mantella_npc_inventory", "actor-a")
    lifecycle.record_rejected("mantella_npc_inventory", "actor-a", "current_turn_not_authorized")
    assert lifecycle.missing_generated("actor-a") == frozenset()
    assert lifecycle.authorized_not_queued() == set()

    dispatched = ActionTurnLifecycle(requested)
    dispatched.record_generated("mantella_npc_inventory", "actor-a")
    dispatched.record_authorized("mantella_npc_inventory", "actor-a")
    assert dispatched.authorized_not_queued() == {("mantella_npc_inventory", "actor-a")}
    dispatched.record_queued("mantella_npc_inventory", "actor-a")
    assert dispatched.authorized_not_queued() == set()
    dispatched.record_protocol_dispatched("mantella_npc_inventory", "actor-a")
    dispatched.record_game_result()
    assert dispatched.game_result_received == {("mantella_npc_inventory", "actor-a")}


def test_correction_prompt_retains_exact_equip_constraint():
    requested = ActionAuthorizationContext.for_player_turn(
        8,
        "Please equip it.",
        [("Wood Elf", "wood-ref")],
        recent_equip_items=("Golden Saint Shield",),
    )
    prompt = requested.corrective_prompt(frozenset({("mantella_npc_equip", "wood-ref")}))
    assert "Authorized Equip item: Golden Saint Shield" in prompt
    assert "Equip: Golden Saint Shield" in prompt


@pytest.mark.parametrize(
    "player_text,owned,expected",
    [
        ("Put your clothes back on.", ("Roughspun Tunic",), "Roughspun Tunic"),
        ("Get dressed.", ("Roughspun Tunic",), "Roughspun Tunic"),
        ("Wear your clothes.", ("Roughspun Tunic",), "Roughspun Tunic"),
        ("Put your armor back on.", ("Stormcloak Cuirass",), "Stormcloak Cuirass"),
        ("Put some armor on.", ("Iron Boots",), "Iron Boots"),
        ("Put your boots on.", ("Iron Boots",), "Iron Boots"),
        ("Wear the tunic.", ("Roughspun Tunic",), "Roughspun Tunic"),
    ],
)
def test_natural_equip_commands_resolve_only_currently_owned_item(player_text, owned, expected):
    requested = ActionAuthorizationContext.for_player_turn(
        30,
        player_text,
        [("Wood Elf", "wood-ref")],
        owned_equip_items_by_actor={"wood-ref": owned},
        authoritative_inventory_actor_refs={"wood-ref"},
    )
    assert requested.requested_actions == frozenset({"mantella_npc_equip"})
    assert requested.equip_target == expected
    assert requested.authorize(
        "mantella_npc_equip", "wood-ref", {"item": expected}
    ) == (True, "authorized")


def test_unresolved_armor_category_accepts_owned_concrete_model_target():
    requested = ActionAuthorizationContext.for_player_turn(
        33,
        "Put your armor on.",
        [("Wood Elf", "wood-ref")],
        owned_equip_items_by_actor={
            "wood-ref": (
                "Stormcloak Cuirass",
                "Steel Soldier Gauntlets",
                "Iron Plate Boots",
                "Roughspun Tunic",
            )
        },
        authoritative_inventory_actor_refs={"wood-ref"},
    )
    assert requested.equip_target == "owned armor"
    assert requested.authorize(
        "mantella_npc_equip", "wood-ref", {"item": "Stormcloak Cuirass"}
    ) == (True, "authorized")


def test_unresolved_armor_category_rejects_removed_or_unowned_target():
    requested = ActionAuthorizationContext.for_player_turn(
        34,
        "Equip your armor.",
        [("Wood Elf", "wood-ref")],
        owned_equip_items_by_actor={"wood-ref": ("Steel Soldier Gauntlets", "Roughspun Tunic")},
        authoritative_inventory_actor_refs={"wood-ref"},
    )
    assert requested.equip_target == "owned armor"
    assert requested.authorize(
        "mantella_npc_equip", "wood-ref", {"item": "Stormcloak Cuirass"}
    ) == (False, "equip_target_not_owned")


def test_unresolved_clothing_category_accepts_owned_tunic():
    requested = ActionAuthorizationContext.for_player_turn(
        35,
        "Get dressed.",
        [("Wood Elf", "wood-ref")],
        owned_equip_items_by_actor={"wood-ref": ("Roughspun Tunic", "Fine Robe")},
        authoritative_inventory_actor_refs={"wood-ref"},
    )
    assert requested.equip_target == "owned clothes"
    assert requested.authorize(
        "mantella_npc_equip", "wood-ref", {"item": "Roughspun Tunic"}
    ) == (True, "authorized")


def test_unresolved_armor_category_rejects_owned_non_armor_item():
    requested = ActionAuthorizationContext.for_player_turn(
        36,
        "Put your armor on.",
        [("Wood Elf", "wood-ref")],
        owned_equip_items_by_actor={"wood-ref": ("Ancient Nord Sword", "Steel Soldier Gauntlets", "Iron Plate Boots")},
        authoritative_inventory_actor_refs={"wood-ref"},
    )
    assert requested.equip_target == "owned armor"
    assert requested.authorize(
        "mantella_npc_equip", "wood-ref", {"item": "Ancient Nord Sword"}
    ) == (False, "equip_target_not_authorized")


def test_exact_equip_target_remains_authorized():
    requested = ActionAuthorizationContext.for_player_turn(
        37,
        "Equip the Golden Saint Shield.",
        [("Wood Elf", "wood-ref")],
        owned_equip_items_by_actor={"wood-ref": ("Golden Saint Shield",)},
        authoritative_inventory_actor_refs={"wood-ref"},
    )
    assert requested.equip_target.casefold() == "golden saint shield"
    assert requested.authorize(
        "mantella_npc_equip", "wood-ref", {"item": "Golden Saint Shield"}
    ) == (True, "authorized")


def test_category_equip_still_rejects_stale_generation_and_wrong_actor():
    requested = ActionAuthorizationContext.for_player_turn(
        38,
        "Put your armor on.",
        [("Wood Elf", "wood-ref"), ("Sven", "sven-ref")],
        owned_equip_items_by_actor={"wood-ref": ("Stormcloak Cuirass",)},
        authoritative_inventory_actor_refs={"wood-ref"},
    )
    args = {"item": "Stormcloak Cuirass"}
    assert requested.as_stale().authorize("mantella_npc_equip", "wood-ref", args) == (False, "stale_turn")
    assert requested.authorize("mantella_npc_equip", "sven-ref", args)[0] is False


def test_equipment_question_does_not_authorize_equip():
    requested = ActionAuthorizationContext.for_player_turn(
        31,
        "Are you wearing armor?",
        [("Wood Elf", "wood-ref")],
        owned_equip_items_by_actor={"wood-ref": ("Roughspun Tunic",)},
        authoritative_inventory_actor_refs={"wood-ref"},
    )
    assert "mantella_npc_equip" not in requested.requested_actions


def test_authoritative_inventory_rejects_removed_exact_item():
    requested = ActionAuthorizationContext.for_player_turn(
        32,
        "Equip your armor.",
        [("Wood Elf", "wood-ref")],
        owned_equip_items_by_actor={"wood-ref": ("Roughspun Tunic",)},
        authoritative_inventory_actor_refs={"wood-ref"},
    )
    assert requested.equip_target == "Roughspun Tunic"
    assert requested.authorize(
        "mantella_npc_equip", "wood-ref", {"item": "Stormcloak Cuirass"}
    ) == (False, "equip_target_not_authorized")
