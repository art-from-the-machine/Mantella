import json
import logging
import re
import threading
import time
from copy import deepcopy
from typing import Any, Callable, cast
import requests
from src.character_manager import Character
from src.config.config_loader import ConfigLoader
from src.conversation.context import context as Context
from src.conversation.conversation_type import multi_npc_game_master
from src.llm.ai_client import AIClient
from src.llm.client_base import ClientBase
from src.llm.message_thread import message_thread
from src.llm.messages import AssistantMessage, join_message, leave_message, Message, UserMessage
from src.llm.sentence import Sentence
from src.llm.sentence_content import SentenceContent, SentenceTypeEnum
from src.llm.sentence_queue import SentenceQueue
from src.prompt_profile_manager import PromptSectionError


def parse_decision(text: str | None, npcs: list[Character], player_name: str, allow_player: bool) -> tuple[bool, Character | None, str]:
    """Reads the Game Master's JSON reply, e.g. {"next": "Lydia", "reason": "..."}

    Returns:
        tuple[bool, Character | None, str]: (is the choice valid, the chosen NPC or None for the player, the reason)
    """
    if not text:
        return False, None, ""
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return False, None, ""
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return False, None, ""
    if not isinstance(data, dict):
        return False, None, ""
    reason = str(data.get("reason", "")).strip()
    is_valid, speaker = match_speaker(str(data.get("next", "")), npcs, player_name, allow_player)
    return is_valid, speaker, reason


def match_speaker(choice: str, npcs: list[Character], player_name: str, allow_player: bool) -> tuple[bool, Character | None]:
    """Matches the Game Master's choice to an NPC or the player

    Returns:
        tuple[bool, Character | None]: (is the choice valid, the chosen NPC or None for the player)
    """
    choice = choice.strip().lower()
    if not choice:
        return False, None
    if choice == "player" or (player_name and choice == player_name.lower()):
        return allow_player, None
    for npc in npcs:
        if npc.name.lower() == choice:
            return True, npc
    for npc in npcs:
        if choice in [part.lower() for part in npc.name.split()]:
            return True, npc
    return False, None


DECISIONS_URLS = {
    "OpenRouter": "https://openrouter.ai/api/alpha/decisions",
    "NanoGPT": "https://nano-gpt.com/api/v1/decisions",
}
DECISION_QUESTION = "next_speaker"
TOKEN_MARGIN = 0.9 # The token count is only an estimate, so part of the limit is kept free


def post_decision_with_retry(url: str, headers: dict[str, str], body: dict[str, Any], timeout: int) -> requests.Response:
    """Posts to the Decisions API, and posts once more if the connection breaks or the server fails (5xx)"""
    try:
        response = requests.post(url, headers=headers, json=body, timeout=timeout)
        if response.status_code < 500:
            return response
        logging.warning(f"Game Master decision call failed with status {response.status_code}. Retrying once...")
    except requests.ConnectionError as e:
        logging.warning(f"Game Master decision call failed: {e}. Retrying once...")
    return requests.post(url, headers=headers, json=body, timeout=timeout)


DECISION_INSTRUCTIONS = "skyrim_game_master_decision_instructions"
DECISION_NPC_CRITERIA = "skyrim_game_master_decision_npc_criteria"
DECISION_PLAYER_CRITERIA = "skyrim_game_master_decision_player_criteria"


def resolve_decision_prompts(config: ConfigLoader) -> dict[str, str]:
    """The decision prompts by prompt type, with an active prompt profile's shared sections expanded

    Raises:
        PromptSectionError: an active profile has a variable that is not allowed
    """
    manager = config.prompt_profile_manager
    return {
        DECISION_INSTRUCTIONS: manager.resolve_prompt(DECISION_INSTRUCTIONS, config.game_master_decision_instructions),
        DECISION_NPC_CRITERIA: manager.resolve_prompt(DECISION_NPC_CRITERIA, config.game_master_decision_npc_criteria),
        DECISION_PLAYER_CRITERIA: manager.resolve_prompt(DECISION_PLAYER_CRITERIA, config.game_master_decision_player_criteria),
    }


def fill_prompt_variables(prompt: str, values: dict[str, str]) -> str:
    """Fills {variables} with str.replace, so other braces in the text are left alone"""
    for name, value in values.items():
        prompt = prompt.replace("{" + name + "}", value)
    return prompt


def drop_oldest_lines(lines: list[str], budget: int, count_line_tokens: Callable[[str], int]) -> list[str] | None:
    """Drops the oldest lines until the rest fit the token budget. None if the budget is used up even without any lines"""
    line_tokens = [count_line_tokens(line) for line in lines]
    first_line = 0
    while sum(line_tokens[first_line:]) > budget:
        if first_line >= len(lines):
            return None
        first_line += 1
    return lines[first_line:]


def build_decision_request(prompts: dict[str, str], model: str, scene: str, history_lines: list[str], npc_names: list[str],
                           player_name: str, allow_player: bool, count_tokens: Callable[[str], int], token_limit: int) -> dict[str, Any] | None:
    """Builds the Decisions API request that asks a decision model who speaks next.
    The oldest conversation lines are dropped until the request fits the model's token limit.

    Args:
        prompts (dict[str, str]): the decision prompts by prompt type (see resolve_decision_prompts)

    Returns:
        dict[str, Any] | None: the request body. None if it does not fit even without any conversation lines
    """
    player_label = player_name or "Player"
    criteria = {name: fill_prompt_variables(prompts[DECISION_NPC_CRITERIA], {"name": name, "player_name": player_label}) for name in npc_names}
    if allow_player:
        criteria[player_label] = fill_prompt_variables(prompts[DECISION_PLAYER_CRITERIA], {"player_name": player_label})
    question = {
        "type": "choice",
        "instructions": fill_prompt_variables(prompts[DECISION_INSTRUCTIONS], {"player_name": player_label, "names": ", ".join(npc_names)}),
        "criteria": criteria,
    }

    budget = (int(token_limit * TOKEN_MARGIN) - count_tokens(json.dumps(question, ensure_ascii=False))
              - count_tokens(json.dumps({"scene": scene, "conversation": []}, ensure_ascii=False)))
    kept_lines = drop_oldest_lines(history_lines, budget, lambda line: count_tokens(json.dumps(line, ensure_ascii=False)) + 1)
    if kept_lines is None:
        return None
    state = {"scene": scene, "conversation": kept_lines}
    return {"model": model, "state": state, "questions": {DECISION_QUESTION: question}}


def format_decision_request(body: dict[str, Any]) -> str:
    """The Decisions API request as readable text for the log, with the prompts' line breaks kept"""
    state = body["state"]
    lines = [f"Model: {body['model']}", "", "===== Scene =====", state["scene"], "",
             f"===== Conversation ({len(state['conversation'])} lines) ====="]
    lines += state["conversation"]
    for name, question in body["questions"].items():
        lines += ["", f"===== Question: {name} ({question['type']}) =====", question["instructions"], "", "Criteria:"]
        lines += [f"  - {choice}: {criterion}" for choice, criterion in question["criteria"].items()]
    return "\n".join(lines)


def format_response_text(text: str) -> str:
    """A JSON response indented for the log. Anything else is returned unchanged"""
    try:
        return json.dumps(json.loads(text), indent=2, ensure_ascii=False)
    except (ValueError, TypeError):
        return text


def format_confidence(answer: dict[str, Any]) -> str:
    """The decision's confidence and probabilities for the log. Values that are not numbers are shown as they are"""
    try:
        probabilities = answer.get("probabilities") or {}
        details = ", ".join(f"{name} {probability:.2f}" for name, probability in sorted(probabilities.items(), key=lambda item: -item[1]))
        return f"confidence {answer.get('confidence', 0):.2f}: {details}"
    except (TypeError, ValueError, AttributeError):
        return f"confidence {answer.get('confidence')}, probabilities {answer.get('probabilities')}"


def log_request_time(started_at: float):
    logging.log(26, f"Game Master request took {time.time() - started_at:.2f} seconds")


def should_log_prompt(logged_prompts: set[str], key: str) -> bool:
    """True the first time a key is seen. Used to log each prompt once, and again when the participants change"""
    if key in logged_prompts:
        return False
    logged_prompts.add(key)
    return True


def messages_heard_by(history: list[Message], npc: Character) -> list[Message]:
    """Keeps only the messages from while the NPC was in the conversation, the same way summaries do.
    The NPCs who start the conversation have no join message, and a long conversation's reload can drop one.
    So an NPC counts as present from the start if its first join/leave message is a leave message, or if it has none.
    """
    markers = [m for m in history if isinstance(m, (join_message, leave_message)) and m.character.name == npc.name]
    if not markers:
        return history
    result: list[Message] = []
    is_present = isinstance(markers[0], leave_message)
    for message in history:
        if isinstance(message, join_message) and message.character.name == npc.name:
            is_present = True
        if is_present:
            result.append(message)
        if isinstance(message, leave_message) and message.character.name == npc.name:
            is_present = False
    return result


def history_text_without_thoughts(history: list[Message]) -> str:
    """The conversation as text with each line labelled by speaker. Turn thoughts are left out"""
    result = ""
    for message in history:
        was_multi_npc_message = message.is_multi_npc_message
        message.is_multi_npc_message = True
        if isinstance(message, AssistantMessage):
            result += f"{message.get_formatted_content(include_thoughts=False)}\n"
        else:
            result += f"{message.get_formatted_content()}\n"
        message.is_multi_npc_message = was_multi_npc_message
    return result


def add_reply_to_history(history: list[Message], sentences: list[Sentence], config: ConfigLoader, is_multi_npc: bool):
    """Adds a reply's sentences to the history the same way the conversation does when they are played:
    to the last assistant message, or to a new one if the last message is not an assistant message"""
    if not sentences:
        return
    if history and isinstance(history[-1], AssistantMessage):
        message = history[-1]
    else:
        message = AssistantMessage(config)
        message.is_multi_npc_message = is_multi_npc
        message.thoughts_in_place = True
        history.append(message)
    for sentence in sentences:
        message.add_sentence(sentence)


def thread_for_lorebook(config: ConfigLoader, history: list[Message]) -> message_thread:
    """A message thread with the given history, for the lorebook"""
    thread = message_thread(config, None)
    thread.add_non_system_messages(history)
    return thread


class GameMaster:
    """Asks the Game Master LLM who speaks next in a multi-NPC Game Master Mode conversation"""
    def __init__(self, context_for_conversation: Context, conversation_type: multi_npc_game_master, client: AIClient | None, logged_prompts: set[str] | None = None) -> None:
        self.__context = context_for_conversation
        self.__conversation_type = conversation_type
        self.__client = client
        self.__logged_prompts: set[str] = logged_prompts if logged_prompts is not None else set()

    def choose_next_speaker(self, live_messages: message_thread, history: list[Message], allow_player: bool) -> Character | None:
        """Asks the Game Master who speaks next

        Args:
            live_messages (message_thread): the message thread used for the lorebook
            history (list[Message]): the conversation history to show the Game Master
            allow_player (bool): whether the Game Master may hand the turn to the player

        Returns:
            Character | None: the NPC to speak next. None if the player should speak or no valid choice was made
        """
        if not self.__client:
            return None
        config = self.__context.config
        npcs = self.__context.get_characters_excluding_player().get_all_characters()
        player = self.__context.npcs_in_conversation.get_player_character()
        player_name = player.name if player else ""
        should_log = should_log_prompt(self.__logged_prompts, "game master|" + self.__context.get_character_names_as_text(True))
        if should_log:
            logging.log(26, "===== Game Master prompt =====")
        try:
            prompt = self.__conversation_type.generate_game_master_prompt(self.__context, live_messages, should_log)
        except PromptSectionError as e:
            logging.error(str(e))
            logging.error("Game Master could not decide who speaks next. Fix the active Game Master prompt profile.")
            return None
        if config.game_master_use_decision_model:
            return self.__choose_with_decision_model(prompt, history, allow_player, npcs, player_name)

        choices = [npc.name for npc in npcs]
        if allow_player and player_name:
            choices.append(player_name)
        history_lines = [line for line in history_text_without_thoughts(history).split("\n") if line.strip()]
        header = "The conversation so far:\n"
        footer = (f"\nWho speaks next? Choose one of: {', '.join(choices)}.\n"
                  'Reply only with JSON in this format: {"next": "<name>", "reason": "<a few words>"}')
        # The conversation is only reloaded when it gets too long for the NPC model, so the oldest lines are dropped to fit the Game Master model
        client = cast(ClientBase, self.__client)
        budget = int(client.token_limit * TOKEN_MARGIN) - client.get_count_tokens(prompt) - client.get_count_tokens(header + footer)
        kept_lines = drop_oldest_lines(history_lines, budget, lambda line: client.get_count_tokens(line) + 1)
        if kept_lines is None:
            logging.error(f"Game Master prompt is too long for the Game Master model {client.model_name} ({client.token_limit} tokens). Shorten the Skyrim Game Master Prompt.")
            return None
        request_text = header + "".join(line + "\n" for line in kept_lines) + footer
        request = message_thread(config, prompt) # Never with the decensor bypass: its roleplay commitment can make the Game Master write dialogue
        request.add_message(UserMessage(config, request_text, "", True))

        started_at = time.time()
        try:
            reply = self.__client.request_call(request)
        except Exception as e:
            logging.error(f"Game Master LLM call failed: {e}")
            return None
        finally:
            log_request_time(started_at)
        is_valid, speaker, reason = parse_decision(reply, npcs, player_name, allow_player)
        if not is_valid:
            logging.warning(f"Game Master gave no valid choice: {reply}")
            return None
        logging.log(26, f"Game Master: {speaker.name if speaker else player_name} speaks next ({reason})")
        return speaker

    def __choose_with_decision_model(self, prompt: str, history: list[Message], allow_player: bool,
                                     npcs: list[Character], player_name: str) -> Character | None:
        """Asks a decision model (e.g. typesafe/jev-1.13) who speaks next through the OpenRouter or NanoGPT Decisions API"""
        config = self.__context.config
        client = cast(ClientBase, self.__client)
        url = DECISIONS_URLS.get(client.service_name)
        if not url:
            logging.error(f"Game Master decision models only work through OpenRouter or NanoGPT, not {client.service_name}.")
            return None
        history_lines = [line for line in history_text_without_thoughts(history).split("\n") if line.strip()]
        try:
            prompts = resolve_decision_prompts(config)
        except PromptSectionError as e:
            logging.error(str(e))
            logging.error("Game Master could not decide who speaks next. Fix the active Game Master Decision prompt profile.")
            return None
        body = build_decision_request(prompts, client.model_name, prompt, history_lines, [npc.name for npc in npcs],
                                      player_name, allow_player, client.get_count_tokens, client.token_limit)
        if not body:
            logging.error(f"Game Master prompt is too long for the decision model {client.model_name} ({client.token_limit} tokens). Shorten the Skyrim Game Master Prompt.")
            return None
        logging.log(15, "Game Master decision request:\n" + format_decision_request(body))

        headers = {
            "Authorization": f"Bearer {client.api_key}",
            "HTTP-Referer": "https://art-from-the-machine.github.io/Mantella/",
            "X-Title": "Mantella",
        }
        logging.info(f"Game Master Request Parameters: model='{client.model_name}', url='{url}'")
        started_at = time.time()
        try:
            response = post_decision_with_retry(url, headers, body, config.llm_response_timeout)
        except Exception as e:
            logging.error(f"Game Master decision call failed: {e}")
            return None
        finally:
            log_request_time(started_at)
        if response.status_code != 200:
            try:
                message = response.json()["error"]["message"]
            except Exception:
                message = response.text
            logging.error(f"Game Master decision call failed with status {response.status_code}: {message}")
            logging.log(23, f"Game Master decision response:\n{format_response_text(response.text)}")
            return None
        try:
            answer = response.json()["answers"][DECISION_QUESTION]
            choice = str(answer["choice"])
        except Exception:
            logging.warning(f"Game Master gave no valid choice:\n{format_response_text(response.text)}")
            return None

        is_valid, speaker = match_speaker(choice, npcs, player_name, allow_player)
        if not is_valid:
            logging.warning(f"Game Master gave no valid choice: {choice}")
            return None
        logging.log(26, f"Game Master: {speaker.name if speaker else player_name} speaks next ({format_confidence(answer)})")
        return speaker


class ReplyQueue:
    """The sentences of one NPC reply. A released reply passes its sentences on to the conversation's SentenceQueue.
    A held reply keeps them until it is released, so it can be generated while the reply before it is still being played.
    """
    def __init__(self, queue: SentenceQueue, is_released: bool) -> None:
        self.__queue = queue
        self.__lock: threading.Lock = threading.Lock()
        self.__held: list[Sentence] = []
        self.__is_more_to_come: bool = True
        self.__is_released: bool = is_released
        self.__is_discarded: bool = False
        self.sentences: list[Sentence] = [] # The sentences the conversation adds to its history when they are played
        self.next_reply: ReplyQueue | None = None # The reply that follows this one. None if the player gets the turn
        self.next_ready: threading.Event = threading.Event() # Set once next_reply is decided

    @property
    def is_released(self) -> bool:
        return self.__is_released

    @property
    def is_more_to_come(self) -> bool:
        return self.__is_more_to_come

    @is_more_to_come.setter
    def is_more_to_come(self, value: bool):
        with self.__lock:
            self.__is_more_to_come = value
            if self.__is_released and not self.__is_discarded:
                self.__queue.is_more_to_come = value

    def put(self, new_sentence: Sentence):
        with self.__lock:
            if self.__is_discarded:
                return
            if not new_sentence.is_system_generated_sentence and not new_sentence.speaker.is_player_character:
                self.sentences.append(new_sentence)
            if self.__is_released:
                self.__queue.put(new_sentence)
            else:
                self.__held.append(new_sentence)

    def release(self) -> bool:
        """Passes the held sentences on and lets the rest of the reply through. False if the reply was thrown away"""
        with self.__lock:
            if self.__is_discarded:
                return False
            for sentence in self.__held:
                self.__queue.put(sentence)
            self.__held.clear()
            self.__queue.is_more_to_come = self.__is_more_to_come
            self.__is_released = True
            return True

    def discard(self):
        """Throws the reply away. Nothing more is passed on"""
        with self.__lock:
            self.__is_discarded = True
            self.__held.clear()

    def end(self, speaker: Character | None):
        """Sends the end-of-reply sentence if the reply has not sent one yet"""
        if self.is_more_to_come:
            self.is_more_to_come = False
            self.put(Sentence(SentenceContent(speaker, "", SentenceTypeEnum.SPEECH, True), "", 0))


class GameMasterTurns:
    """Turn state of a multi-NPC Game Master Mode conversation.
    After each NPC reply, the next speaker is decided and their reply is generated while the reply before it is still being played in game.
    Generation stays at most one reply ahead of the reply being played.
    """
    def __init__(self, context_for_conversation: Context, sentences: SentenceQueue) -> None:
        self.__context = context_for_conversation
        self.__sentences = sentences
        self.__npc_turns_since_player: int = 0
        self.__turn_id: int = 0 # Bumped when the turn is thrown away, so work from it is thrown away too
        self.__playing: ReplyQueue | None = None # The reply being played. None until an NPC turn starts after the last player input
        self.__replies: list[ReplyQueue] = [] # The replies of the running turn
        self.__logged_prompts: set[str] = set()
        self.__lock: threading.Lock = threading.Lock() # Keeps the turn id check and the update that follows it together
        self.__output_manager = None # The ChatManager the latest reply was generated with. After a settings change, it is not the conversation's ChatManager

    def on_player_input(self):
        with self.__lock:
            self.__npc_turns_since_player = 0
            self.__discard_turn()

    def cancel(self):
        """Throws away the running NPC turn and its replies, so the player gets the next turn.
        Call before stopping generation, so the turn sees it was discarded as soon as its reply stops."""
        with self.__lock:
            self.__discard_turn()
        # A discarded turn never sends its end-of-reply sentence. Without one, a request waiting for the next
        # sentence would wait forever while holding the queue's lock, so clearing the queue would never finish
        self.__end_reply()

    def drop_lookahead(self) -> bool:
        """Throws away the replies that have not started playing, so the player gets the turn after the reply being played.

        Returns:
            bool: True if a reply that was thrown away may still be generating
        """
        with self.__lock:
            return self.__drop_lookahead()

    def log_prompts_again(self):
        """Logs each prompt again the next time it is used, e.g. after a settings change that can change the prompts"""
        self.__logged_prompts.clear()

    def stop_generation(self):
        """Stops generation on the ChatManager the latest reply was generated with.
        A reply started before a settings change keeps generating on the old ChatManager"""
        output_manager = self.__output_manager
        if output_manager:
            output_manager.stop_generation()

    def __drop_lookahead(self) -> bool:
        """drop_lookahead for a caller that holds the lock"""
        playing = self.__playing
        if not playing:
            return False
        self.__turn_id += 1
        for reply in self.__replies:
            if reply is not playing:
                reply.discard()
        self.__replies = [playing]
        playing.next_reply = None
        playing.next_ready.set()
        # Once the reply being played is fully generated, any generation still running is for a reply that was thrown away
        return not playing.is_more_to_come

    def __discard_turn(self):
        self.__turn_id += 1
        for reply in self.__replies:
            reply.discard()
        self.__replies = []
        self.__playing = None

    def start_turn(self) -> int:
        """Call before starting the thread for run_turn. Returns the id to pass to run_turn"""
        with self.__lock:
            first_reply = ReplyQueue(self.__sentences, True)
            self.__replies = [first_reply]
            self.__playing = first_reply
            return self.__turn_id

    def play_next_reply(self, timeout: float, is_interrupted: Callable[[], bool] = lambda: False) -> bool:
        """Starts playing the reply that follows the one that has just been played

        Args:
            timeout (float): seconds to wait for the decision
            is_interrupted (Callable[[], bool]): stops the wait early when it returns True, e.g. when the player has spoken

        Returns:
            bool: True if an NPC reply follows. False if the player gets the turn
        """
        with self.__lock:
            playing = self.__playing
            turn_id = self.__turn_id
        if not playing:
            # No NPC turn is running (e.g. the conversation just switched to Game Master Mode, or an NPC was dismissed)
            return False
        deadline = time.time() + timeout
        while not playing.next_ready.wait(0.05):
            if is_interrupted() or turn_id != self.__turn_id:
                return False
            if time.time() >= deadline:
                logging.warning("Game Master did not decide in time. The player gets the turn.")
                with self.__lock:
                    if turn_id == self.__turn_id:
                        # Stops the turn, so a late decision does not generate a reply that is never played.
                        # The decision is still being made, so no reply is generating
                        self.__drop_lookahead()
                return False
        with self.__lock:
            next_reply = playing.next_reply
            if turn_id != self.__turn_id or not next_reply or not next_reply.release():
                return False
            self.__playing = next_reply
            return True

    def run_turn(self, turn_id: int, get_conversation_type: Callable[[], Any], get_output_manager: Callable[[], Any], live_messages: message_thread):
        """Generates NPC replies one after another, each with a prompt that only contains that NPC, until the player gets the turn.
        Each reply after the first is generated while the one before it is being played, and is held until that one has been played.
        Runs in the generation thread.

        Args:
            turn_id (int): the id returned by start_turn
            get_conversation_type (Callable[[], Any]): returns the conversation's current conversation type, which builds the prompts
            get_output_manager (Callable[[], Any]): returns the conversation's current ChatManager, which generates the replies and holds the Game Master client
                Both are read again for each request, so a settings change applies from the next request on
            live_messages (message_thread): the conversation's message thread
        """
        with self.__lock:
            if turn_id != self.__turn_id or not self.__playing:
                return
            reply: ReplyQueue | None = self.__playing
        # The history as it will be once the replies generated so far have been played
        history = live_messages.get_persistent_messages()
        speaker: Character | None = None
        while reply:
            try:
                conversation_type = get_conversation_type()
                if not isinstance(conversation_type, multi_npc_game_master):
                    # A settings change turned Game Master Mode off
                    self.__end_turn_early(turn_id, reply)
                    return
                if not speaker:
                    # The first speaker of the turn, after the player has spoken
                    speaker = self.__choose_first_speaker(self.__game_master(conversation_type, get_output_manager()), history)
                if not speaker:
                    self.__end_turn_early(turn_id, reply)
                    return
                speaker, reply = self.__run_reply(speaker, reply, turn_id, history, conversation_type, get_conversation_type, get_output_manager)
            except Exception as e:
                logging.error(f"Game Master turn failed: {e}")
                self.__end_turn_early(turn_id, reply)
                return

    def __game_master(self, conversation_type: multi_npc_game_master, output_manager) -> GameMaster:
        return GameMaster(self.__context, conversation_type, output_manager.game_master_client, self.__logged_prompts)

    def __choose_first_speaker(self, game_master: GameMaster, history: list[Message]) -> Character | None:
        speaker = game_master.choose_next_speaker(thread_for_lorebook(self.__context.config, history), history, allow_player=False)
        if speaker:
            return speaker
        characters = self.__context.npcs_in_conversation
        npcs = self.__context.get_characters_excluding_player().get_all_characters()
        if characters.last_added_character and not characters.last_added_character.is_player_character:
            return characters.last_added_character
        if npcs:
            return npcs[-1]
        return None

    def __run_reply(self, speaker: Character, reply: ReplyQueue, turn_id: int, history: list[Message], conversation_type: multi_npc_game_master,
                    get_conversation_type: Callable[[], Any], get_output_manager: Callable[[], Any]) -> tuple[Character | None, ReplyQueue | None]:
        """Generates one reply, decides who speaks next and waits until the reply is being played

        Returns:
            tuple[Character | None, ReplyQueue | None]: the next speaker and their reply. (None, None) if this turn is over
        """
        config = self.__context.config
        characters = self.__context.npcs_in_conversation
        if turn_id != self.__turn_id:
            return None, None
        output_manager = get_output_manager()

        should_log = should_log_prompt(self.__logged_prompts, f"{speaker.ref_id}|{self.__context.get_character_names_as_text(True)}")
        if should_log:
            logging.log(26, f"===== Game Master Mode prompt for {speaker.name} =====")
        try:
            prompt = conversation_type.generate_npc_prompt(self.__context, speaker, thread_for_lorebook(config, history), should_log)
        except PromptSectionError as e:
            logging.error(str(e))
            logging.error("NPC reply was not generated. Fix the active Game Master NPC prompt profile, or end the conversation.")
            self.__end_turn_early(turn_id, reply)
            return None, None
        # A separate copy, so only what this NPC heard and only its own thoughts are sent. The Game Master sees the whole conversation, without thoughts
        npc_history = messages_heard_by(deepcopy(history), speaker)
        for message in npc_history:
            if isinstance(message, AssistantMessage):
                message.thoughts_only_of_ref_id = speaker.ref_id
        npc_request = message_thread(config, prompt, include_decensor_bypass=True)
        npc_request.add_non_system_messages(npc_history)
        if len(npc_history) == 0 or not isinstance(npc_history[-1], UserMessage):
            # Only sent with this request so the NPC has something to reply to. Never added to the conversation itself
            npc_request.add_message(UserMessage(config, f"({speaker.name} speaks next.)", "", True))

        with self.__lock:
            if turn_id != self.__turn_id:
                return None, None
            self.__output_manager = output_manager
        output_manager.generate_response(npc_request, characters, reply, config.actions, single_speaker=speaker)
        add_reply_to_history(history, reply.sentences, config, characters.contains_multiple_npcs())
        with self.__lock:
            if turn_id != self.__turn_id:
                return None, None
            self.__npc_turns_since_player += 1
            npc_turns = self.__npc_turns_since_player
        next_speaker: Character | None = None
        # Read again, so a settings change made while the reply was generating applies to the decision
        conversation_type = get_conversation_type()
        if isinstance(conversation_type, multi_npc_game_master): # Otherwise a settings change turned Game Master Mode off, and the player gets the turn
            # Director mode: the player is not part of the conversation, so they only get the turn back once the run ends
            is_director = conversation_type.is_director_mode()
            max_npc_turns = config.multi_npc_game_master_director_max_npc_turns if is_director else config.multi_npc_game_master_max_npc_turns
            if npc_turns < max_npc_turns:
                game_master = self.__game_master(conversation_type, get_output_manager())
                next_speaker = game_master.choose_next_speaker(thread_for_lorebook(config, history), history, allow_player=not is_director)
            else:
                logging.log(26, f"Game Master: {npc_turns} NPC replies in a row. The player gets the turn.")
        with self.__lock:
            if turn_id != self.__turn_id:
                return None, None
            next_reply = ReplyQueue(self.__sentences, False) if next_speaker else None
            if next_reply:
                self.__replies.append(next_reply)
            reply.next_reply = next_reply
            reply.next_ready.set()
        if not next_reply:
            return None, None
        # Generation stays one reply ahead: the next reply is only generated once this one is being played
        while not reply.is_released:
            if turn_id != self.__turn_id:
                return None, None
            time.sleep(0.05)
        return next_speaker, next_reply

    def __end_turn_early(self, turn_id: int, reply: ReplyQueue | None):
        """Hands the turn to the player after the reply when it could not be generated"""
        with self.__lock:
            if reply and turn_id == self.__turn_id:
                reply.next_reply = None
                reply.next_ready.set()
        if reply:
            reply.end(self.__context.npcs_in_conversation.last_added_character)

    def __end_reply(self):
        """Sends the end-of-reply sentence if a reply is still expected. Unblocks the game if it is already waiting for the next sentence"""
        if self.__sentences.is_more_to_come:
            self.__sentences.is_more_to_come = False
            self.__sentences.put(Sentence(SentenceContent(self.__context.npcs_in_conversation.last_added_character, "", SentenceTypeEnum.SPEECH, True), "", 0))
