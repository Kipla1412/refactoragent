import asyncio
from datetime import datetime, timezone
from agent.session import Session
from config.config import Config


class SessionManager:

    def __init__(self, ttl_seconds: int = 3600):
        # Key format: "user_id:session_id"
        self.sessions: dict[str, Session] = {}
        self._last_accessed: dict[str, datetime] = {}
        self._lock = asyncio.Lock()
        self._ttl_seconds = ttl_seconds

    async def get_session(
        self, user_id: str, config: Config, session_id: str | None = None
    ) -> Session:
        key = f"{user_id}:{session_id or 'default'}"

        async with self._lock:
            if key not in self.sessions:
                session = Session(config)
                session.metadata["user_id"] = user_id
                session.metadata["session_id"] = session_id or "default"

                self.sessions[key] = session

            self._last_accessed[key] = datetime.now(timezone.utc)
            return self.sessions[key]

    async def delete_session(self, user_id: str, session_id: str) -> None:
        key = f"{user_id}:{session_id}"
        async with self._lock:
            await self._delete_session_unlocked(key)

    async def _delete_session_unlocked(self, key: str) -> None:
        if key in self.sessions:
            session = self.sessions.pop(key)
            self._last_accessed.pop(key, None)

            # Properly close MCP connections to avoid dangling sockets
            if hasattr(session, "mcp_manager") and session.mcp_manager:
                await session.mcp_manager.shutdown()

    async def cleanup_expired_sessions(self) -> int:
        """Removes sessions that haven't been accessed within the TTL."""
        now = datetime.now(timezone.utc)
        expired_keys = []

        async with self._lock:
            for key, last_used in self._last_accessed.items():
                if (now - last_used).total_seconds() > self._ttl_seconds:
                    expired_keys.append(key)

            for key in expired_keys:
                await self._delete_session_unlocked(key)

        return len(expired_keys)

    async def shutdown(self) -> None:
        """Call this on FastAPI shutdown to gracefully close all MCP sessions."""
        async with self._lock:
            keys = list(self.sessions.keys())
            for key in keys:
                await self._delete_session_unlocked(key)

# from agent.session import Session
# from config.config import Config

# class SessionManager:
#     def __init__(self):
#         self.sessions: dict[str, Session] = {}

#     async def get_session(self, user_id: str, config: Config) -> Session:

#         if user_id not in self.sessions:
#             session = Session(config)
#             # await session.initialize()

#             # attach metadata (optional but powerful)
#             session.metadata["user_id"] = user_id

#             self.sessions[user_id] = session

#         return self.sessions[user_id]

#     def reset_session(self, user_id: str):
#         if user_id in self.sessions:
#             self.sessions[user_id].reset()

#     def delete_session(self, user_id: str):
#         if user_id in self.sessions:
#             del self.sessions[user_id]