from __future__ import annotations

import os
from dataclasses import dataclass


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    auth_mode: str
    firebase_project_id: str | None
    single_user_uid: str | None
    allow_dev_auth: bool
    dev_token: str | None
    ws_auth_timeout_seconds: float = 5.0
    max_ws_message_bytes: int = 64 * 1024

    def validate(self) -> "Settings":
        if self.auth_mode not in {"firebase", "dev"}:
            raise RuntimeError("T2_AUTH_MODE must be 'firebase' or 'dev'.")

        if self.auth_mode == "firebase" and not self.firebase_project_id:
            raise RuntimeError(
                "T2_FIREBASE_PROJECT_ID is required when T2_AUTH_MODE=firebase."
            )

        if self.auth_mode == "dev":
            if not self.allow_dev_auth:
                raise RuntimeError(
                    "Development authentication is disabled. "
                    "Set T2_ALLOW_DEV_AUTH=1 only for local testing."
                )
            if not self.dev_token or len(self.dev_token) < 24:
                raise RuntimeError(
                    "T2_DEV_TOKEN must be set to a random value of at least 24 characters."
                )

        if self.ws_auth_timeout_seconds <= 0:
            raise RuntimeError("T2_WS_AUTH_TIMEOUT_SECONDS must be > 0.")
        if self.max_ws_message_bytes < 1024:
            raise RuntimeError("T2_MAX_WS_MESSAGE_BYTES must be >= 1024.")
        return self


def load_settings() -> Settings:
    return Settings(
        auth_mode=os.getenv("T2_AUTH_MODE", "firebase").strip().lower(),
        firebase_project_id=(os.getenv("T2_FIREBASE_PROJECT_ID") or "").strip() or None,
        single_user_uid=(os.getenv("T2_SINGLE_USER_UID") or "").strip() or None,
        allow_dev_auth=_env_bool("T2_ALLOW_DEV_AUTH"),
        dev_token=(os.getenv("T2_DEV_TOKEN") or "").strip() or None,
        ws_auth_timeout_seconds=float(os.getenv("T2_WS_AUTH_TIMEOUT_SECONDS", "5")),
        max_ws_message_bytes=int(os.getenv("T2_MAX_WS_MESSAGE_BYTES", str(64 * 1024))),
    ).validate()
