# T2 online server prototype (test2)

This directory is a new network/authentication boundary. It does **not** replace
`ui/server/ui_server.py`, and it intentionally does not import the poker engine yet.

## Stage 1 scope

Implemented:

- FastAPI HTTP gateway
- WebSocket gateway at `/v1/ws`
- Firebase ID-token verification on the server
- explicit local-only development-token mode
- optional one-Firebase-UID allowlist via `T2_SINGLE_USER_UID`
- process-local connection registry
- authenticated `/v1/me` and `/v1/server-state`
- a protocol boundary that rejects `game.*` messages until the engine adapter is attached

Not implemented in this stage:

- poker-engine attachment
- Android client wiring
- PostgreSQL / Redis
- tournament persistence migration
- public TLS/domain deployment

Keeping these out of Stage 1 prevents the existing local UI server and tournament
state files from becoming an accidental internet-facing source of truth.

## Local transport test (no Firebase account required)

Use this only on your own machine.

```sh
python3 -m venv .venv
. .venv/bin/activate
pip install -r online_server/requirements.txt

export T2_AUTH_MODE=dev
export T2_ALLOW_DEV_AUTH=1
export T2_DEV_TOKEN="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
export T2_SINGLE_USER_UID=local-dev-user

uvicorn online_server.app:app --host 127.0.0.1 --port 8000
```

Health check:

```sh
curl http://127.0.0.1:8000/health
```

Authenticated HTTP check:

```sh
curl -H "Authorization: Bearer $T2_DEV_TOKEN" \
  http://127.0.0.1:8000/v1/me
```

Run the dependency-light verifier:

```sh
python3 tools/verify_online_server.py
```

Development auth is fail-closed: it will not start unless
`T2_ALLOW_DEV_AUTH=1` is explicitly set and the token is at least 24 characters.

## WebSocket protocol v1

Connect to:

```text
ws://127.0.0.1:8000/v1/ws
```

The first client frame must be:

```json
{"type":"auth","id_token":"<Firebase ID token or local dev token>"}
```

Authentication is deliberately sent as the first WebSocket frame rather than as
a query-string token, so credentials do not normally appear in access-log URLs.

Success:

```json
{
  "type": "auth.ok",
  "protocol": 1,
  "connection_id": "...",
  "user": {"uid": "..."},
  "capabilities": ["ping", "server.state"],
  "game_backend": "detached"
}
```

Currently supported messages after authentication:

```json
{"type":"ping","client_id":"optional-value"}
{"type":"server.state"}
```

Any `game.*` request returns `game_backend_not_attached`. That is intentional
until a server-authoritative adapter around the existing T2 engine is added.

## Real Google/Firebase login

The Android app signs into Firebase with Google, gets the signed-in user's
**Firebase ID token**, and sends that ID token to this server. The client must
never send a raw `uid` and expect the server to trust it.

Server configuration:

```sh
export T2_AUTH_MODE=firebase
export T2_FIREBASE_PROJECT_ID=your-project-id

# On a normal VPS:
export GOOGLE_APPLICATION_CREDENTIALS=/secure/outside/git/service-account.json

uvicorn online_server.app:app --host 127.0.0.1 --port 8000
```

For a Google-managed runtime, prefer Application Default Credentials / an
attached service account rather than storing a service-account JSON in the
repository or image.

For the initial one-user server, first log in once, read the verified UID from
`GET /v1/me`, then restart with:

```sh
export T2_SINGLE_USER_UID=the-verified-firebase-uid
```

After that, valid Firebase tokens belonging to other Google accounts are
rejected by this server.

## What the owner must configure before real login works

1. Create/select a Firebase project.
2. Register the future Android app in that project.
3. Add the Android app's SHA-1 fingerprint.
4. Enable Google under Firebase Authentication > Sign-in method.
5. Put the resulting `google-services.json` in the Android project (not in this
   server directory).
6. Give the server Firebase Admin credentials. On a VPS, keep the service-account
   JSON outside the git checkout and point `GOOGLE_APPLICATION_CREDENTIALS` at it.
7. Put HTTPS in front of this server before sending real Firebase ID tokens over
   the public internet.

## Container

Build from the repository root:

```sh
docker build -f online_server/Dockerfile -t t2-online:test2 .
```

The image contains only the gateway at this stage. The poker engine is not copied
into the image until the engine adapter stage.
