from __future__ import annotations

import asyncio
import hashlib
import json
import os
import threading
from pathlib import Path
from typing import Any

from online_server.config import Settings


class GameError(Exception):
    def __init__(self, code: str, detail: str):
        super().__init__(detail)
        self.code = code
        self.detail = detail


_SAFE_RAW_KEYS = {
    "stage", "street", "pos", "hole", "board", "stacks", "contrib",
    "pot", "tocall", "stack", "min_raise", "max_raise", "raise_to_min",
    "can_raise", "can_check", "can_bet", "legal", "live", "allin",
    "log", "hash",
}


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, set):
        return [_json_safe(v) for v in sorted(value, key=lambda x: str(x))]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _safe_raw(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    return {
        key: _json_safe(raw[key])
        for key in _SAFE_RAW_KEYS
        if key in raw
    }


class GameEngine:
    """Single-user authoritative adapter around the existing T2 live engine.

    Stage 2 intentionally supports one 9-max table only.  It serializes every
    command because the existing live2 engine owns process-global state.
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self._mutex = threading.RLock()

        data_dir = Path(settings.online_data_dir).expanduser().resolve()
        data_dir.mkdir(parents=True, exist_ok=True)
        self.data_dir = data_dir
        self.state_path = data_dir / "live2_state.json"
        self.public_state_path = data_dir / "public_state.json"

        # live2 resolves ST and its sidecar namespace at import time.
        os.environ["T2_LIVE_STATE"] = str(self.state_path)

        import live2 as live_engine

        expected = os.path.realpath(str(self.state_path))
        actual = os.path.realpath(str(live_engine.ST))
        if actual != expected:
            raise RuntimeError(
                "live2 was imported before T2 online state isolation was set: "
                f"{actual} != {expected}"
            )
        self.live = live_engine

    def _authorize(self, uid: str) -> None:
        if self.settings.single_user_uid:
            if uid != self.settings.single_user_uid:
                raise GameError("forbidden_user", "this user does not own this game")
            return
        if self.settings.auth_mode == "dev":
            return
        raise GameError(
            "single_user_not_configured",
            "Set T2_SINGLE_USER_UID before enabling the Firebase game backend.",
        )

    def _load_state(self) -> dict[str, Any]:
        try:
            return self.live.load()
        except RuntimeError as exc:
            raise GameError("no_game", "no online game exists yet") from exc

    @staticmethod
    def _action_token(st: dict[str, Any]) -> str:
        field = st.get("field") or {}
        material = {
            "hand_no": field.get("hand_no"),
            "hero_pid": field.get("hero_pid"),
            "hero": (field.get("players") or {}).get(str(field.get("hero_pid"))),
            "hand_seed": st.get("hand_seed"),
            "actions": st.get("actions") or [],
            "decisions_n": len(st.get("decisions") or []),
            "busted": bool(st.get("busted")),
            "rank": st.get("rank"),
        }
        blob = json.dumps(
            material, ensure_ascii=False, sort_keys=True,
            separators=(",", ":"), default=str,
        ).encode("utf-8")
        return hashlib.sha256(blob).hexdigest()[:32]

    @staticmethod
    def _summary(st: dict[str, Any]) -> dict[str, Any]:
        field = st.get("field") or {}
        players = field.get("players") or {}
        hero_pid = field.get("hero_pid")
        hero = players.get(str(hero_pid), {}) if hero_pid is not None else {}
        remaining = sum(
            1 for row in players.values()
            if int(row.get("stack", 0) or 0) > 0
        )
        return {
            "hand_no": int(field.get("hand_no", 0) or 0),
            "entries": int(field.get("entries", 0) or 0),
            "remaining": remaining,
            "hero_stack": int(hero.get("stack", 0) or 0),
            "hero_table": hero.get("table"),
            "hero_seat": hero.get("seat"),
            "busted": bool(st.get("busted")),
            "rank": st.get("rank"),
            "hand_in_progress": st.get("hand_seed") is not None,
        }

    def _public_response(self, out: dict[str, Any] | None = None) -> dict[str, Any]:
        st = self._load_state()
        done = bool((out or {}).get("done"))
        response = {
            "exists": True,
            "token": self._action_token(st),
            "phase": (
                "decision" if st.get("hand_seed") is not None and not done
                else "hand_result" if done
                else "between_hands"
            ),
            "summary": self._summary(st),
            "done": done,
            "view": (out or {}).get("view"),
            "state": _safe_raw((out or {}).get("raw")),
            "busted": bool((out or {}).get("busted", st.get("busted"))),
            "rank": (out or {}).get("rank", st.get("rank")),
        }
        return _json_safe(response)

    def _persist_public(self, payload: dict[str, Any]) -> None:
        tmp = self.public_state_path.with_suffix(".json.tmp")
        with open(tmp, "w", encoding="utf-8") as fp:
            json.dump(payload, fp, ensure_ascii=False, separators=(",", ":"))
            fp.flush()
            os.fsync(fp.fileno())
        os.replace(tmp, self.public_state_path)

    def _read_public(self) -> dict[str, Any] | None:
        try:
            with open(self.public_state_path, encoding="utf-8") as fp:
                value = json.load(fp)
            return value if isinstance(value, dict) else None
        except (OSError, ValueError):
            return None

    def _sync_new_game(
        self,
        uid: str,
        *,
        seed: int | None = None,
        start_stack: int = 30000,
    ) -> dict[str, Any]:
        self._authorize(uid)
        if not 1000 <= int(start_stack) <= 100_000_000:
            raise GameError("bad_start_stack", "start_stack is out of range")

        with self._mutex:
            # Stage 2 is deliberately fixed to one 9-max table.
            self.live.new_game(
                entries=9,
                start_stack=int(start_stack),
                seed=seed,
                fmt="standard",
            )
            out = self.live.step()
            payload = self._public_response(out)
            self._persist_public(payload)
            return payload

    def _sync_state(self, uid: str) -> dict[str, Any]:
        self._authorize(uid)
        with self._mutex:
            if not self.state_path.exists():
                return {"exists": False, "phase": "no_game"}

            st = self._load_state()
            current_token = self._action_token(st)
            cached = self._read_public()
            if cached and cached.get("token") == current_token:
                return cached

            # Never advance the poker engine from a read-only state request.
            payload = {
                "exists": True,
                "token": current_token,
                "phase": (
                    "decision_recovery" if st.get("hand_seed") is not None
                    else "between_hands"
                ),
                "summary": self._summary(st),
                "done": False,
                "view": None,
                "state": None,
                "recovery_required": st.get("hand_seed") is not None,
                "busted": bool(st.get("busted")),
                "rank": st.get("rank"),
            }
            return _json_safe(payload)

    def _check_token(self, st: dict[str, Any], token: str) -> None:
        expected = self._action_token(st)
        if not token or token != expected:
            raise GameError(
                "stale_action",
                "action token is stale; reload the authoritative game state",
            )

    def _sync_action(
        self,
        uid: str,
        *,
        token: str,
        action: str,
        amount: int = 0,
    ) -> dict[str, Any]:
        self._authorize(uid)
        action = str(action or "").strip().lower()
        if action not in {"fold", "check", "call", "bet", "raise", "allin"}:
            raise GameError("bad_action", "unsupported poker action")
        try:
            amount = int(amount or 0)
        except (TypeError, ValueError) as exc:
            raise GameError("bad_amount", "amount must be an integer") from exc
        if amount < 0:
            raise GameError("bad_amount", "amount must be non-negative")

        with self._mutex:
            st = self._load_state()
            self._check_token(st, token)
            if st.get("hand_seed") is None:
                raise GameError("no_decision", "there is no hand awaiting an action")

            out = self.live.step(action, amount)
            if isinstance(out, dict):
                raw = out.get("raw")
                if isinstance(raw, dict) and raw.get("error"):
                    raise GameError("illegal_action", str(raw.get("error")))

            payload = self._public_response(out)
            self._persist_public(payload)
            return payload

    def _sync_next(self, uid: str, *, token: str) -> dict[str, Any]:
        self._authorize(uid)
        with self._mutex:
            st = self._load_state()
            self._check_token(st, token)
            if st.get("busted"):
                raise GameError("game_over", "the hero has been eliminated")
            if st.get("hand_seed") is not None:
                raise GameError("hand_in_progress", "finish the current hand first")

            out = self.live.step()
            payload = self._public_response(out)
            self._persist_public(payload)
            return payload

    async def new_game(
        self, uid: str, *, seed: int | None = None, start_stack: int = 30000
    ) -> dict[str, Any]:
        return await asyncio.to_thread(
            self._sync_new_game, uid, seed=seed, start_stack=start_stack
        )

    async def state(self, uid: str) -> dict[str, Any]:
        return await asyncio.to_thread(self._sync_state, uid)

    async def action(
        self, uid: str, *, token: str, action: str, amount: int = 0
    ) -> dict[str, Any]:
        return await asyncio.to_thread(
            self._sync_action, uid, token=token, action=action, amount=amount
        )

    async def next_hand(self, uid: str, *, token: str) -> dict[str, Any]:
        return await asyncio.to_thread(self._sync_next, uid, token=token)
