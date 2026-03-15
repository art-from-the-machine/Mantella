import pytest
from unittest.mock import MagicMock
from src.character_manager import Character
from src.output_manager import ChatManager
from src.config.config_loader import ConfigLoader
from src.config.definitions.tts_definitions import TTSEnum
from src.tts.piper import Piper
from src.games.skyrim import Skyrim
from src.llm.sentence_content import SentenceContent, SentenceTypeEnum
from tests.conftest import MockAIClient


@pytest.fixture
def output_manager(default_config: ConfigLoader, piper: Piper, mock_ai_client: MockAIClient, skyrim: Skyrim, monkeypatch) -> ChatManager:
    piper.synthesize = MagicMock(return_value="mock_audio_file.wav")
    monkeypatch.setattr('src.utils.get_audio_duration', lambda *args, **kwargs: 1.0)
    return ChatManager(default_config, piper, mock_ai_client, skyrim)


class TestGetOrCreateTTS:
    """Tests for ChatManager._get_or_create_tts."""

    def test_returns_default_when_service_matches_config(self, output_manager: ChatManager, default_config: ConfigLoader):
        """When the requested service matches the globally configured TTS, return the default instance."""
        default_service = default_config.tts_service
        result = output_manager._get_or_create_tts(default_service)
        assert result is output_manager.tts

    def test_caches_tts_instance(self, output_manager: ChatManager, monkeypatch):
        """A second call for the same service should return the cached instance."""
        mock_xvasynthsynth = MagicMock()
        monkeypatch.setattr("src.tts.tts_factory.xVASynth", lambda config: mock_xvasynthsynth)
        output_manager._ChatManager__config.tts_service = TTSEnum.PIPER

        first = output_manager._get_or_create_tts(TTSEnum.XVASYNTH)
        second = output_manager._get_or_create_tts(TTSEnum.XVASYNTH)
        assert first is second
        assert first is mock_xvasynthsynth

    def test_falls_back_to_default_on_creation_failure(self, output_manager: ChatManager, monkeypatch):
        """If TTS creation fails, fall back to the default TTS instance."""
        monkeypatch.setattr("src.tts.tts_factory.xVASynth", lambda config: (_ for _ in ()).throw(Exception("fail")))
        output_manager._ChatManager__config.tts_service = TTSEnum.PIPER

        result = output_manager._get_or_create_tts(TTSEnum.XVASYNTH)
        assert result is output_manager.tts

    def test_piper_requires_game_context(self, output_manager: ChatManager):
        """Creating Piper without a game context should fall back to default."""
        output_manager._ChatManager__config.tts_service = TTSEnum.XVASYNTH
        output_manager._ChatManager__game = None

        result = output_manager._get_or_create_tts(TTSEnum.PIPER)
        assert result is output_manager.tts

    def test_creates_piper_with_game_context(self, output_manager: ChatManager, monkeypatch):
        """With a game context, Piper should be successfully created and cached."""
        mock_piper = MagicMock()
        monkeypatch.setattr("src.tts.tts_factory.Piper", lambda config, game: mock_piper)
        output_manager._ChatManager__config.tts_service = TTSEnum.XVASYNTH

        result = output_manager._get_or_create_tts(TTSEnum.PIPER)
        assert result is mock_piper
        assert result is not output_manager.tts


class TestPerCharacterTTSInGenerateSentence:
    """Tests for per-character TTS selection in generate_sentence."""

    def test_uses_default_tts_when_overrides_disabled(self, output_manager: ChatManager, example_skyrim_npc_character: Character):
        """When allow_per_character_tts_overrides is False (default), always use the default TTS even if tts_service is set."""
        output_manager._ChatManager__config.allow_per_character_tts_overrides = False
        example_skyrim_npc_character.tts_service = "xvasynth"
        content = SentenceContent(example_skyrim_npc_character, "Hello there.", SentenceTypeEnum.SPEECH, False)

        sentence = output_manager.generate_sentence(content)
        assert sentence.voice_file == "mock_audio_file.wav"
        output_manager.tts.synthesize.assert_called_once()

    def test_uses_default_tts_when_no_tts_service_set(self, output_manager: ChatManager, example_skyrim_npc_character: Character):
        """Characters without tts_service use the default TTS."""
        output_manager._ChatManager__config.allow_per_character_tts_overrides = True
        example_skyrim_npc_character.tts_service = ""
        content = SentenceContent(example_skyrim_npc_character, "Hello there.", SentenceTypeEnum.SPEECH, False)

        sentence = output_manager.generate_sentence(content)
        assert sentence.voice_file == "mock_audio_file.wav"
        output_manager.tts.synthesize.assert_called_once()

    def test_uses_per_character_tts_when_service_set(self, output_manager: ChatManager, example_skyrim_npc_character: Character, monkeypatch):
        """Characters with a valid tts_service use a per-character TTS instance."""
        output_manager._ChatManager__config.allow_per_character_tts_overrides = True
        mock_xvasynth = MagicMock()
        mock_xvasynth.synthesize.return_value = "xvasynth_audio.wav"
        monkeypatch.setattr("src.tts.tts_factory.xVASynth", lambda config: mock_xvasynth)
        output_manager._ChatManager__config.tts_service = TTSEnum.PIPER

        example_skyrim_npc_character.tts_service = "xvasynth"
        content = SentenceContent(example_skyrim_npc_character, "Hello there.", SentenceTypeEnum.SPEECH, False)

        monkeypatch.setattr('src.utils.get_audio_duration', lambda *args, **kwargs: 1.0)
        sentence = output_manager.generate_sentence(content)
        assert sentence.voice_file == "xvasynth_audio.wav"
        mock_xvasynth.synthesize.assert_called_once()

    def test_falls_back_on_per_character_tts_failure(self, output_manager: ChatManager, example_skyrim_npc_character: Character, monkeypatch):
        """If per-character TTS fails, fall back to default TTS."""
        output_manager._ChatManager__config.allow_per_character_tts_overrides = True
        mock_xvasynth = MagicMock()
        mock_xvasynth.synthesize.side_effect = Exception("TTS crashed")
        monkeypatch.setattr("src.tts.tts_factory.xVASynth", lambda config: mock_xvasynth)
        output_manager._ChatManager__config.tts_service = TTSEnum.PIPER

        example_skyrim_npc_character.tts_service = "xvasynth"
        content = SentenceContent(example_skyrim_npc_character, "Hello there.", SentenceTypeEnum.SPEECH, False)

        sentence = output_manager.generate_sentence(content)
        assert sentence.voice_file == "mock_audio_file.wav"
        output_manager.tts.synthesize.assert_called_once()

    def test_unrecognized_tts_service_uses_default(self, output_manager: ChatManager, example_skyrim_npc_character: Character):
        """A character with an unrecognized tts_service should use the default TTS."""
        output_manager._ChatManager__config.allow_per_character_tts_overrides = True
        example_skyrim_npc_character.tts_service = "fake_tts"
        content = SentenceContent(example_skyrim_npc_character, "Hello there.", SentenceTypeEnum.SPEECH, False)

        sentence = output_manager.generate_sentence(content)
        assert sentence.voice_file == "mock_audio_file.wav"
        output_manager.tts.synthesize.assert_called_once()
