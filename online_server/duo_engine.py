from __future__ import annotations

import asyncio
import copy
import hashlib
import json
import os
import threading
import time
import zlib
from pathlib import Path
from typing import Any

from online_server.config import Settings
from online_server.engine import GameError


class DuoTournamentEngine:
    """Two authenticated humans in one 9-max tournament field.

    The humans are not forced onto the same table.  Any table containing at
    least one surviving human is interactive; bot-only tables are advanced by
    the existing field simulator when the current synchronized round settles.

    This v1 intentionally uses a round barrier between interactive tables.  It
    keeps cross-table tournament state deterministic while validating the
    multiplayer ownership model.  Later the existing independent virtual-clock
    scheduler can replace this barrier without changing the HTTP contract.
    """

    VERSION = 1
    ROOM_ID = "home-duo"

    def __init__(self, settings: Settings):
        self.settings = settings
        self._lock = threading.RLock()
        self.data_dir = Path(settings.online_data_dir).expanduser().resolve()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.data_dir / "duo_room.json"

        import fieldsim as FS
        import live2 as L
        import play
        import session as SE

        self.FS = FS
        self.L = L
        self.play = play
        self.SE = SE

    # ---------- durable room ----------
    def _blank(self) -> dict[str, Any]:
        return {
            "version": self.VERSION,
            "room_id": self.ROOM_ID,
            "revision": 0,
            "created_at": time.time(),
            "players": [],
            "started": False,
            "finished": False,
            "entries": int(os.getenv("T2_DUO_ENTRIES", "18") or 18),
            "start_stack": int(os.getenv("T2_DUO_START_STACK", "30000") or 30000),
            "seed": None,
            "field": None,
            "round_no": 0,
            "round": None,
        }

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return self._blank()
        try:
            with open(self.path, encoding="utf-8") as fp:
                state = json.load(fp)
        except (OSError, ValueError) as exc:
            raise GameError("room_state_corrupt", "duo room state is unreadable") from exc
        if not isinstance(state, dict) or state.get("version") != self.VERSION:
            raise GameError("room_state_version", "duo room state version mismatch")
        return state

    def _save(self, state: dict[str, Any]) -> None:
        state["revision"] = int(state.get("revision", 0)) + 1
        tmp = self.path.with_suffix(".json.tmp")
        with open(tmp, "w", encoding="utf-8") as fp:
            json.dump(state, fp, ensure_ascii=False, separators=(",", ":"))
            fp.flush()
            os.fsync(fp.fileno())
        os.replace(tmp, self.path)

    @staticmethod
    def _player_row(state: dict[str, Any], uid: str) -> dict[str, Any] | None:
        return next((p for p in state.get("players", []) if p.get("uid") == uid), None)

    def _require_player(self, state: dict[str, Any], uid: str) -> dict[str, Any]:
        row = self._player_row(state, uid)
        if row is None:
            raise GameError("not_joined", "join the two-player room first")
        return row

    # ---------- tournament lifecycle ----------
    def _start_tournament(self, state: dict[str, Any]) -> None:
        if len(state["players"]) != 2:
            return

        entries = max(9, min(200, int(state.get("entries") or 18)))
        start_stack = max(1000, int(state.get("start_stack") or 30000))
        seed = state.get("seed")
        if seed is None:
            seed = int.from_bytes(os.urandom(4), "big")
            state["seed"] = seed

        # Join order owns pid 0 and pid 1.  The Field shuffles all seats normally,
        # so the two humans may land on the same table or on different tables.
        for idx, p in enumerate(state["players"]):
            p["pid"] = idx

        f = self.FS.Field(
            entries=entries,
            start_stack=start_stack,
            hero_pid=0,
            human_pids=[0, 1],
            seed=int(seed),
            fmt="standard",
        )
        state["entries"] = entries
        state["start_stack"] = start_stack
        state["field"] = self.L._dump(f)
        state["started"] = True
        state["finished"] = False
        state["round_no"] = 0
        state["round"] = None
        self._begin_round(state)

    def _begin_round(self, state: dict[str, Any]) -> None:
        if not state.get("started") or state.get("finished"):
            return

        f = self.L._load_field(copy.deepcopy(state["field"]))
        alive_humans = [
            pid for pid in sorted(getattr(f, "human_pids", set()))
            if pid in f.players and f.players[pid].get("stack", 0) > 0
        ]
        if f.remaining() <= 1 or not alive_humans:
            state["finished"] = True
            state["round"] = None
            state["field"] = self.L._dump(f)
            return

        f.hand_no += 1
        f.advance_level()
        f.notes = []
        base = self.L._dump(f)

        human_tables = sorted(f.human_tables())
        hands: dict[str, Any] = {}
        next_round = int(state.get("round_no", 0)) + 1
        for tid in human_tables:
            tb = f.tables.get(tid)
            if tb is None or tb.n() < 2:
                continue
            seed = zlib.crc32(
                f"{state.get('seed')}|duo|{next_round}|{tid}".encode()
            ) % (10**9)
            hands[str(tid)] = {
                "table_id": int(tid),
                "seed": int(seed),
                "actions": [],
                "decisions": [],
                "complete": False,
                "commit": None,
                "result": None,
            }

        if not hands:
            state["finished"] = True
            state["round"] = None
            state["field"] = base
            return

        state["round_no"] = next_round
        state["round"] = {
            "base": base,
            "hands": hands,
            "started_at": time.time(),
        }

    # ---------- hand replay ----------
    def _build_hand(
        self,
        base: dict[str, Any],
        rec: dict[str, Any],
    ):
        f = self.L._load_field(copy.deepcopy(base))
        tid = int(rec["table_id"])
        tb = f.tables[tid]
        alive = tb.ordered_alive()
        if len(alive) < 2:
            raise GameError("table_closed", "interactive table has fewer than two players")

        layout = tb.hand_layout()
        seats = [tb.seat_of(p["pid"]) for p in alive]
        profs = {str(tb.seat_of(p["pid"])): p["prof"] for p in alive}
        stacks = {tb.seat_of(p["pid"]): p["stack"] for p in alive}
        human_seats = {
            tb.seat_of(p["pid"])
            for p in alive
            if p["pid"] in getattr(f, "human_pids", set())
        }
        human_seats.discard(None)
        hero = min(human_seats) if human_seats else None
        sb, bb = f.blinds()

        h = self.play.Hand(
            seats,
            profs,
            stacks,
            layout["button"],
            sb,
            bb,
            hero=hero,
            human_seats=human_seats,
            seed=int(rec["seed"]),
            book=f.book,
            position_map=layout["pos"],
            pre_seats=layout["pre_seats"],
            post_seats=layout["post_seats"],
            sb_seat=layout["sb"],
            bb_seat=layout["bb"],
        )
        h.seat_pid = {tb.seat_of(p["pid"]): p["pid"] for p in alive}
        h.table_id = tb.id
        h.table_max_seat = tb.max_seat
        f.stamp(h)

        run = self.SE.HandRun(h, decisions=rec.get("decisions") or [])
        raw = run.start()

        for row in rec.get("actions") or []:
            if not isinstance(raw, dict) or raw.get("done"):
                raise GameError("replay_mismatch", "saved human action outlived the hand")
            actor_pid = int(raw.get("actor_pid"))
            if actor_pid != int(row["pid"]):
                raise GameError("replay_mismatch", "saved human action owner mismatch")
            raw = run.send(str(row["action"]), int(row.get("amount", 0) or 0))
            if isinstance(raw, dict) and raw.get("error"):
                raise GameError("replay_mismatch", str(raw.get("error")))

        return f, tb, alive, h, run, raw

    @staticmethod
    def _book_subset(packed: dict[str, Any], pids: list[int]) -> dict[str, Any]:
        owners = {str(x) for x in pids}
        return {
            k: copy.deepcopy(v)
            for k, v in (packed or {}).items()
            if str(k).partition(">")[0] in owners
        }

    def _make_commit(self, f, tb, alive, h, run) -> dict[str, Any]:
        for p in alive:
            seat = tb.seat_of(p["pid"])
            if seat is not None:
                p["stack"] = int(h.stacks.get(seat, p["stack"]))

        tb.advance_button()
        tb.hands += 1
        out = self.L._dump(f)
        pids = [int(p["pid"]) for p in alive]
        return {
            "players": {
                str(pid): copy.deepcopy(out["players"][str(pid)])
                for pid in pids
                if str(pid) in out["players"]
            },
            "table": copy.deepcopy(out["tables"][str(tb.id)]),
            "tilt": {
                str(pid): copy.deepcopy((out.get("tilt") or {}).get(str(pid)))
                for pid in pids
                if str(pid) in (out.get("tilt") or {})
            },
            "book": self._book_subset(out.get("book") or {}, pids),
            "notes": list(getattr(f, "notes", []) or []),
            "result": self._sanitize_result(run.result or {}),
        }

    @staticmethod
    def _sanitize_result(result: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(result, dict):
            return {}
        keep = {
            "how", "winners", "main_winners", "pot", "showdown", "board",
            "pots", "shown_hole", "show_order", "mucked", "allin_show",
            "best_five", "stacks", "hash", "full_log", "pos", "note",
        }
        return {
            str(k): copy.deepcopy(v)
            for k, v in result.items()
            if k in keep
        }

    def _merge_commit(self, f, tid: int, commit: dict[str, Any], blind_state: str) -> None:
        for pid_s, row in (commit.get("players") or {}).items():
            pid = int(pid_s)
            if pid not in f.players:
                raise GameError("merge_mismatch", "interactive player missing from field")
            p = f.players[pid]
            p["stack"] = int(row["stack"])
            p["table"] = row.get("table")
            p["seat"] = row.get("seat")

        f.tables[int(tid)] = self.L._restore_table(
            f,
            tid,
            commit["table"],
            blind_state,
        )

        for pid_s, row in (commit.get("tilt") or {}).items():
            if row is not None:
                f.tilt.state[str(pid_s)] = copy.deepcopy(row)

        owners = {str(x) for x in (commit.get("players") or {})}
        packed = f.book_packed()
        for key in [
            k for k in packed
            if str(k).partition(">")[0] in owners
        ]:
            packed.pop(key, None)
        packed.update(copy.deepcopy(commit.get("book") or {}))
        f.set_book_packed(packed)

    def _settle_round_if_ready(self, state: dict[str, Any]) -> bool:
        rnd = state.get("round")
        if not rnd:
            return False
        hands = rnd.get("hands") or {}
        if not hands or not all(bool(x.get("complete")) for x in hands.values()):
            return False

        base = copy.deepcopy(rnd["base"])
        f = self.L._load_field(base)
        blind_state = base.get("blind_state")
        for tid_s in sorted(hands, key=lambda x: int(x)):
            rec = hands[tid_s]
            self._merge_commit(f, int(tid_s), rec["commit"], blind_state)

        # Existing field simulator advances every table that has no surviving
        # human.  Human tables were already resolved above and are protected by
        # Field.human_tables().
        f.step_others(settle=False, simultaneous=True)
        f._collect_busts()
        f._balance()

        state["field"] = self.L._dump(f)
        state["round"] = None
        if f.remaining() <= 1:
            state["finished"] = True
        else:
            self._begin_round(state)
        return True

    # ---------- user-specific public state ----------
    @staticmethod
    def _rank_for(f, pid: int) -> int | None:
        p = f.players.get(pid)
        if not p:
            return None
        if p.get("stack", 0) > 0:
            stacks = sorted(
                (x.get("stack", 0) for x in f.players.values() if x.get("stack", 0) > 0),
                reverse=True,
            )
            try:
                return stacks.index(p["stack"]) + 1
            except ValueError:
                return None
        if pid in f.busted_order:
            after = len(f.busted_order) - f.busted_order.index(pid) - 1
            return f.remaining() + 1 + after
        return None

    def _token(
        self,
        state: dict[str, Any],
        pid: int,
        tid: int,
        rec: dict[str, Any],
        raw: dict[str, Any],
    ) -> str:
        material = {
            "room": state.get("room_id"),
            "revision": state.get("revision"),
            "round": state.get("round_no"),
            "table": tid,
            "pid": pid,
            "actions": len(rec.get("actions") or []),
            "actor": raw.get("actor_pid"),
            "hash": raw.get("hash"),
            "stage": raw.get("stage"),
        }
        return hashlib.sha256(
            json.dumps(material, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()[:32]

    def _public_table(
        self,
        f,
        tb,
        h,
        raw: dict[str, Any],
        me_pid: int,
    ) -> dict[str, Any]:
        me_seat = tb.seat_of(me_pid)
        stacks = raw.get("stacks") or {}
        contrib = raw.get("contrib") or {}
        live = set(raw.get("live") or [])
        allin = set(raw.get("allin") or [])
        seats = []
        for p in tb.ordered_alive():
            seat = tb.seat_of(p["pid"])
            seats.append({
                "seat": seat,
                "pid": int(p["pid"]),
                "me": int(p["pid"]) == int(me_pid),
                "pos": h.pos.get(seat),
                "stack": int(stacks.get(seat, p.get("stack", 0)) or 0),
                "bet": int(contrib.get(seat, 0) or 0),
                "in_hand": seat in live,
                "allin": seat in allin,
            })

        tc = int(raw.get("tocall", 0) or 0)
        actor_seat = raw.get("actor_seat")
        actor_stack = int(raw.get("stack", 0) or 0)
        actor_contrib = int(contrib.get(actor_seat, 0) or 0) if actor_seat else 0
        max_to = actor_contrib + actor_stack
        min_to = int(raw.get("min_raise", 0) or 0)
        stage = raw.get("stage")
        wager_action = "raise"
        if stage != "preflop" and max((int(v or 0) for v in contrib.values()), default=0) == 0:
            wager_action = "bet"

        legal = {
            "fold": tc > 0,
            "check": tc == 0,
            "call": tc if tc > 0 else None,
            "allin": actor_stack > 0,
            "wager_action": wager_action,
            "raise": (
                {"min_to": min_to, "max_to": max_to}
                if raw.get("can_raise") and max_to >= min_to and actor_stack > 0
                else None
            ),
        }

        return {
            "id": int(tb.id),
            "actor_pid": int(raw["actor_pid"]) if raw.get("actor_pid") is not None else None,
            "actor_seat": actor_seat,
            "stage": stage,
            "board": list(raw.get("board") or []),
            "hole": list(h.hole.get(me_seat, [])) if me_seat is not None else [],
            "pot": int(raw.get("pot", 0) or 0),
            "pot_total": int(raw.get("pot_total", raw.get("pot", 0)) or 0),
            "tocall": tc,
            "legal": legal,
            "log": copy.deepcopy(raw.get("log") or []),
            "seats": seats,
        }

    def _public(self, state: dict[str, Any], uid: str) -> dict[str, Any]:
        player = self._player_row(state, uid)
        if player is None:
            return {
                "room_id": self.ROOM_ID,
                "joined": False,
                "started": bool(state.get("started")),
                "phase": "not_joined",
                "players_joined": len(state.get("players") or []),
                "capacity": 2,
            }

        base_out = {
            "room_id": self.ROOM_ID,
            "joined": True,
            "slot": int(player.get("slot", 0)),
            "players_joined": len(state.get("players") or []),
            "capacity": 2,
            "started": bool(state.get("started")),
            "finished": bool(state.get("finished")),
            "revision": int(state.get("revision", 0)),
        }
        if not state.get("started"):
            base_out["phase"] = "waiting_player"
            return base_out

        pid = int(player["pid"])
        field_dump = (
            (state.get("round") or {}).get("base")
            or state.get("field")
        )
        f = self.L._load_field(copy.deepcopy(field_dump))
        p = f.players.get(pid)
        if p is None:
            raise GameError("player_missing", "human pid missing from tournament")

        base_out["me"] = {
            "pid": pid,
            "stack": int(p.get("stack", 0) or 0),
            "table": p.get("table"),
            "seat": p.get("seat"),
            "rank": self._rank_for(f, pid),
            "alive": p.get("stack", 0) > 0,
        }
        base_out["tournament"] = {
            "entries": int(f.entries),
            "remaining": int(f.remaining()),
            "itm": int(f.itm),
            "level": int(f.level),
            "hand_no": int(f.hand_no),
            "tables": len(f.tables),
        }

        if state.get("finished") or p.get("stack", 0) <= 0:
            base_out["phase"] = "game_over" if state.get("finished") else "busted"
            return base_out

        rnd = state.get("round")
        if not rnd:
            base_out["phase"] = "settling"
            return base_out

        tid = int(p["table"])
        rec = (rnd.get("hands") or {}).get(str(tid))
        if rec is None:
            # This can happen only transiently around a balance/round boundary.
            base_out["phase"] = "waiting_round"
            return base_out

        if rec.get("complete"):
            base_out["phase"] = "waiting_round"
            base_out["result"] = copy.deepcopy(rec.get("result") or {})
            return base_out

        f2, tb, _alive, h, _run, raw = self._build_hand(rnd["base"], rec)
        if not isinstance(raw, dict) or raw.get("done"):
            base_out["phase"] = "waiting_round"
            return base_out

        actor_pid = int(raw.get("actor_pid"))
        base_out["phase"] = "decision" if actor_pid == pid else "waiting_other"
        base_out["table"] = self._public_table(f2, tb, h, raw, pid)
        if actor_pid == pid:
            base_out["token"] = self._token(state, pid, tid, rec, raw)
        return base_out

    # ---------- commands ----------
    def _sync_join(self, uid: str) -> dict[str, Any]:
        with self._lock:
            state = self._load()
            row = self._player_row(state, uid)
            if row is None:
                if len(state["players"]) >= 2:
                    raise GameError("room_full", "this test room already has two players")
                row = {
                    "uid": uid,
                    "slot": len(state["players"]) + 1,
                    "pid": None,
                    "joined_at": time.time(),
                }
                state["players"].append(row)
                if len(state["players"]) == 2:
                    self._start_tournament(state)
                self._save(state)
            return self._public(state, uid)

    def _sync_state(self, uid: str) -> dict[str, Any]:
        with self._lock:
            state = self._load()
            return self._public(state, uid)

    def _sync_action(
        self,
        uid: str,
        token: str,
        action: str,
        amount: int = 0,
    ) -> dict[str, Any]:
        with self._lock:
            state = self._load()
            player = self._require_player(state, uid)
            if not state.get("started") or state.get("finished"):
                raise GameError("no_active_tournament", "the duo tournament is not active")

            pid = int(player["pid"])
            rnd = state.get("round")
            if not rnd:
                raise GameError("round_settling", "the tournament round is settling")

            f = self.L._load_field(copy.deepcopy(rnd["base"]))
            p = f.players.get(pid)
            if not p or p.get("stack", 0) <= 0 or p.get("table") is None:
                raise GameError("player_busted", "this player is no longer active")

            tid = int(p["table"])
            rec = (rnd.get("hands") or {}).get(str(tid))
            if not rec or rec.get("complete"):
                raise GameError("no_decision", "this table is not waiting for an action")

            f2, tb, alive, h, run, raw = self._build_hand(rnd["base"], rec)
            if not isinstance(raw, dict) or raw.get("done"):
                raise GameError("no_decision", "this hand is already complete")
            if int(raw.get("actor_pid")) != pid:
                raise GameError("not_your_turn", "another human player is acting")

            expected = self._token(state, pid, tid, rec, raw)
            if not token or token != expected:
                raise GameError("stale_action", "reload the latest multiplayer state")

            action = str(action or "").strip().lower()
            if action not in {"fold", "check", "call", "bet", "raise", "allin"}:
                raise GameError("bad_action", "unsupported poker action")
            try:
                amount = int(amount or 0)
            except (TypeError, ValueError) as exc:
                raise GameError("bad_amount", "amount must be an integer") from exc
            if amount < 0:
                raise GameError("bad_amount", "amount must be non-negative")

            out = run.send(action, amount)
            if isinstance(out, dict) and out.get("error"):
                raise GameError("illegal_action", str(out.get("error")))

            rec["actions"].append({
                "pid": pid,
                "action": action,
                "amount": amount,
            })
            rec["decisions"] = [list(x) for x in run.recorded]

            if isinstance(out, dict) and out.get("done"):
                commit = self._make_commit(f2, tb, alive, h, run)
                rec["complete"] = True
                rec["commit"] = commit
                rec["result"] = copy.deepcopy(commit.get("result") or {})

            settled = self._settle_round_if_ready(state)
            self._save(state)
            return self._public(state, uid)

    def _sync_reset(self, uid: str) -> dict[str, Any]:
        with self._lock:
            state = self._load()
            player = self._require_player(state, uid)
            if int(player.get("slot", 0)) != 1:
                raise GameError("reset_forbidden", "only room slot 1 may reset the test room")
            fresh = self._blank()
            fresh["players"] = [
                {
                    "uid": uid,
                    "slot": 1,
                    "pid": None,
                    "joined_at": time.time(),
                }
            ]
            self._save(fresh)
            return self._public(fresh, uid)

    async def join(self, uid: str) -> dict[str, Any]:
        return await asyncio.to_thread(self._sync_join, uid)

    async def state(self, uid: str) -> dict[str, Any]:
        return await asyncio.to_thread(self._sync_state, uid)

    async def action(
        self,
        uid: str,
        token: str,
        action: str,
        amount: int = 0,
    ) -> dict[str, Any]:
        return await asyncio.to_thread(
            self._sync_action,
            uid,
            token,
            action,
            amount,
        )

    async def reset(self, uid: str) -> dict[str, Any]:
        return await asyncio.to_thread(self._sync_reset, uid)
