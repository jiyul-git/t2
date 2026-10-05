#!/usr/bin/env python3
"""Dependency-light checks for the test2 online server boundary."""

import asyncio
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from online_server.auth import AuthError, AuthService
from online_server.config import Settings
from online_server.registry import ConnectionRegistry


def _settings(**overrides):
    base = dict(
        auth_mode="dev",
        firebase_project_id=None,
        single_user_uid="only-user",
        allow_dev_auth=True,
        dev_token="0123456789abcdef0123456789abcdef",
        online_data_dir=tempfile.gettempdir(),
    )
    base.update(overrides)
    return Settings(**base)


def verify_auth() -> None:
    token = "0123456789abcdef0123456789abcdef"
    settings = _settings().validate()
    service = AuthService(settings)

    identity = service.verify(token)
    assert identity.uid == "only-user"
    assert identity.provider == "dev"

    try:
        service.verify("wrong-token")
    except AuthError:
        pass
    else:
        raise AssertionError("wrong dev token was accepted")


def verify_config_guards() -> None:
    try:
        _settings(allow_dev_auth=False).validate()
    except RuntimeError:
        pass
    else:
        raise AssertionError("dev auth started without explicit enable flag")

    try:
        _settings(
            auth_mode="firebase",
            firebase_project_id=None,
            single_user_uid=None,
            allow_dev_auth=False,
            dev_token=None,
        ).validate()
    except RuntimeError:
        pass
    else:
        raise AssertionError("firebase auth started without a project id")

    try:
        _settings(online_data_dir="").validate()
    except RuntimeError:
        pass
    else:
        raise AssertionError("empty online data dir was accepted")


async def verify_registry() -> None:
    registry = ConnectionRegistry()
    first = await registry.connect("u1")
    second = await registry.connect("u1")
    third = await registry.connect("u2")

    snap = await registry.snapshot()
    assert snap["connections"] == 3
    assert snap["users"] == 2
    assert snap["connections_per_user"] == {"u1": 2, "u2": 1}

    await registry.touch(first.connection_id)
    await registry.disconnect(second.connection_id)
    await registry.disconnect(third.connection_id)
    snap = await registry.snapshot()
    assert snap["connections"] == 1
    assert snap["users"] == 1


def main() -> None:
    verify_auth()
    verify_config_guards()
    asyncio.run(verify_registry())
    print("online_server verifier: PASS")


if __name__ == "__main__":
    main()
