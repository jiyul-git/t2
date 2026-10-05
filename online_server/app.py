from __future__ import annotations

import asyncio
import json
import time
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Request, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from online_server.auth import AuthError, AuthService, Identity
from online_server.config import Settings, load_settings
from online_server.engine import GameEngine, GameError
from online_server.registry import ConnectionRegistry


class ProtocolError(Exception):
    pass


class NewGameRequest(BaseModel):
    seed: int | None = None
    start_stack: int = Field(default=30000, ge=1000, le=100_000_000)


class ActionRequest(BaseModel):
    token: str
    action: str
    amount: int = Field(default=0, ge=0)


class NextHandRequest(BaseModel):
    token: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = load_settings()
    app.state.settings = settings
    app.state.auth = AuthService(settings)
    app.state.registry = ConnectionRegistry()
    app.state.game = GameEngine(settings)
    yield


app = FastAPI(
    title="T2 Online Gateway",
    version="0.2.0",
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


def _raise_game_http(exc: GameError) -> None:
    if exc.code in {"forbidden_user", "single_user_not_configured"}:
        status = 403
    elif exc.code in {
        "stale_action", "no_decision", "hand_in_progress", "game_over", "no_game"
    }:
        status = 409
    else:
        status = 400
    raise HTTPException(
        status_code=status,
        detail={"code": exc.code, "message": exc.detail},
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
        "protocol": 2,
        "game_backend": "single_user_9max",
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
    game: GameEngine = request.app.state.game
    try:
        game_state = await game.state(identity.uid)
    except GameError as exc:
        game_state = {"error": exc.code, "detail": exc.detail}
    return {
        "user": {"uid": identity.uid},
        "realtime": await registry.snapshot(),
        "game_backend": "single_user_9max",
        "game": game_state,
    }


@app.get("/v1/game/state")
async def game_state(
    request: Request,
    identity: Identity = Depends(current_identity),
) -> dict[str, Any]:
    game: GameEngine = request.app.state.game
    try:
        return await game.state(identity.uid)
    except GameError as exc:
        _raise_game_http(exc)


@app.post("/v1/game/new")
async def game_new(
    body: NewGameRequest,
    request: Request,
    identity: Identity = Depends(current_identity),
) -> dict[str, Any]:
    game: GameEngine = request.app.state.game
    try:
        return await game.new_game(
            identity.uid,
            seed=body.seed,
            start_stack=body.start_stack,
        )
    except GameError as exc:
        _raise_game_http(exc)


@app.post("/v1/game/action")
async def game_action(
    body: ActionRequest,
    request: Request,
    identity: Identity = Depends(current_identity),
) -> dict[str, Any]:
    game: GameEngine = request.app.state.game
    try:
        return await game.action(
            identity.uid,
            token=body.token,
            action=body.action,
            amount=body.amount,
        )
    except GameError as exc:
        _raise_game_http(exc)


@app.post("/v1/game/next")
async def game_next(
    body: NextHandRequest,
    request: Request,
    identity: Identity = Depends(current_identity),
) -> dict[str, Any]:
    game: GameEngine = request.app.state.game
    try:
        return await game.next_hand(identity.uid, token=body.token)
    except GameError as exc:
        _raise_game_http(exc)


async def _ws_game_message(
    websocket: WebSocket,
    game: GameEngine,
    identity: Identity,
    message: dict[str, Any],
) -> bool:
    message_type = message.get("type")
    if not isinstance(message_type, str) or not message_type.startswith("game."):
        return False

    try:
        if message_type == "game.state":
            payload = await game.state(identity.uid)
        elif message_type == "game.new":
            payload = await game.new_game(
                identity.uid,
                seed=message.get("seed"),
                start_stack=message.get("start_stack", 30000),
            )
        elif message_type == "game.action":
            payload = await game.action(
                identity.uid,
                token=str(message.get("token") or ""),
                action=str(message.get("action") or ""),
                amount=message.get("amount", 0),
            )
        elif message_type == "game.next":
            payload = await game.next_hand(
                identity.uid,
                token=str(message.get("token") or ""),
            )
        else:
            await websocket.send_json(
                {
                    "type": "error",
                    "error": "unsupported_game_message",
                    "detail": message_type,
                }
            )
            return True

        await websocket.send_json(
            {"type": f"{message_type}.ok", "payload": payload}
        )
    except GameError as exc:
        await websocket.send_json(
            {
                "type": f"{message_type}.error",
                "error": exc.code,
                "detail": exc.detail,
            }
        )
    except (TypeError, ValueError) as exc:
        await websocket.send_json(
            {
                "type": f"{message_type}.error",
                "error": "bad_request",
                "detail": str(exc),
            }
        )
    return True


@app.websocket("/v1/ws")
async def websocket_gateway(websocket: WebSocket) -> None:
    await websocket.accept()

    settings: Settings = websocket.app.state.settings
    auth_service: AuthService = websocket.app.state.auth
    registry: ConnectionRegistry = websocket.app.state.registry
    game: GameEngine = websocket.app.state.game
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
                "protocol": 2,
                "connection_id": connection_id,
                "user": identity.public_dict(),
                "capabilities": [
                    "ping", "server.state",
                    "game.state", "game.new", "game.action", "game.next",
                ],
                "game_backend": "single_user_9max",
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
                        "game_backend": "single_user_9max",
                    }
                )
                continue

            if await _ws_game_message(websocket, game, identity, message):
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
