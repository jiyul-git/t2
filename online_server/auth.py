from __future__ import annotations

import hmac
from dataclasses import dataclass
from typing import Any

from online_server.config import Settings


class AuthError(Exception):
    pass


@dataclass(frozen=True)
class Identity:
    uid: str
    email: str | None = None
    name: str | None = None
    provider: str = "unknown"

    def public_dict(self) -> dict[str, Any]:
        return {
            "uid": self.uid,
            "email": self.email,
            "name": self.name,
            "provider": self.provider,
        }


class AuthService:
    """Verify identity tokens without trusting client-supplied user IDs."""

    _firebase_app: Any = None

    def __init__(self, settings: Settings):
        self.settings = settings

    def verify(self, token: str) -> Identity:
        token = (token or "").strip()
        if not token or len(token) > 32_768:
            raise AuthError("invalid authentication token")

        if self.settings.auth_mode == "dev":
            identity = self._verify_dev(token)
        else:
            identity = self._verify_firebase(token)

        allowed_uid = self.settings.single_user_uid
        if allowed_uid and identity.uid != allowed_uid:
            raise AuthError("this account is not allowed on this server")
        return identity

    def _verify_dev(self, token: str) -> Identity:
        expected = self.settings.dev_token or ""
        if not hmac.compare_digest(token, expected):
            raise AuthError("invalid development token")
        return Identity(
            uid=self.settings.single_user_uid or "dev-user",
            name="T2 local developer",
            provider="dev",
        )

    def _verify_firebase(self, token: str) -> Identity:
        try:
            import firebase_admin
            from firebase_admin import auth
        except ImportError as exc:
            raise AuthError("firebase-admin is not installed") from exc

        try:
            if self._firebase_app is None:
                try:
                    self._firebase_app = firebase_admin.get_app("t2-online")
                except ValueError:
                    self._firebase_app = firebase_admin.initialize_app(
                        options={"projectId": self.settings.firebase_project_id},
                        name="t2-online",
                    )

            decoded = auth.verify_id_token(
                token,
                app=self._firebase_app,
                check_revoked=True,
            )
        except Exception as exc:
            # Never return credential internals or token contents to a client.
            raise AuthError("Firebase ID token verification failed") from exc

        uid = str(decoded.get("uid") or decoded.get("sub") or "").strip()
        if not uid:
            raise AuthError("Firebase token has no uid")

        firebase_claim = decoded.get("firebase") or {}
        provider = str(firebase_claim.get("sign_in_provider") or "firebase")
        return Identity(
            uid=uid,
            email=decoded.get("email"),
            name=decoded.get("name"),
            provider=provider,
        )
