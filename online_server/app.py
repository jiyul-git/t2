from __future__ import annotations

import asyncio
import json
import time
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Request, WebSocket, WebSocketDisconnect

from online_server.auth import AuthError, AuthService, Identity
from online_server.config import Settings, load_settings
from online_server.registry import ConnectionRegistry


class ProtocolError(Exception):
    pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = load_settings()
    app.state.settings = settings
    app.state.auth = AuthService(settings)
    app.state.registry = ConnectionRegistry()
    yield


app = FastAPI(
    title="T2 Online Gateway",
    version="0.1.0",
    lifespan=lifespan,
)


def _bearer_token(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(
            status_code=401,
            detail="Bearer token required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    scheme, sep, token = authorization.partition(" ")
    if not sep or scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(
            status_code=401,
            detail="Invalid Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return token.strip()


async def current_identity(
    request: Request,
    authorization: str | None = Header(default=None),
) -> Identity:
    token = _bearer_token(authorization)
    auth_service: AuthService = request.app.state.auth
    try:
        return auth_service.verify(token)
    except AuthError as exc:
        raise HTTPException(
            status_code=401,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from None


async def _receive_object(websocket: WebSocket, settings: Settings) -> dict[str, Any]:
    raw = await websocket.receive_text()
    if len(raw.encode("utf-8")) > settings.max_ws_message_bytes:
        raise ProtocolError("message too large")
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ProtocolError("invalid JSON") from exc
    if not isinstance(obj, dict):
        raise ProtocolError("JSON object required")
    return obj


@app.get("/health")
async def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "service": "t2-online-gateway",
        "protocol": 1,
        "game_backend": "detached",
    }


@app.get("/v1/me")
async def me(identity: Identity = Depends(current_identity)) -> dict[str, Any]:
    return {"user": identity.public_dict()}


@app.get("/v1/server-state")
async def server_state(
    request: Request,
    identity: Identity = Depends(current_identity),
) -> dict[str, Any]:
    registry: ConnectionRegistry = request.app.state.registry
    return {
        "user": {"uid": identity.uid},
        "realtime": await registry.snapshot(),
        "game_backend": "detached",
    }


@app.websocket("/v1/ws")
async def websocket_gateway(websocket: WebSocket) -> None:
    await websocket.accept()

    settings: Settings = websocket.app.state.settings
    auth_service: AuthService = websocket.app.state.auth
    registry: ConnectionRegistry = websocket.app.state.registry
    connection_id: str | None = None

    try:
        try:
            first = await asyncio.wait_for(
                _receive_object(websocket, settings),
                timeout=settings.ws_auth_timeout_seconds,
            )
        except asyncio.TimeoutError:
            await websocket.send_json(
                {"type": "auth.error", "error": "authentication timeout"}
            )
            await websocket.close(code=4401)
            return
        except ProtocolError as exc:
            await websocket.send_json({"type": "auth.error", "error": str(exc)})
            await websocket.close(code=4400)
            return

        if first.get("type") != "auth" or not isinstance(first.get("id_token"), str):
            await websocket.send_json(
                {"type": "auth.error", "error": "first message must be auth"}
            )
            await websocket.close(code=4401)
            return

        try:
            identity = auth_service.verify(first["id_token"])
        except AuthError as exc:
            await websocket.send_json({"type": "auth.error", "error": str(exc)})
            await websocket.close(code=4401)
            return

        info = await registry.connect(identity.uid)
        connection_id = info.connection_id
        await websocket.send_json(
            {
                "type": "auth.ok",
                "protocol": 1,
                "connection_id": connection_id,
                "user": identity.public_dict(),
                "capabilities": ["ping", "server.state"],
                "game_backend": "detached",
            }
        )

        while True:
            try:
                message = await _receive_object(websocket, settings)
            except ProtocolError as exc:
                if str(exc) == "message too large":
                    await websocket.close(code=1009)
                    return
                await websocket.send_json(
                    {"type": "error", "error": "bad_message", "detail": str(exc)}
                )
                continue

            await registry.touch(connection_id)
            message_type = message.get("type")

            if message_type == "ping":
                await websocket.send_json(
                    {
                        "type": "pong",
                        "client_id": message.get("client_id"),
                        "server_time_ms": int(time.time() * 1000),
                    }
                )
                continue

            if message_type == "server.state":
                await websocket.send_json(
                    {
                        "type": "server.state",
                        "realtime": await registry.snapshot(),
                        "game_backend": "detached",
                    }
                )
                continue

            if isinstance(message_type, str) and message_type.startswith("game."):
                await websocket.send_json(
                    {
                        "type": "error",
                        "error": "game_backend_not_attached",
                        "detail": (
                            "The online transport/auth boundary is ready, "
                            "but the existing poker engine has not been attached yet."
                        ),
                    }
                )
                continue

            await websocket.send_json(
                {
                    "type": "error",
                    "error": "unsupported_message",
                    "detail": str(message_type),
                }
            )

    except WebSocketDisconnect:
        pass
    finally:
        if connection_id is not None:
            await registry.disconnect(connection_id)
