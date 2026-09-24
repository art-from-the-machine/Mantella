import re

from src.character_manager import Character
from src.llm.output.output_parser import output_parser, sentence_generation_settings
from src.llm.sentence_content import SentenceContent, SentenceTypeEnum


_THOUGHT_MARKER = re.compile(r"<<\s*thought(?:\s+([^>]*?))?\s*>>", re.IGNORECASE)


class thought_parser(output_parser):
    """Cuts `<<thought Name>>` lines out of spoken text.

    The marker and everything after it, until the next marker, is a private
    thought for that NPC. A second marker for the same NPC in one reply is dropped.
    """

    def __init__(self, characters: list[Character]) -> None:
        super().__init__()
        self.__by_name: list[Character] = sorted(
            [c for c in characters if not c.is_player_character],
            key=lambda c: len(c.name),
            reverse=True,
        )

    def cut_sentence(self, output: str, current_settings: sentence_generation_settings) -> tuple[SentenceContent | None, str]:
        match = _THOUGHT_MARKER.search(output)
        if not match:
            return None, output

        before = output[:match.start()]
        if before.strip():
            return SentenceContent(current_settings.current_speaker, before, current_settings.sentence_type, False), output[match.start():]

        speaker = self.__resolve(match.group(1) or "", current_settings.current_speaker)
        current_settings.sentence_type = SentenceTypeEnum.THOUGHT
        if speaker is None:
            current_settings.suppress_thought = True
        else:
            current_settings.current_speaker = speaker
            ref_id = speaker.ref_id
            if ref_id in current_settings.thought_speakers:
                current_settings.suppress_thought = True
            else:
                current_settings.thought_speakers.add(ref_id)
                current_settings.suppress_thought = False
        return None, output[match.end():]

    def modify_sentence_content(self, cut_content: SentenceContent, last_content: SentenceContent | None, settings: sentence_generation_settings) -> tuple[SentenceContent | None, SentenceContent | None]:
        if cut_content.sentence_type == SentenceTypeEnum.THOUGHT and settings.suppress_thought:
            return None, last_content
        return cut_content, last_content

    def __resolve(self, name: str, current: Character) -> Character | None:
        cleaned = " ".join(name.split())
        if not cleaned:
            if current is not None and not current.is_player_character:
                return current
            return None
        lowered = cleaned.lower()
        for character in self.__by_name:
            if character.name.lower() == lowered:
                return character
        for character in self.__by_name:
            parts = [part.lower() for part in character.name.split() if part]
            if lowered in parts:
                return character
        return None
