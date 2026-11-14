from enum import Enum, auto
from src.config.config_value_constraint import ConfigValueConstraint, ConfigValueConstraintResult
from src.config.types.config_value import ConfigValue, ConfigValueTag
from src.config.types.config_value_bool import ConfigValueBool
from src.config.types.config_value_int import ConfigValueInt
from src.config.types.config_value_multi_selection import ConfigValueMultiSelection
from src.config.types.config_value_selection import ConfigValueSelection


class WhoMustSpeakEnum(Enum):
    """Who has to say something before the player's turn (or before a watched NPC Event ends). Several can be ticked. See the Conversation page"""
    EVERYONE = auto()
    YOU_TALK_TO = auto()
    NPC_TALKS_TO = auto()
    NOBODY = auto()

    @property
    def display_name(self) -> str:
        return {
            self.EVERYONE: "Everyone in the conversation",
            self.YOU_TALK_TO: "Anyone you talk to",
            self.NPC_TALKS_TO: "Anyone an NPC talks to",
            self.NOBODY: "Nobody in particular",
        }[self]


class WhoAnswersFirstEnum(Enum):
    """Who gives the first replies after someone is talked to: by the player (or an event or direction), or by an NPC"""
    ANSWER_NEXT = auto()
    EACH_IN_TURN = auto()
    GAME_MASTER = auto()

    @property
    def display_name(self) -> str:
        return {
            self.ANSWER_NEXT: "They answer next",
            self.EACH_IN_TURN: "Each answers in turn",
            self.GAME_MASTER: "The Game Master decides",
        }[self]


class AtReplyLimitEnum(Enum):
    """Who of the people who still have to speak still does once the NPCs reach the reply limit"""
    NOT_ANSWERED_YOU = auto() # Drops the people who only owe an NPC an answer
    EVERYONE_LEFT = auto() # Drops nobody
    NOBODY = auto() # Drops everyone: the player's turn now

    @property
    def display_name(self) -> str:
        return {
            self.NOT_ANSWERED_YOU: "Only people who haven't answered you yet",
            self.EVERYONE_LEFT: "Everyone who still has to speak",
            self.NOBODY: "Nobody, it's your turn now",
        }[self]


class NewcomersRememberEnum(Enum):
    """What someone who joins by shouting heard before they joined"""
    SINCE_SHOUT = 0
    LAST_LINE = 1
    EVERYTHING = 2

    @property
    def display_name(self) -> str:
        return {
            self.SINCE_SHOUT: "Since Shout",
            self.LAST_LINE: "Last Line",
            self.EVERYTHING: "Everything",
        }[self]


CONVERSATION_PAGE = "Conversation" # The UI page these settings are shown on, below the live conversation editor

# The kinds of conversation a turn of NPC replies can belong to, as used in the setting keys
GROUP = "group_conversation"
SHOUT = "shout"
DIRECTOR = "director"
CONVERSATION_EVENT = "conversation_event"
NEARBY_EVENT = "nearby_event"
RANDOM_EVENT = "random_event"
NPC_EVENT = "npc_event"
EVENT_KINDS = {"conversation": CONVERSATION_EVENT, "nearby": NEARBY_EVENT, "random": RANDOM_EVENT}
TALK_KINDS = [GROUP, SHOUT, DIRECTOR, CONVERSATION_EVENT, NEARBY_EVENT, RANDOM_EVENT, NPC_EVENT] # Each has a "Use its own settings" switch
SHARED = "" # The shared set of talk settings, in the All Conversations section. Used by every kind whose switch is off

# The talk settings of one set. A kind's own set has the kind in front, e.g. shout_who_must_speak
WHO_MUST_SPEAK = "who_must_speak"
WHEN_YOU_TALK = "when_you_talk_to_someone"
WHEN_NPC_TALKS = "when_an_npc_talks_to_someone"
AT_REPLY_LIMIT = "who_still_speaks_at_reply_limit"
REPLIES_IN_BETWEEN = "replies_in_between"
EXTRA_ROUNDS = "extra_rounds"
TALK_SETTINGS = [WHO_MUST_SPEAK, WHEN_YOU_TALK, WHEN_NPC_TALKS, AT_REPLY_LIMIT, REPLIES_IN_BETWEEN, EXTRA_ROUNDS]

DEFAULT_MOST_REPLIES = 100
DEFAULT_MAX_ANSWERING = 5
MAX_REPLIES_IN_BETWEEN = 29 # Never more than the reply limit minus 1 when used, and Max NPC Turns per Direction goes up to 30
MAX_EXTRA_ROUNDS = 20 # Each round takes at least one person off, and nobody new is added after the reply limit: in practice no limit


def talk_key(kind: str, setting: str) -> str:
    """The key of a talk setting: the shared set's (kind SHARED), or a kind's own"""
    return f"{kind}_{setting}" if kind else setting


def use_own_key(kind: str) -> str:
    return f"{kind}_use_own_talk_settings"


def most_replies_identifier(situation: str) -> str:
    return f"{situation}_most_replies_per_person"


# Each has its own Max NPC Turns per Player Turn. Director Mode (Max NPC Turns per Direction) and the watched NPC Event (Max Lines Without Player) have their own kind of limit
MAX_NPC_TURNS_KINDS = [GROUP, SHOUT, CONVERSATION_EVENT, NEARBY_EVENT, RANDOM_EVENT]
DEFAULT_MAX_NPC_TURNS = 3


def max_npc_turns_identifier(kind: str) -> str:
    return f"{kind}_max_npc_turns"


def default_talk_settings(kind: str) -> dict[str, object]:
    """The defaults of a set of talk settings, by setting. The watched NPC Event's own set: nobody in particular has to speak, and the Game Master
    picks who answers an NPC"""
    defaults: dict[str, object] = {
        WHO_MUST_SPEAK: [WhoMustSpeakEnum.YOU_TALK_TO],
        WHEN_YOU_TALK: WhoAnswersFirstEnum.ANSWER_NEXT,
        WHEN_NPC_TALKS: WhoAnswersFirstEnum.ANSWER_NEXT,
        AT_REPLY_LIMIT: AtReplyLimitEnum.NOT_ANSWERED_YOU,
        REPLIES_IN_BETWEEN: 1,
        EXTRA_ROUNDS: 1,
    }
    if kind == NPC_EVENT:
        defaults[WHO_MUST_SPEAK] = [WhoMustSpeakEnum.NOBODY]
        defaults[WHEN_NPC_TALKS] = WhoAnswersFirstEnum.GAME_MASTER
    return defaults


def default_uses_own_settings(kind: str) -> bool:
    return kind == NPC_EVENT


def must_speak_options(kind: str) -> list[WhoMustSpeakEnum]:
    """The tick boxes a set offers. A watched NPC Event has nobody "you" talk to"""
    return [option for option in WhoMustSpeakEnum if not (kind == NPC_EVENT and option == WhoMustSpeakEnum.YOU_TALK_TO)]


def must_speak_problem(ticked: list[WhoMustSpeakEnum]) -> str:
    """Why a set of ticked boxes for "Who must speak before your turn" can't be saved. Empty if it can"""
    if not ticked:
        return "Tick at least one box."
    if WhoMustSpeakEnum.NOBODY in ticked and len(ticked) > 1:
        return f'"{WhoMustSpeakEnum.NOBODY.display_name}" can\'t be ticked with any other box.'
    if WhoMustSpeakEnum.EVERYONE in ticked and WhoMustSpeakEnum.YOU_TALK_TO in ticked:
        return (f'"{WhoMustSpeakEnum.EVERYONE.display_name}" and "{WhoMustSpeakEnum.YOU_TALK_TO.display_name}" can\'t be ticked together: '
                "everyone you could talk to is already included.")
    return ""


def resolve_ticks(before: list[str], after: list[str]) -> list[str]:
    """The boxes of "Who must speak before your turn" that stay ticked after a click: a box that can't go with one already ticked unticks it,
    and the last box can't be unticked. By display name, in the order of the options"""
    names = {option.display_name: option for option in WhoMustSpeakEnum}
    old = [names[name] for name in before if name in names]
    new = [names[name] for name in after if name in names]
    ticked = [option for option in new if option not in old]
    result = list(new)
    for option in ticked:
        if option == WhoMustSpeakEnum.NOBODY:
            result = [WhoMustSpeakEnum.NOBODY]
        else:
            result = [o for o in result if o != WhoMustSpeakEnum.NOBODY]
            if option == WhoMustSpeakEnum.EVERYONE:
                result = [o for o in result if o != WhoMustSpeakEnum.YOU_TALK_TO]
            elif option == WhoMustSpeakEnum.YOU_TALK_TO:
                result = [o for o in result if o != WhoMustSpeakEnum.EVERYONE]
    if not result:
        result = old # The last box stays ticked
    return [option.display_name for option in WhoMustSpeakEnum if option in result]


def greyed_choices(must_speak: list[str], at_reply_limit: str, extra_rounds: int | float | None) -> dict[str, bool]:
    """Which talk settings can't change anything with the others as they are, so the page greys them out (they stay visible).
    By display names: must_speak the ticked boxes, at_reply_limit the picked option of "who still speaks"

    Returns:
        dict[str, bool]: for AT_REPLY_LIMIT, REPLIES_IN_BETWEEN and EXTRA_ROUNDS whether the whole setting is greyed.
            Nothing greys the setting that greyed it, so nothing can get stuck
    """
    nobody = WhoMustSpeakEnum.NOBODY.display_name in must_speak
    hard_cutoff = at_reply_limit == AtReplyLimitEnum.NOBODY.display_name
    no_rounds = extra_rounds is not None and int(extra_rounds) <= 0
    return {
        AT_REPLY_LIMIT: nobody, # Nobody has to speak, so nobody is left at the reply limit
        EXTRA_ROUNDS: nobody or hard_cutoff,
        REPLIES_IN_BETWEEN: nobody or hard_cutoff or no_rounds,
    }


def still_to_speak_by_box(kind: str) -> dict[WhoMustSpeakEnum, str]:
    """Who still has to speak because of each tick box of "Who must speak", worded for the kind of conversation"""
    you = {DIRECTOR: "everyone your direction is about who hasn't spoken yet"}.get(
        kind, "everyone the event is about who hasn't spoken yet" if kind in EVENT_KINDS.values() else "everyone you spoke to who hasn't answered you yet")
    return {
        WhoMustSpeakEnum.YOU_TALK_TO: you,
        WhoMustSpeakEnum.NPC_TALKS_TO: "everyone an NPC spoke to who hasn't answered that NPC yet",
        WhoMustSpeakEnum.EVERYONE: f"every NPC in the {'scene' if kind == NPC_EVENT else 'conversation'} who hasn't said anything yet",
    }


def who_still_speaks_now(kind: str, must_speak: list[str], at_reply_limit: str) -> str:
    """Who of the people who still have to speak still gets a turn at the limit, with these boxes ticked and this choice picked (by display names).
    Shown under the choices, so the page says who "everyone" is right now. Empty for "Nobody, it's your turn now", which says it itself"""
    if at_reply_limit == AtReplyLimitEnum.NOBODY.display_name:
        return ""
    by_box = still_to_speak_by_box(kind)
    ticked = [option for option in WhoMustSpeakEnum if option.display_name in must_speak and option in by_box]
    if at_reply_limit == AtReplyLimitEnum.NOT_ANSWERED_YOU.display_name:
        ticked = [option for option in ticked if option != WhoMustSpeakEnum.NPC_TALKS_TO] # Only owed to an NPC: dropped at the limit
    who = ", and ".join(by_box[option] for option in ticked) or "nobody"
    return f"Right now, with the boxes ticked above: {who}."


class MustSpeakConstraint(ConfigValueConstraint[list[str]]):
    """The ticked boxes of "Who must speak before your turn" go together"""
    def __init__(self) -> None:
        super().__init__(None)

    def apply_constraint(self, value_to_apply_to: list[str]) -> ConfigValueConstraintResult:
        names = {option.display_name: option for option in WhoMustSpeakEnum}
        problem = must_speak_problem([names[name] for name in value_to_apply_to if name in names])
        return ConfigValueConstraintResult(problem) if problem else ConfigValueConstraintResult()


def _words(kind: str) -> dict[str, str]:
    """How the talk settings of a set are worded for its kind of conversation"""
    if kind == DIRECTOR:
        return {"turn": "before you direct again", "limit": "Max NPC Turns per Direction", "you": "you talk to",
                "you_note": " In Director Mode, the people your direction is about count as the people you talk to.", "back": "you can direct again"}
    if kind in EVENT_KINDS.values():
        return {"turn": "before your turn", "limit": "Max NPC Turns per Player Turn", "you": "you talk to",
                "you_note": " After an event, the people the event is about count as the people you talk to.", "back": "it's your turn"}
    if kind == NPC_EVENT:
        return {"turn": "before the scene ends", "limit": "Max Lines Without Player", "you": "", "you_note": "", "back": "the scene ends"}
    if kind == SHARED:
        return {"turn": "before your turn", "limit": "Max NPC Turns per Player Turn", "you": "you talk to",
                "you_note": " In Director Mode, that is the people your direction is about. After an event, the people the event is about.",
                "back": "it's your turn"}
    return {"turn": "before your turn", "limit": "Max NPC Turns per Player Turn", "you": "you talk to", "you_note": "", "back": "it's your turn"}


SHARED_LIMIT_NOTE = ("Max NPC Turns per Player Turn is the one in the section of each kind of conversation: Group Conversation, Shout, and each event. "
                     "Director Mode uses Max NPC Turns per Direction instead, and a watched NPC Event Max Lines Without Player.")
EVENT_LIMIT_NOTE = "Max NPC Turns per Player Turn is this event's own, below, also in Director Mode."


class ConversationDefinitions:
    """The Conversation page: who speaks when in Game Master Mode, and the Shout and event options the game only sends to Mantella"""

    TALK_LEVEL_DOCS_URL = "https://github.com/dreaminalife/Mantella/blob/personal_use/FEATURES_README.md#talk-level"
    PAGE_DESCRIPTION = f"""### Conversation Settings
One section for all conversations, then one for each kind of conversation. Click a section's title to open it.
How the talk settings work, and what happens when the NPCs reach Max NPC Turns: [Talk Level]({TALK_LEVEL_DOCS_URL})"""

    ALL_CONVERSATIONS_DESCRIPTION = ("Settings that more than one kind of conversation uses. Below Game Master Spoken To Threshold are the talk settings every kind of conversation "
                                     "uses, unless its own section has \"Use its own settings\" on.")

    @staticmethod
    def get_use_own_settings_config_value(kind: str) -> ConfigValue:
        description = """Off: this kind of conversation uses the talk settings in the All Conversations section.
On: it uses its own, which appear below while this is on."""
        return ConfigValueBool(use_own_key(kind), "Use its own settings", description, default_uses_own_settings(kind))

    @staticmethod
    def get_talk_config_values(kind: str) -> list[ConfigValue]:
        """The talk settings of one set: the shared one (kind SHARED) or a kind's own, worded for it. A watched NPC Event's own set leaves out
        what is about "you"

        Each set's settings appear only while its kind's "Use its own settings" switch is on (shown_when)"""
        words = _words(kind)
        shown_when = use_own_key(kind) if kind else None
        defaults = default_talk_settings(kind)
        limit_note = "\n" + SHARED_LIMIT_NOTE if kind == SHARED else "\n" + EVENT_LIMIT_NOTE if kind in EVENT_KINDS.values() else ""
        values: list[ConfigValue] = []

        options = must_speak_options(kind)
        option_lines = {
            WhoMustSpeakEnum.EVERYONE: f"every NPC in the conversation says something {words['turn']}.",
            WhoMustSpeakEnum.YOU_TALK_TO: f"everyone {words['you']} answers you {words['turn']}.{words['you_note']}",
            WhoMustSpeakEnum.NPC_TALKS_TO: f"when an NPC talks to someone, that person answers {words['turn']}.",
            WhoMustSpeakEnum.NOBODY: "nobody is guaranteed to speak. Who answers depends on the two settings below.",
        }
        together = ('"Nobody in particular" can\'t be ticked with the others, and "Everyone in the conversation" can\'t be ticked with "Anyone you talk to": '
                    "ticking one unticks the other.") if kind != NPC_EVENT else '"Nobody in particular" can\'t be ticked with the others: ticking one unticks the other.'
        description = (f"Who has to say something {words['turn']}. Tick one or more:\n"
                       + "\n".join(f"- {option.display_name}: {option_lines[option]}" for option in options)
                       + f"\n{together}\nMost Replies per Person still wins: someone who has reached it doesn't have to speak.")
        if kind == SHARED:
            description += "\n" + SHARED_LIMIT_NOTE
        must_speak = ConfigValueMultiSelection(talk_key(kind, WHO_MUST_SPEAK), f"Who must speak {words['turn']}", description,
                                               [option.display_name for option in defaults[WHO_MUST_SPEAK]], [option.display_name for option in options], # type: ignore
                                               constraints=[MustSpeakConstraint()], tags=[ConfigValueTag.tick_boxes], resolve_ticks=resolve_ticks)
        must_speak.shown_when = shown_when
        values.append(must_speak)

        first = "Only the first replies are set this way. After them, the Game Master picks freely, also people who already spoke."
        if kind != NPC_EVENT:
            sentences = {
                WhoAnswersFirstEnum.ANSWER_NEXT: f"one of the people {words['you']} replies first.",
                WhoAnswersFirstEnum.EACH_IN_TURN: f"everyone {words['you']} replies first, one after another, once each.",
                WhoAnswersFirstEnum.GAME_MASTER: "the Game Master picks who replies, in any order.",
            }
            description = (f"Who replies first after you talk to one or more people.{words['you_note']} {first}\n"
                           + "\n".join(f"- {option.display_name}: {sentence}" for option, sentence in sentences.items())
                           + f"\nWhether they have to reply {words['turn']} is set by \"Who must speak {words['turn']}\".")
            values.append(ConversationDefinitions.__answers_first(kind, WHEN_YOU_TALK, "When you talk to someone", description, sentences,
                                                                  defaults[WHEN_YOU_TALK], shown_when)) # type: ignore
        sentences = {
            WhoAnswersFirstEnum.ANSWER_NEXT: "one of the people the NPC talked to replies next.",
            WhoAnswersFirstEnum.EACH_IN_TURN: "everyone the NPC talked to replies next, one after another, once each. Anyone still waiting their turn goes first.",
            WhoAnswersFirstEnum.GAME_MASTER: "the Game Master picks who replies, in any order.",
        }
        description = (f"Who replies first after an NPC talks to one or more people. {first}\n"
                       + "\n".join(f"- {option.display_name}: {sentence}" for option, sentence in sentences.items()))
        if kind != NPC_EVENT:
            description += ("\nIf people you talked to are still waiting their turn (Each answers in turn), they go first, and an NPC's \"They answer next\" "
                            "is forgotten.")
        description += f"\nTo make sure the people an NPC talks to answer, tick \"Anyone an NPC talks to\" above."
        values.append(ConversationDefinitions.__answers_first(kind, WHEN_NPC_TALKS, "When an NPC talks to someone", description, sentences,
                                                              defaults[WHEN_NPC_TALKS], shown_when)) # type: ignore

        reached = "When the scene reaches" if kind == NPC_EVENT else "When the NPCs reach"
        labels = {
            AtReplyLimitEnum.NOT_ANSWERED_YOU: "Only people who haven't spoken yet" if kind == NPC_EVENT else AtReplyLimitEnum.NOT_ANSWERED_YOU.display_name,
            AtReplyLimitEnum.EVERYONE_LEFT: AtReplyLimitEnum.EVERYONE_LEFT.display_name,
            AtReplyLimitEnum.NOBODY: {DIRECTOR: "Nobody, you can direct again now", NPC_EVENT: "Nobody, the scene ends now"}.get(kind, AtReplyLimitEnum.NOBODY.display_name),
        }
        not_answered = ("people who still have to speak because of \"Everyone in the conversation\" speak; people an NPC talked to don't."
                        if kind == NPC_EVENT else "people who still owe you an answer speak; people who only owe an NPC an answer don't.")
        sentences = {
            AtReplyLimitEnum.NOT_ANSWERED_YOU: f"{not_answered} Unless \"Anyone an NPC talks to\" is ticked, this works like \"Everyone who still has to speak\".",
            AtReplyLimitEnum.EVERYONE_LEFT: "nobody is dropped: everyone still waiting to speak gets a turn in the extra rounds (see \"Replies in between\" "
                                            "and \"Extra rounds\").",
            AtReplyLimitEnum.NOBODY: f"nobody else speaks: {words['back']} right away.",
        }
        by_box = still_to_speak_by_box(kind)
        description = (f"Once the NPCs have replied {words['limit']} times in a row, who of the people who still have to speak still gets to.\n"
                       + "\n".join(f"- {labels[option]}: {sentence}" for option, sentence in sentences.items())
                       + f"\nWho still has to speak depends on the boxes ticked in \"Who must speak {words['turn']}\":\n"
                       + "\n".join(f"- {option.display_name}: {by_box[option]}." for option in must_speak_options(kind) if option in by_box)
                       + "\nWith more than one box ticked, it's all of these together. Nobody else, and nobody who has reached Most Replies per Person. "
                       "The line under the choices says who that is with the boxes ticked now."
                       + "\nGreyed out when \"Nobody in particular\" is ticked: nobody is left who has to speak.")
        description += limit_note
        at_limit = ConfigValueSelection(talk_key(kind, AT_REPLY_LIMIT), f"{reached} {words['limit']}, who still speaks", description,
                                        defaults[AT_REPLY_LIMIT].display_name, [option.display_name for option in AtReplyLimitEnum], # type: ignore
                                        corresponding_enums=list(AtReplyLimitEnum), tags=[ConfigValueTag.radio_buttons],
                                        option_descriptions={option.display_name: sentence[0].upper() + sentence[1:] for option, sentence in sentences.items()},
                                        option_labels={option.display_name: labels[option] for option in AtReplyLimitEnum if labels[option] != option.display_name})
        at_limit.shown_when = shown_when
        values.append(at_limit)

        description = (f"Once the NPCs reach {words['limit']}, the people who still have to speak get their turn one at a time. "
                       "This is how many other NPCs may reply after each of them, before the next one speaks. "
                       "0 means they speak one after another, and nobody replies to them.\n"
                       f"It is never more than {words['limit']} minus 1, so one round is never longer than {words['limit']}.\n"
                       "Greyed out when it can't change anything: \"Nobody in particular\" is ticked, nobody still speaks, or Extra rounds is 0." + limit_note)
        between = ConfigValueInt(talk_key(kind, REPLIES_IN_BETWEEN), "Replies in between", description, defaults[REPLIES_IN_BETWEEN], # type: ignore
                                 0, MAX_REPLIES_IN_BETWEEN, tags=[ConfigValueTag.share_row])
        between.shown_when = shown_when
        values.append(between)

        description = (f"Once the NPCs reach {words['limit']}, the people who still have to speak get extra rounds. In each round, one of them speaks, "
                       "then up to \"Replies in between\" other NPCs reply. If one of those replies comes from someone who still has to speak, that counts as "
                       f"their turn too. This is the most rounds there can be. When they run out, anyone who hasn't spoken yet doesn't speak, and {words['back']}.\n"
                       f"0 means no extra rounds: {words['back']} as soon as the NPCs reach {words['limit']}. Each round takes at least one person off, "
                       f"so {MAX_EXTRA_ROUNDS} is the same as no limit.\n"
                       "Greyed out when it can't change anything: \"Nobody in particular\" is ticked, or nobody still speaks." + limit_note)
        rounds = ConfigValueInt(talk_key(kind, EXTRA_ROUNDS), "Extra rounds", description, defaults[EXTRA_ROUNDS], 0, MAX_EXTRA_ROUNDS, # type: ignore
                                tags=[ConfigValueTag.share_row])
        rounds.shown_when = shown_when
        values.append(rounds)
        return values

    @staticmethod
    def __answers_first(kind: str, setting: str, label: str, description: str, sentences: dict[WhoAnswersFirstEnum, str], default: WhoAnswersFirstEnum,
                        shown_when: str | None) -> ConfigValue:
        value = ConfigValueSelection(talk_key(kind, setting), label, description, default.display_name, [option.display_name for option in WhoAnswersFirstEnum],
                                     corresponding_enums=list(WhoAnswersFirstEnum), tags=[ConfigValueTag.share_row],
                                     option_descriptions={option.display_name: sentence[0].upper() + sentence[1:] for option, sentence in sentences.items()})
        value.shown_when = shown_when
        return value

    @staticmethod
    def get_max_npc_turns_config_value(kind: str) -> ConfigValue:
        where = {GROUP: "in a group conversation", SHOUT: "in a Shout", CONVERSATION_EVENT: "after a Conversation Event",
                 NEARBY_EVENT: "after a Nearby Event", RANDOM_EVENT: "after a Random Event"}[kind]
        description = f"""The most NPC replies in a row {where} before your turn. The Game Master can give you the turn earlier.
Who still speaks once it is reached is set by the talk settings."""
        if kind in EVENT_KINDS.values():
            description += "\nAlso in Director Mode: then it is the most NPC replies to the event before you can direct again."
        return ConfigValueInt(max_npc_turns_identifier(kind), "Max NPC Turns per Player Turn", description, DEFAULT_MAX_NPC_TURNS, 1, 10,
                              tags=[ConfigValueTag.share_row])

    @staticmethod
    def get_most_replies_config_value(situation: str, name: str) -> ConfigValue:
        if situation == NPC_EVENT:
            description = """The most lines one person may say in a watched NPC Event. Once someone has said that many, the Game Master doesn't pick them again,
and they no longer have to answer anyone. This wins over the talk settings. If nobody is left who may speak, the scene ends."""
        else:
            if situation == DIRECTOR:
                turn, next_line, back = "before you direct again", "your next direction", "you can direct again"
            else:
                turn, next_line, back = "before your turn", "your next line", "it's your turn"
            description = f"""The most replies one NPC may give {turn}. Once an NPC has replied that many times, the Game Master doesn't pick them again until {next_line},
and they no longer have to answer anyone. This wins over the talk settings. If nobody is left who may speak, {back}.
Conversation, Nearby and Random Events use the number of the conversation they happen in. 100 means no limit in practice."""
        return ConfigValueInt(most_replies_identifier(situation), "Most Replies per Person", description, DEFAULT_MOST_REPLIES, 1, 100, tags=[ConfigValueTag.share_row])

    @staticmethod
    def get_group_conversation_max_answering_config_value() -> ConfigValue:
        description = """When you say something to the whole group, like "hello everyone", this many of them count as talked to.
With "Anyone you talk to" ticked, they must speak at least once before your turn.
Who of them replies first is set by "When you talk to someone". After that, the Game Master picks, and anyone in the conversation can speak in between.
People you call by name are always included and take places first: with 5, "Hulda, Mikael, hello everyone" means Hulda, Mikael and three others.
The same number applies when an NPC speaks to the whole group.
"Everyone in the conversation" includes everyone anyway, however many there are."""
        return ConfigValueInt("group_conversation_max_answering", "People Who Must Answer a Group Line", description, DEFAULT_MAX_ANSWERING, 1, 10, tags=[ConfigValueTag.share_row])

    @staticmethod
    def get_shout_max_people_config_value() -> ConfigValue:
        description = """Nobody new joins once the conversation has this many people, you included (not while you direct).
The people a Nearby or Random Event or a direction is about still join."""
        return ConfigValueInt("shout_max_people", "Most People in Conversation", description, 6, 2, 10, tags=[ConfigValueTag.share_row])

    @staticmethod
    def get_shout_max_answering_config_value() -> ConfigValue:
        description = """When you say something to a group, like "hello guys", this many of them count as talked to:
the people in the conversation first, then the nearest people around, who join to answer.
With "Anyone you talk to" ticked, they must speak at least once before your turn.
Who of them replies first is set by "When you talk to someone". After that, the Game Master picks, and anyone in the conversation can speak in between.
People you call by name are always included and take places first: with 5, "Hulda, Mikael, hello guys" means Hulda, Mikael and three others.
Someone nearby only joins if Most People in Conversation has room for them.
The same number applies when an NPC speaks to the group.
"Everyone in the conversation" includes everyone in the conversation anyway. If nobody has to answer, this number only limits how many people nearby join at once."""
        return ConfigValueInt("shout_max_answering", "People Who Must Answer a Group Line", description, DEFAULT_MAX_ANSWERING, 1, 10, tags=[ConfigValueTag.share_row])

    @staticmethod
    def get_shout_newcomers_remember_config_value() -> ConfigValue:
        description = """What someone who joins by shouting heard before they joined.
- Since Shout: what was said since you started shouting.
- Last Line: your last line and the replies to it.
- Everything: the whole conversation."""
        options = list(NewcomersRememberEnum)
        return ConfigValueSelection("shout_newcomers_remember", "Newcomers Remember", description, NewcomersRememberEnum.SINCE_SHOUT.display_name,
                                    [option.display_name for option in options], corresponding_enums=options, tags=[ConfigValueTag.share_row])

    @staticmethod
    def get_event_send_history_config_value(kind: str, default: bool) -> ConfigValue:
        description = """Whether the event generator gets the latest lines of the conversation, so the event can follow from what was said."""
        return ConfigValueBool(f"{kind}_event_send_history", "Send the Conversation So Far", description, default, tags=[ConfigValueTag.share_row])

    @staticmethod
    def get_event_include_player_config_value(kind: str, default: bool) -> ConfigValue:
        description = """Whether the event can be about you too. Ignored in Director Mode: events are never about you there."""
        return ConfigValueBool(f"{kind}_event_include_player", "Include Me", description, default, tags=[ConfigValueTag.share_row])
