import pytest

from customagents.sessionmanager import SessionManager


@pytest.mark.asyncio
async def test_get_session_default_key(config):
    manager = SessionManager()
    session = await manager.get_session("user-1", config)

    assert session is not None
    assert session.metadata["user_id"] == "user-1"
    assert session.metadata["session_id"] == "default"


@pytest.mark.asyncio
async def test_get_session_returns_same_instance_for_same_user(config):
    manager = SessionManager()
    first = await manager.get_session("user-1", config)
    second = await manager.get_session("user-1", config)

    assert first is second


@pytest.mark.asyncio
async def test_get_session_distinguishes_explicit_session_id(config):
    manager = SessionManager()
    default = await manager.get_session("user-1", config)
    explicit = await manager.get_session("user-1", config, session_id="abc")

    assert default is not explicit
    assert explicit.metadata["session_id"] == "abc"


@pytest.mark.asyncio
async def test_delete_session(config):
    manager = SessionManager()
    await manager.get_session("user-1", config, session_id="abc")
    await manager.delete_session("user-1", "abc")

    assert "user-1:abc" not in manager.sessions
    assert "user-1:abc" not in manager._last_accessed
