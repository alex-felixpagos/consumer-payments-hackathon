from __future__ import annotations

from app.agents import history


def test_append_turn_persists_conversation_history(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(history, "_HISTORY_FILE", tmp_path / "conversation_history.json")

    conversation = history.append_turn(
        agent_id="agent_123",
        phone_number="+15551234567",
        session_id="session_abc",
        user_id="wa:15551234567",
        user_message="hello",
        assistant_message="hi there",
        delegated_to="movies_agent",
        events=[{"type": "transfer", "to": "movies_agent"}],
    )

    assert conversation.phone_number == "15551234567"
    assert conversation.session_id == "session_abc"
    assert [message.role for message in conversation.messages] == ["user", "assistant"]
    assert conversation.messages[0].content == "hello"
    assert conversation.messages[1].content == "hi there"
    assert conversation.messages[1].metadata["delegated_to"] == "movies_agent"

    persisted = history.list_conversations()
    assert len(persisted) == 1
    assert persisted[0].messages[1].metadata["events"] == [{"type": "transfer", "to": "movies_agent"}]
