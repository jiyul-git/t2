from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass


@dataclass
class ConnectionInfo:
    connection_id: str
    uid: str
    connected_at: float
    last_seen: float


class ConnectionRegistry:
    """Process-local connection registry.

    This is deliberately small for the first single-user server. Redis can
    replace this registry later without changing the wire protocol.
    """

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._connections: dict[str, ConnectionInfo] = {}

    async def connect(self, uid: str) -> ConnectionInfo:
        now = time.time()
        info = ConnectionInfo(
            connection_id=uuid.uuid4().hex,
            uid=uid,
            connected_at=now,
            last_seen=now,
        )
        async with self._lock:
            self._connections[info.connection_id] = info
        return info

    async def touch(self, connection_id: str) -> None:
        async with self._lock:
            info = self._connections.get(connection_id)
            if info is not None:
                info.last_seen = time.time()

    async def disconnect(self, connection_id: str) -> None:
        async with self._lock:
            self._connections.pop(connection_id, None)

    async def snapshot(self) -> dict:
        async with self._lock:
            per_user: dict[str, int] = {}
            for info in self._connections.values():
                per_user[info.uid] = per_user.get(info.uid, 0) + 1
            return {
                "connections": len(self._connections),
                "users": len(per_user),
                "connections_per_user": per_user,
            }
