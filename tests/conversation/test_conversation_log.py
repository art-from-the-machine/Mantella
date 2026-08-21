from types import SimpleNamespace

from src.conversation.conversation_log import conversation_log


def test_save_conversation_log_does_not_escape_unicode(tmp_path, monkeypatch):
    monkeypatch.setattr(conversation_log, "game_path", str(tmp_path))

    character = SimpleNamespace(name="Lydia", ref_id="000A2C8E")
    messages = [
        {
            "role": "assistant",
            "content": "こんにちは 안녕하세요 Привет",
        }
    ]

    conversation_log.save_conversation_log(character, messages, "test-world")

    log_files = list(tmp_path.rglob("*.json"))
    assert len(log_files) == 1

    saved_text = log_files[0].read_text(encoding="utf-8")

    assert "こんにちは" in saved_text
    assert "안녕하세요" in saved_text
    assert "Привет" in saved_text