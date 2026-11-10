from src.conversation.conversation import Conversation
from src.conversation.ingame_event_tidy import tidy_events
from src.llm.messages import UserMessage


def test_unrecognised_events_are_kept_as_they_are():
    events = ["The location is now Whiterun", "Lydia picked up Iron Sword", "Lydia rested on / used a(n) Chair on Stage"]

    assert tidy_events(events) == events


def test_empty_events_are_dropped():
    assert tidy_events(["", "  ", "Lydia equipped Iron Sword"]) == ["Lydia equipped Iron Sword"]


def test_a_single_event_keeps_its_exact_text():
    events = ["Bandit punched the player .", "Lydia is no longer in combat.", "The player casted the spell / consumed Flames"]

    assert tidy_events(events) == events


def test_same_spell_hitting_several_people_becomes_one_line():
    events = ["Yulia hit Tigra with Black Hand", "Yulia hit Kak with Black Hand", "Yulia hit Gorr with Black Hand"]

    assert tidy_events(events) == ["Yulia hit Tigra, Kak and Gorr with Black Hand"]


def test_repeated_hit_on_the_same_person_is_listed_once():
    events = ["Serana hit Kak with Orc Strength", "Serana hit Gorr with Orc Strength", "Serana hit Kak with Orc Strength"]

    assert tidy_events(events) == ["Serana hit Kak and Gorr with Orc Strength"]


def test_hits_by_different_people_or_spells_stay_apart():
    events = ["Yulia hit Gorr with Black Hand", "Kak hit Gorr with Black Hand", "Yulia hit Gorr with Flames"]

    assert tidy_events(events) == events


def test_friendly_spell_used_on_several_people_becomes_one_line():
    events = ["Yulia used MassHealing on Tigra", "Yulia used MassHealing on Kak"]

    assert tidy_events(events) == ["Yulia used MassHealing on Tigra and Kak"]


def test_punches_are_merged():
    assert tidy_events(["Bandit punched Lydia", "Bandit punched the player ."]) == ["Bandit punched Lydia and the player"]


def test_merged_line_stands_where_its_first_event_stood():
    events = ["Yulia hit Tigra with Black Hand", "Lydia equipped Iron Sword", "Yulia hit Kak with Black Hand"]

    assert tidy_events(events) == ["Yulia hit Tigra and Kak with Black Hand", "Lydia equipped Iron Sword"]


def test_spells_cast_by_the_same_person_become_one_line():
    events = ["Yulia casted the spell Black Hand", "Serana casted the spell Conjure Houndmaster", "Yulia casted the spell Heal Cloak", "Yulia casted the spell Black Hand"]

    assert tidy_events(events) == ["Yulia casted the spells Black Hand and Heal Cloak", "Serana casted the spell Conjure Houndmaster"]


def test_spells_cast_by_the_player_become_one_line():
    events = ["The player casted the spell / consumed Flames", "The player casted the spell / consumed Oakflesh"]

    assert tidy_events(events) == ["The player casted the spells / consumed Flames and Oakflesh"]


def test_cast_is_dropped_when_the_events_say_who_was_hit():
    events = ["Serana casted the spell Orc Strength", "Serana casted the spell Conjure Houndmaster", "Serana used Orc Strength on Gorr", "Yulia hit Kak with Black Hand", "Yulia casted the spell Black Hand"]

    assert tidy_events(events) == ["Serana casted the spell Conjure Houndmaster", "Serana used Orc Strength on Gorr", "Yulia hit Kak with Black Hand"]


def test_cast_is_kept_when_someone_else_hit_with_that_spell():
    events = ["Serana casted the spell Flames", "Yulia hit Kak with Flames"]

    assert tidy_events(events) == events


def test_combat_notices_are_merged():
    events = [
        "Serana has entered combat with Cave Bear", "Gorr has entered combat with Cave Bear", "Yulia has entered combat with Wolf",
        "Serana has entered combat with Cave Bear",
        "Serana is no longer in combat.", "Gorr is no longer in combat.",
        "Lydia is now in combat!", "Faendal is now in combat!",
        "Lydia is searching for the player", "Faendal is searching for the player",
    ]

    assert tidy_events(events) == [
        "Serana and Gorr have entered combat with Cave Bear", "Yulia has entered combat with Wolf",
        "Serana and Gorr are no longer in combat.",
        "Lydia and Faendal are now in combat!",
        "Lydia and Faendal are searching for the player",
    ]


def test_someone_back_in_combat_is_not_merged_into_a_line_before_they_left():
    events = ["Serana has entered combat with Cave Bear", "Gorr has entered combat with Cave Bear", "Serana is no longer in combat.", "Serana has entered combat with Cave Bear", "Yulia has entered combat with Cave Bear"]

    assert tidy_events(events) == ["Serana and Gorr have entered combat with Cave Bear", "Serana is no longer in combat.", "Serana and Yulia have entered combat with Cave Bear"]


def test_same_unrecognised_event_twice_in_a_row_is_listed_once():
    events = ["Lydia equipped Iron Sword", "Lydia equipped Iron Sword", "Lydia unequipped Iron Sword", "Lydia equipped Iron Sword"]

    assert tidy_events(events) == ["Lydia equipped Iron Sword", "Lydia unequipped Iron Sword", "Lydia equipped Iron Sword"]


# Corner cases

def test_no_events_gives_no_lines():
    assert tidy_events([]) == []


def test_only_blank_events_gives_no_lines():
    assert tidy_events(["", " ", "\n"]) == []


def test_surrounding_spaces_are_trimmed_so_the_same_hit_still_merges():
    events = ["  Yulia hit Gorr with Flames\n", "Yulia hit Kak with Flames ", "Yulia hit Gorr with Flames"]

    assert tidy_events(events) == ["Yulia hit Gorr and Kak with Flames"]


def test_events_that_are_not_text_are_passed_on_as_they_are():
    marker = object()

    assert tidy_events(["Lydia equipped Iron Sword", marker]) == ["Lydia equipped Iron Sword", marker] # type: ignore[list-item]


def test_the_same_single_hit_repeated_keeps_its_exact_text():
    assert tidy_events(["Bandit punched the player .", "Bandit punched the player ."]) == ["Bandit punched the player ."]


def test_the_same_unrecognised_event_apart_is_kept_both_times():
    events = ["The player took damage.", "Lydia equipped Iron Sword", "The player took damage."]

    assert tidy_events(events) == events


def test_spell_name_with_the_word_with_in_it_stays_whole():
    events = ["Yulia hit Gorr with Strike with Fire", "Yulia hit Kak with Strike with Fire"]

    assert tidy_events(events) == ["Yulia hit Gorr and Kak with Strike with Fire"]


def test_spell_name_with_the_word_on_in_it_stays_whole():
    events = ["Yulia used Hands on Healing on Gorr", "Yulia used Hands on Healing on Kak"]

    assert tidy_events(events) == ["Yulia used Hands on Healing on Gorr and Kak"]


def test_sitting_down_is_not_taken_for_a_spell_used_on_someone():
    events = ["Lydia rested on / used a(n) Chair", "Serana rested on / used a(n) Chair"]

    assert tidy_events(events) == events


def test_harmful_and_friendly_lines_of_the_same_spell_stay_apart():
    events = ["Yulia hit Bandit with Black Hand", "Yulia used Black Hand on Gorr", "Yulia hit Wolf with Black Hand"]

    assert tidy_events(events) == ["Yulia hit Bandit and Wolf with Black Hand", "Yulia used Black Hand on Gorr"]


def test_spell_names_that_differ_only_by_case_are_not_merged():
    events = ["Yulia hit Gorr with Flames", "Yulia hit Kak with flames"]

    assert tidy_events(events) == events


def test_cast_is_dropped_whatever_the_case_of_the_hit():
    assert tidy_events(["Yulia casted the spell Flames", "yulia hit Gorr with flames"]) == ["yulia hit Gorr with flames"]


def test_the_players_cast_is_dropped_when_the_events_say_who_the_player_hit():
    events = ["The player casted the spell / consumed Flames", "The player hit Lydia with Flames"]

    assert tidy_events(events) == ["The player hit Lydia with Flames"]


def test_cast_is_dropped_even_when_the_hit_came_first():
    events = ["Yulia hit Gorr with Flames", "Lydia equipped Iron Sword", "Yulia casted the spell Flames"]

    assert tidy_events(events) == ["Yulia hit Gorr with Flames", "Lydia equipped Iron Sword"]


def test_only_the_covered_spell_is_dropped_from_a_merged_cast_line():
    events = ["Yulia casted the spell Flames", "Yulia casted the spell Oakflesh", "Yulia casted the spell Sparks", "Yulia hit Gorr with Flames"]

    assert tidy_events(events) == ["Yulia casted the spells Oakflesh and Sparks", "Yulia hit Gorr with Flames"]


def test_one_cast_left_after_dropping_keeps_its_exact_text():
    events = ["The player casted the spell / consumed Flames", "The player casted the spell / consumed Healing", "The player hit Lydia with Flames"]

    assert tidy_events(events) == ["The player casted the spell / consumed Healing", "The player hit Lydia with Flames"]


def test_the_players_casts_and_an_npcs_casts_stay_apart():
    events = ["The player casted the spell / consumed Flames", "Lydia casted the spell Healing", "The player casted the spell / consumed Sparks", "Lydia casted the spell Oakflesh"]

    assert tidy_events(events) == ["The player casted the spells / consumed Flames and Sparks", "Lydia casted the spells Healing and Oakflesh"]


def test_someone_affected_twice_is_named_once_in_the_order_first_seen():
    events = ["Yulia hit Kak with Flames", "Yulia hit Gorr with Flames", "Yulia hit Kak with Flames", "Yulia hit Tigra with Flames"]

    assert tidy_events(events) == ["Yulia hit Kak, Gorr and Tigra with Flames"]


def test_caster_hitting_themselves_is_merged_like_anyone_else():
    assert tidy_events(["Yulia hit Yulia with Heal Cloak", "Yulia hit Gorr with Heal Cloak"]) == ["Yulia hit Yulia and Gorr with Heal Cloak"]


def test_punches_by_different_people_stay_apart():
    assert tidy_events(["Bandit punched Lydia", "Thug punched Lydia"]) == ["Bandit punched Lydia", "Thug punched Lydia"]


def test_no_longer_in_combat_with_and_without_a_full_stop_are_merged():
    assert tidy_events(["Lydia is no longer in combat.", "Serana is no longer in combat"]) == ["Lydia and Serana are no longer in combat."]


def test_entering_combat_with_different_enemies_stays_apart():
    events = ["Lydia has entered combat with Cave Bear", "Serana has entered combat with Wolf", "Gorr has entered combat with Cave Bear"]

    assert tidy_events(events) == ["Lydia and Gorr have entered combat with Cave Bear", "Serana has entered combat with Wolf"]


def test_searching_between_two_combat_entries_keeps_them_apart():
    events = ["Serana has entered combat with Cave Bear", "Serana is searching for Cave Bear", "Serana has entered combat with Cave Bear"]

    assert tidy_events(events) == events


def test_someone_else_leaving_combat_does_not_stop_a_merge():
    events = ["Serana has entered combat with Cave Bear", "Lydia is no longer in combat.", "Gorr has entered combat with Cave Bear"]

    assert tidy_events(events) == ["Serana and Gorr have entered combat with Cave Bear", "Lydia is no longer in combat."]


def test_now_in_combat_notices_keep_their_order_per_person():
    events = ["Lydia is now in combat!", "Lydia is no longer in combat.", "Lydia is now in combat!"]

    assert tidy_events(events) == events


def test_combat_line_started_after_a_break_takes_later_entries():
    events = [
        "Serana has entered combat with Cave Bear", "Serana is no longer in combat.", "Serana has entered combat with Cave Bear",
        "Gorr has entered combat with Cave Bear",
    ]

    assert tidy_events(events) == ["Serana has entered combat with Cave Bear", "Serana is no longer in combat.", "Serana and Gorr have entered combat with Cave Bear"]


def test_hits_are_not_kept_apart_by_combat_changes():
    events = ["Yulia hit Gorr with Flames", "Gorr is no longer in combat.", "Yulia hit Kak with Flames"]

    assert tidy_events(events) == ["Yulia hit Gorr and Kak with Flames", "Gorr is no longer in combat."]


def test_several_people_killed_by_the_same_one_become_one_line():
    events = ["Bandit was killed by Serana", "Bandit Outlaw was killed by Serana", "Draugr was killed by Serana"]

    assert tidy_events(events) == ["Bandit, Bandit Outlaw and Draugr were killed by Serana"]


def test_a_single_kill_keeps_its_exact_text():
    events = ["The dragon was killed by the player"]

    assert tidy_events(events) == events


def test_kills_by_different_people_stay_apart():
    events = ["Bandit was killed by Serana", "Draugr was killed by the player", "Bandit Thug was killed by Serana"]

    assert tidy_events(events) == ["Bandit and Bandit Thug were killed by Serana", "Draugr was killed by the player"]


def test_the_same_victim_reported_twice_is_listed_once():
    events = ["The dragon was killed by Serana", "The dragon was killed by Serana"]

    assert tidy_events(events) == ["The dragon was killed by Serana"]


# A participant's death can be reported twice: by the OnDying handler of MantellaTargetListenerScript.psc, and by the
# OnActorKilled handler of MantellaListenerScript.psc when the dead one was already taken out of the conversation.
# Both write the same sentence, so the merging below is what keeps the double out of the request. Keep the two wordings
# identical, or a death starts showing up twice
def test_a_death_reported_twice_with_other_events_between_is_still_listed_once():
    events = [
        "Lydia was killed by Serana",
        "Serana hit Bandit with Iron Sword",
        "Gorr is no longer in combat.",
        "Lydia was killed by Serana",
    ]

    assert tidy_events(events) == ["Lydia was killed by Serana", "Serana hit Bandit with Iron Sword", "Gorr is no longer in combat."]


def test_a_death_without_a_killer_is_kept_as_it_is():
    events = ["Bandit was killed by Serana", "Gorr died", "Draugr was killed by Serana"]

    assert tidy_events(events) == ["Bandit and Draugr were killed by Serana", "Gorr died"]


def test_kills_and_hits_on_the_same_enemy_are_kept_apart():
    events = ["Serana hit The dragon with Firebolt", "The dragon was killed by Serana"]

    assert tidy_events(events) == events


def test_the_input_list_is_not_changed():
    events = ["Yulia hit Gorr with Flames", "Yulia hit Kak with Flames"]

    tidy_events(events)

    assert events == ["Yulia hit Gorr with Flames", "Yulia hit Kak with Flames"]


# With the conversation

def events_sent(conversation: Conversation, events: list[str], max_count_events: int = 5, interrupting: bool = False) -> list[str]:
    context = conversation.context
    context.config.max_count_events = max_count_events
    context.update_context(None, None, events, "", {})
    conversation._Conversation__is_player_interrupting = interrupting
    message = conversation.update_game_events(UserMessage(context.config, "Hello"))
    return message._UserMessage__ingame_events


def test_max_count_events_counts_the_tidied_lines(default_conversation: Conversation):
    events = [f"Serana hit {name} with Orc Strength" for name in ["Gorr", "Kak", "Yulia", "Jenassa", "Rayya", "Minei"]]
    events += ["Lydia equipped Iron Sword"]

    assert events_sent(default_conversation, events, max_count_events=2) == [
        "Serana hit Gorr, Kak, Yulia, Jenassa, Rayya and Minei with Orc Strength",
        "Lydia equipped Iron Sword",
    ]


def test_max_count_events_keeps_the_latest_tidied_lines(default_conversation: Conversation):
    events = ["Lydia equipped Iron Sword", "Yulia hit Gorr with Flames", "Lydia unequipped Iron Sword", "Yulia hit Kak with Flames"]

    assert events_sent(default_conversation, events, max_count_events=2) == ["Yulia hit Gorr and Kak with Flames", "Lydia unequipped Iron Sword"]


def test_interrupting_is_added_after_the_tidied_lines(default_conversation: Conversation):
    events = ["Yulia hit Gorr with Flames", "Yulia hit Kak with Flames"]

    assert events_sent(default_conversation, events, interrupting=True) == ["Yulia hit Gorr and Kak with Flames", "Interrupting..."]


def test_ignored_events_are_filtered_before_the_tidying(default_conversation: Conversation):
    config = default_conversation.context.config
    config.definitions.get_config_value_definition("ingame_events_filter").value = "*Kak*"
    config.update_config_loader_with_changed_config_values()
    events = ["Yulia hit Gorr with Flames", "Yulia hit Kak with Flames", "Yulia hit Tigra with Flames"]

    assert events_sent(default_conversation, events) == ["Yulia hit Gorr and Tigra with Flames"]


def test_events_are_cleared_after_they_are_sent(default_conversation: Conversation):
    events_sent(default_conversation, ["Yulia hit Gorr with Flames"])

    assert default_conversation.context.get_context_ingame_events() == []
