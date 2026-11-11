"""Examples of the requests sent to the Game Master (and the NPC Initiative check), shown in the prompt profile editor.
Each example marks where the chosen prompt goes, so users can see what the model reads around it.

The layouts follow the real requests: the decision model's request as Mantella logs it (format_decision_request in
src/conversation/game_master.py), and the Game Master LLM's system and user messages (GameMaster.choose_next_speaker).
Keep them in step when those requests change."""

import re

# A slot is {{prompt_type}} or {{prompt_type|note}}, e.g. {{skyrim_game_master_decision_npc_criteria|for Lydia}}.
# For a merged prompt, the note starts with the situation, e.g. {{skyrim_game_master_prompt|as Shout}}
SLOT = re.compile(r"\{\{([a-z_]+)(?:\|([^}]*))?\}\}")

DECISION_GROUP = ("With a decision model, in a group conversation (Game Master Mode on)", """===== Scene =====
{{skyrim_game_master_prompt}}

===== Conversation (2 lines) =====
Ragnar: What do you two make of this letter?
Lydia: It's a forgery, my Thane. Hulda would know the seal.

===== Question: next_speaker (choice) =====
{{skyrim_game_master_decision_instructions}}

Criteria:
  - Lydia: {{skyrim_game_master_decision_npc_criteria|for Lydia}}
  - Hulda: {{skyrim_game_master_decision_npc_criteria|for Hulda}}
  - Ragnar: {{skyrim_game_master_decision_player_criteria}}""",
    "After your own line, you are not one of the options: an NPC answers first.")

DECISION_DIRECTOR = ("With a decision model, while you direct the conversation (Director Mode)", """===== Scene =====
{{skyrim_game_master_prompt|as Group conversation, Director Mode}}

===== Conversation (2 lines) =====
(Lydia slams the letter on the table.)
Lydia: It's a forgery. Hulda would know the seal.

===== Question: next_speaker (choice) =====
{{skyrim_game_master_decision_instructions}}

Criteria:
  - Lydia: {{skyrim_game_master_decision_npc_criteria|for Lydia}}
  - Hulda: {{skyrim_game_master_decision_npc_criteria|for Hulda}}""",
    "You are never one of the options while you direct.")

DECISION_SHOUT = ("With a decision model, in a Shout conversation", """===== Scene =====
{{skyrim_game_master_prompt|as Shout}}

===== Conversation (2 lines) =====
Ragnar: Someone took my coin purse.
Lydia: Guard! Ysolda! Did either of you see who did it?

===== Question: next_speaker (choice) =====
{{skyrim_game_master_decision_instructions}}

Criteria:
  - Lydia: {{skyrim_game_master_decision_npc_criteria|for Lydia}}
  - Ragnar: {{skyrim_game_master_decision_player_criteria}}
  - Whiterun Guard: {{skyrim_shout_decision_nearby_criteria|for Whiterun Guard, who is nearby}}
  - Ysolda: {{skyrim_shout_decision_nearby_criteria|for Ysolda, who is nearby}}

===== Question: addressed_1 (noul) =====
Was Lydia's latest line addressed to Whiterun Guard?

Criteria:
  - true: {{skyrim_shout_decision_addressed_criteria|for Whiterun Guard}}
  - false: {{skyrim_shout_decision_not_addressed_criteria|for Whiterun Guard}}

===== Question: addressed_2 (noul) =====
Was Lydia's latest line addressed to Ysolda?

Criteria:
  - true: {{skyrim_shout_decision_addressed_criteria|for Ysolda}}
  - false: {{skyrim_shout_decision_not_addressed_criteria|for Ysolda}}""",
    "One addressed question is asked for each person in the conversation and nearby, except whoever said the line. "
    "People nearby are only options while there is room for someone new. After your own line, you are not one of the options.")

DECISION_AFTER_EVENT = ("With a decision model, right after a Talk, Nearby or Random Event (Shout on)", """===== Scene =====
{{skyrim_game_master_prompt|as Shout}}

===== Conversation (2 lines) =====
Ragnar: Someone took my coin purse.
(A boy darts past Ysolda and drops a coin purse at Lydia's feet.)

===== Question: next_speaker (choice) =====
{{skyrim_game_master_decision_instructions|as Who reacts first to a wheel event}}

Criteria:
  - Lydia: {{skyrim_game_master_decision_npc_criteria|for Lydia}}
  - Ragnar: {{skyrim_game_master_decision_player_criteria|as Who reacts first to a wheel event}}
  - Ysolda: {{skyrim_shout_decision_nearby_criteria|for Ysolda, who is nearby}}

===== Question: addressed_1 (noul) =====
Is Lydia part of what just happened (the last line, in brackets)?

Criteria:
  - true: {{skyrim_shout_decision_event_part_criteria|for Lydia}}
  - false: {{skyrim_shout_decision_event_not_part_criteria|for Lydia}}

===== Question: addressed_2 (noul) =====
Is Ysolda part of what just happened (the last line, in brackets)?

Criteria:
  - true: {{skyrim_shout_decision_event_part_criteria|for Ysolda}}
  - false: {{skyrim_shout_decision_event_not_part_criteria|for Ysolda}}""",
    "In a one-on-one or group conversation without Shout, the scene is the Skyrim Game Master Prompt, nobody nearby is an option, "
    "and the \"part of what just happened\" questions are not asked.")

DECISION_NPC_EVENT = ("With a decision model, in an NPC Event scene you are watching", """===== Scene =====
{{skyrim_game_master_prompt|as Watching an NPC Event}}

{{skyrim_npc_event_wind_down_prompt|only during the last lines before the scene's limit}}

===== Conversation (2 lines) =====
(Nazeem sneers at Ysolda's prices and accuses her of cheating.)
Nazeem: You call this fair? I'll have the guard look at your scales.

===== Question: next_speaker (choice) =====
{{skyrim_game_master_decision_instructions}}

Criteria:
  - Nazeem: {{skyrim_game_master_decision_npc_criteria|for Nazeem}}
  - Ysolda: {{skyrim_game_master_decision_npc_criteria|for Ysolda}}
  - Whiterun Guard: {{skyrim_shout_decision_nearby_criteria|as Watching an NPC Event, for Whiterun Guard, who is nearby}}
  - Ragnar: {{skyrim_shout_decision_nearby_criteria|as Watching an NPC Event, for you, once the NPCs can notice you}}

===== Question: addressed_1 (noul) =====
Was Nazeem's latest line addressed to Ysolda?

Criteria:
  - true: {{skyrim_shout_decision_addressed_criteria|for Ysolda}}
  - false: {{skyrim_shout_decision_not_addressed_criteria|for Ysolda}}

===== Question: addressed_2 (noul) =====
Was Nazeem's latest line addressed to Whiterun Guard?

Criteria:
  - true: {{skyrim_shout_decision_addressed_criteria|for Whiterun Guard}}
  - false: {{skyrim_shout_decision_not_addressed_criteria|for Whiterun Guard}}

===== Question: addressed_3 (noul) =====
Was Nazeem's latest line addressed to Ragnar?

Criteria:
  - true: {{skyrim_shout_decision_addressed_criteria|for you}}
  - false: {{skyrim_shout_decision_not_addressed_criteria|for you}}""",
    "One addressed question is asked for each person in the scene and nearby, except whoever said the line. "
    "Someone nearby who was spoken to joins the scene.")

DECISION_SAY = ("With a decision model, when you use Say (nobody in the conversation yet)", """===== Scene =====
{{skyrim_game_master_prompt|as Saying something to the room}}

===== Conversation (1 lines) =====
Ragnar: Has anyone seen a big grey dog around here?

===== Question: next_speaker (choice) =====
{{skyrim_game_master_decision_instructions}}

Criteria:
  - Whiterun Guard: {{skyrim_shout_decision_nearby_criteria|for Whiterun Guard, who is nearby}}
  - Ysolda: {{skyrim_shout_decision_nearby_criteria|for Ysolda, who is nearby}}
  - Nobody: {{skyrim_shout_decision_nobody_criteria|as Saying something to the room}}

===== Question: addressed_1 (noul) =====
Was Ragnar's latest line addressed to Whiterun Guard?

Criteria:
  - true: {{skyrim_shout_decision_addressed_criteria|for Whiterun Guard}}
  - false: {{skyrim_shout_decision_not_addressed_criteria|for Whiterun Guard}}

===== Question: addressed_2 (noul) =====
Was Ragnar's latest line addressed to Ysolda?

Criteria:
  - true: {{skyrim_shout_decision_addressed_criteria|for Ysolda}}
  - false: {{skyrim_shout_decision_not_addressed_criteria|for Ysolda}}""",
    "")

DECISION_SAY_DIRECTOR = ("With a decision model, when you use Say while you direct (Director Mode)", """===== Scene =====
{{skyrim_game_master_prompt|as Saying something to the room, Director Mode}}

===== Conversation (1 lines) =====
(A big grey dog runs through the market with a stolen ham.)

===== Question: next_speaker (choice) =====
{{skyrim_game_master_decision_instructions}}

Criteria:
  - Whiterun Guard: {{skyrim_shout_decision_nearby_criteria|for Whiterun Guard, who is nearby}}
  - Ysolda: {{skyrim_shout_decision_nearby_criteria|for Ysolda, who is nearby}}
  - Nobody: {{skyrim_shout_decision_nobody_criteria|as Saying something to the room, Director Mode}}

===== Question: addressed_1 (noul) =====
Is Whiterun Guard part of what just happened (the latest scene direction, the last line without a speaker)?

Criteria:
  - true: {{skyrim_shout_decision_event_part_criteria|for Whiterun Guard}}
  - false: {{skyrim_shout_decision_event_not_part_criteria|for Whiterun Guard}}""",
    "Your direction has no speaker, so the question for each person is whether they are part of it, as after a wheel event.")

LLM_FOOTER = 'Reply only with JSON in this format: {"next": "<name>", "reason": "<a few words>"}'
LLM_ALSO_FOOTER = ('Leave "also" empty if there is nobody else.\n'
                   'Reply only with JSON in this format: {"next": "<name>", "also": ["<name>"], "reason": "<a few words>"}')

LLM_GROUP = ("With the Game Master LLM (no decision model), in a group conversation", """----- System message -----
{{skyrim_game_master_prompt}}

----- User message -----
The conversation so far:
Ragnar: What do you two make of this letter?
Lydia: It's a forgery, my Thane. Hulda would know the seal.

Who speaks next? Choose one of: Lydia, Hulda, Ragnar.
""" + LLM_FOOTER, "After your own line, you are not one of the choices.")

LLM_DIRECTOR = ("With the Game Master LLM (no decision model), while you direct the conversation", """----- System message -----
{{skyrim_game_master_prompt|as Group conversation, Director Mode}}

----- User message -----
The conversation so far:
(Lydia slams the letter on the table.)
Lydia: It's a forgery. Hulda would know the seal.

Who speaks next? Choose one of: Lydia, Hulda.
""" + LLM_FOOTER, "")

LLM_SHOUT = ("With the Game Master LLM (no decision model), in a Shout conversation", """----- System message -----
{{skyrim_game_master_prompt|as Shout}}

----- User message -----
The conversation so far:
Ragnar: Someone took my coin purse.
Lydia: Guard! Ysolda! Did either of you see who did it?

Who speaks next? Choose one of: Lydia, Whiterun Guard, Ysolda, Ragnar.
In "also", list everyone else of Whiterun Guard, Ysolda for whom this is true: {{skyrim_shout_decision_addressed_criteria|with "that person" in place of {name}}}
""" + LLM_ALSO_FOOTER, "The \"also\" lines are only there when more than one person could have been meant by the latest line.")

LLM_AFTER_EVENT = ("With the Game Master LLM (no decision model), right after a Talk, Nearby or Random Event (Shout on)", """----- System message -----
{{skyrim_game_master_prompt|as Shout}}

----- User message -----
The conversation so far:
Ragnar: Someone took my coin purse.
(A boy darts past Ysolda and drops a coin purse at Lydia's feet.)

Who speaks next? Choose one of: Lydia, Ysolda, Ragnar.
In "also", list everyone else of Lydia, Ysolda for whom this is true: {{skyrim_shout_decision_event_part_criteria|with "that person" in place of {name}}}
""" + LLM_ALSO_FOOTER, "Without Shout there are no \"also\" lines and nobody nearby is a choice.")

LLM_NPC_EVENT = ("With the Game Master LLM (no decision model), in an NPC Event scene you are watching", """----- System message -----
{{skyrim_game_master_prompt|as Watching an NPC Event}}

{{skyrim_npc_event_wind_down_prompt|only during the last lines before the scene's limit}}

----- User message -----
The conversation so far:
(Nazeem sneers at Ysolda's prices and accuses her of cheating.)
Nazeem: You call this fair? I'll have the guard look at your scales.

Who speaks next? Choose one of: Nazeem, Ysolda, Whiterun Guard, Ragnar.
In "also", list everyone else of Ysolda, Whiterun Guard, Ragnar for whom this is true: {{skyrim_shout_decision_addressed_criteria|with "that person" in place of {name}}}
""" + LLM_ALSO_FOOTER, "You (Ragnar here) are only a choice once the NPCs can notice you. The wind-down text is also added to the prompt of the NPC who speaks.")

LLM_SAY = ("With the Game Master LLM (no decision model), when you use Say", """----- System message -----
{{skyrim_game_master_prompt|as Saying something to the room}}

----- User message -----
The conversation so far:
Ragnar: Has anyone seen a big grey dog around here?

Who speaks next? Choose one of: Whiterun Guard, Ysolda, Nobody.
In "also", list everyone else of Whiterun Guard, Ysolda for whom this is true: {{skyrim_shout_decision_addressed_criteria|with "that person" in place of {name}}}
""" + LLM_ALSO_FOOTER, "The \"also\" lines are only there when more than one person is nearby.")

INITIATIVE_DECISION = ("With a decision model", """===== Scene =====
(empty)

===== Conversation (0 lines) =====

===== Question: npc_initiative (choice) =====
{{skyrim_npc_initiative_decision_instructions|with the NPCs' bios and memories filled in}}

Criteria:
  - Lydia: {{skyrim_npc_initiative_decision_npc_criteria|for Lydia}}
  - Ysolda: {{skyrim_npc_initiative_decision_npc_criteria|for Ysolda}}
  - Nobody: {{skyrim_npc_initiative_decision_nobody_criteria}}""", "")

INITIATIVE_LLM = ("With the Game Master LLM (no decision model)", """----- System message -----
{{skyrim_npc_initiative_decision_instructions|with the NPCs' bios and memories filled in}}

The options are:
- Lydia: {{skyrim_npc_initiative_decision_npc_criteria|for Lydia}}
- Ysolda: {{skyrim_npc_initiative_decision_npc_criteria|for Ysolda}}
- Nobody: {{skyrim_npc_initiative_decision_nobody_criteria}}

----- User message -----
Choose one of: Lydia, Ysolda, Nobody.
Reply only with JSON in this format: {"next": "<option>", "reason": "<a few words>"}""", "")

# The examples shown for each prompt type that goes into a Game Master request
EXAMPLES: dict[str, list[tuple[str, str, str]]] = {
    "skyrim_game_master_prompt": [DECISION_GROUP, LLM_GROUP, LLM_DIRECTOR, LLM_SHOUT, LLM_SAY, LLM_NPC_EVENT],
    "skyrim_game_master_decision_instructions": [DECISION_GROUP, DECISION_SHOUT, DECISION_AFTER_EVENT],
    "skyrim_game_master_decision_npc_criteria": [DECISION_GROUP, DECISION_SHOUT],
    "skyrim_game_master_decision_player_criteria": [DECISION_GROUP, DECISION_SHOUT, DECISION_AFTER_EVENT],
    "skyrim_npc_initiative_decision_instructions": [INITIATIVE_DECISION, INITIATIVE_LLM],
    "skyrim_npc_initiative_decision_npc_criteria": [INITIATIVE_DECISION, INITIATIVE_LLM],
    "skyrim_npc_initiative_decision_nobody_criteria": [INITIATIVE_DECISION, INITIATIVE_LLM],
    "skyrim_npc_event_wind_down_prompt": [DECISION_NPC_EVENT, LLM_NPC_EVENT],
    "skyrim_shout_decision_nearby_criteria": [DECISION_SHOUT, DECISION_SAY, DECISION_NPC_EVENT],
    "skyrim_shout_decision_addressed_criteria": [DECISION_SHOUT, LLM_SHOUT],
    "skyrim_shout_decision_not_addressed_criteria": [DECISION_SHOUT],
    "skyrim_shout_decision_event_part_criteria": [DECISION_AFTER_EVENT, LLM_AFTER_EVENT, DECISION_SAY_DIRECTOR],
    "skyrim_shout_decision_event_not_part_criteria": [DECISION_AFTER_EVENT, DECISION_SAY_DIRECTOR],
    "skyrim_shout_decision_nobody_criteria": [DECISION_SAY, DECISION_SAY_DIRECTOR],
}


def render_example(template: str, prompt_type: str, display_names: dict[str, str]) -> str:
    """The example with the chosen prompt marked, and the other prompts named in brackets"""
    def fill(match: re.Match) -> str:
        slot_type, note = match.group(1), match.group(2)
        suffix = f" ({note})" if note else ""
        if slot_type == prompt_type:
            return f">>> THIS PROMPT{suffix} <<<"
        return f"[{display_names.get(slot_type, slot_type)}{suffix}]"
    return SLOT.sub(fill, template)


def get_request_examples_markdown(prompt_type: str, display_names: dict[str, str]) -> str:
    """Markdown with each example request for a prompt type, the prompt's place marked. Empty for prompt types that are not part of a Game Master request"""
    examples = EXAMPLES.get(prompt_type)
    if not examples:
        return ""
    parts = ["**Where it goes in the request.** `>>> THIS PROMPT <<<` marks this prompt, other prompts are named in [brackets]. "
             "The names and lines are only an example."]
    for title, template, note in examples:
        parts.append(f"*{title}:*\n\n```text\n{render_example(template, prompt_type, display_names)}\n```")
        if note:
            parts.append(note)
    return "\n\n".join(parts)
