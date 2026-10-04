"""Voice sessions must not leak conversation history across restarts.

The voice WebSocket previously keyed sessions by user alone ("<user_id>:default"),
so every reconnect returned the same Session and the agent "remembered" the
previous conversation. Sessions are now keyed by an explicit session id that is
generated fresh per connection unless the client pins one, and ephemeral
sessions are dropped on disconnect.

HTTP chat endpoints keep the opposite default on purpose: with no session id
they reuse the user's session, so a chat is not erased between turns.
"""

import logging

import pytest

from api.wsrouters.webs2s import _resolve_session_id


def test_resolve_session_id_keeps_client_supplied_value():
    assert _resolve_session_id("session-abc") == "session-abc"


def test_resolve_session_id_creates_unique_ids_when_absent():
    first = _resolve_session_id(None)
    second = _resolve_session_id(None)

    assert first
    assert second
    assert first != second


class _FakeSession:
    def __init__(self, config):
        self.metadata = {}
        self.messages = []
        # Mirrors the real Session, which generates its own uuid in __init__.
        self.session_id = "generated-by-constructor"


@pytest.fixture
def manager(monkeypatch):
    import customagents.sessionmanager as sessionmanager

    monkeypatch.setattr(sessionmanager, "Session", _FakeSession)
    return sessionmanager.SessionManager()


@pytest.mark.asyncio
async def test_get_session_is_keyed_by_session_id(manager):
    first = await manager.get_session("user-1", config=None, session_id="call-1")
    again = await manager.get_session("user-1", config=None, session_id="call-1")
    other = await manager.get_session("user-1", config=None, session_id="call-2")

    assert first is again
    assert first is not other


@pytest.mark.asyncio
async def test_default_session_is_reused_per_user(manager):
    """Chat endpoints pass no session id and must keep the conversation."""
    first = await manager.get_session("user-1", config=None)
    second = await manager.get_session("user-1", config=None)
    other_user = await manager.get_session("user-2", config=None)

    assert first is second
    assert first is not other_user
    assert first.metadata["session_id"] == "default"


@pytest.mark.asyncio
async def test_session_id_matches_the_key_so_clients_can_resume(manager):
    """`X-Session-ID` must be the value the client sends back.

    It used to be the Session's own generated uuid, which did not match the key
    the manager stored it under, so a client echoing it created a brand-new
    session on every request and lost the conversation.
    """
    session = await manager.get_session("user-1", config=None, session_id="call-1")
    assert session.session_id == "call-1"

    default = await manager.get_session("user-1", config=None)
    assert default.session_id == "default"


@pytest.mark.asyncio
async def test_echoing_the_returned_id_resumes_the_same_session(manager):
    first = await manager.get_session("user-1", config=None)
    echoed = first.session_id

    again = await manager.get_session("user-1", config=None, session_id=echoed)

    assert again is first


@pytest.mark.asyncio
async def test_new_session_id_starts_with_empty_history(manager):
    first = await manager.get_session("user-1", config=None, session_id="call-1")
    first.messages.append("previous conversation turn")

    fresh = await manager.get_session("user-1", config=None, session_id="call-2")

    assert fresh.messages == []


@pytest.mark.asyncio
async def test_delete_session_forces_a_brand_new_session(manager):
    first = await manager.get_session("user-1", config=None, session_id="call-1")

    await manager.delete_session("user-1", "call-1")

    after = await manager.get_session("user-1", config=None, session_id="call-1")
    assert after is not first
    assert after.messages == []


@pytest.mark.asyncio
async def test_session_lifecycle_is_logged(manager, caplog):
    """Session ids are logged so churn (a new id every turn) is diagnosable."""
    with caplog.at_level(logging.INFO, logger="customagents.sessionmanager"):
        await manager.get_session("user-1", config=None, session_id="call-1")
        await manager.get_session("user-1", config=None, session_id="call-1")
        await manager.delete_session("user-1", "call-1")

    text = caplog.text
    assert "[SESSION] created" in text
    assert "[SESSION] reused" in text
    assert "[SESSION] removed" in text
    assert "call-1" in text


@pytest.mark.asyncio
async def test_deleting_an_unknown_session_is_logged_as_a_warning(manager, caplog):
    with caplog.at_level(logging.INFO, logger="customagents.sessionmanager"):
        await manager.delete_session("user-1", "never-existed")

    assert "not found" in caplog.text
