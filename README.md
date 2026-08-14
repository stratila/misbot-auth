# misbot-auth-server

An OAuth 2.0 authorization server for the client-credentials grant (RFC 6749 §4.4),
issuing RS256-signed JWTs that resource servers verify against a published JWK Set.

| Endpoint | Purpose |
|---|---|
| `POST /token` | Issue an access token (RFC 6749 §4.4) |
| `GET /.well-known/jwks.json` | Public signing keys (RFC 7517) |
| `GET /.well-known/oauth-authorization-server` | Server metadata (RFC 8414) |

Clients authenticate with either HTTP Basic or form credentials (§2.3.1), never both
in one request.

## Configuration

All settings are read from the environment, from `.env.dev` / `.env`, or from files
in the secrets directory. Both dotfiles are gitignored, so a fresh clone configures
everything through the environment.

| Variable | Default | Purpose |
|---|---|---|
| `MISBOT_AUTH_JWT__ISSUER` | — | This server's URL; becomes the `iss` claim |
| `MISBOT_AUTH_JWT__AUDIENCE` | — | The resource server's URL; becomes `aud` |
| `MISBOT_AUTH_JWT__ALGORITHM` | `RS256` | Signing algorithm |
| `MISBOT_AUTH_JWT__ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | Token lifetime |
| `MISBOT_AUTH_DATABASE__DB_FILE` | `db/authdb.sqlite` | SQLite file; **make this absolute in a container** |
| `MISBOT_AUTH_DATABASE__SQL_ECHO` | `false` | Log every SQL statement |
| `MISBOT_AUTH_SECRETS_DIR` | `secrets` | Directory of file-backed secrets |
| `EXECUTE_MIGRATIONS` | `false` | Container only: run `alembic upgrade head` at startup |

### The signing key

The RSA private key is read from a **file**, not an environment variable:
`$MISBOT_AUTH_SECRETS_DIR/misbot_auth_jwt-private_key`. The filename maps to the
`jwt.private_key` setting via the `-` nesting delimiter. Generate one with:

```bash
mkdir -p secrets
openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 \
    -out secrets/misbot_auth_jwt-private_key
chmod 600 secrets/misbot_auth_jwt-private_key
```

`secrets/` is gitignored and is never copied into a container image.

## Local development

```bash
uv sync
uv run alembic -c alembic.ini upgrade head          # create the schema
uv run misbot-auth-server register-client --client-id svc --scopes read,write
uv run fastapi dev src/misbot_auth_server/server.py
```

Run everything from the repository root: `MISBOT_AUTH_SECRETS_DIR` and
`MISBOT_AUTH_DATABASE__DB_FILE` default to relative paths.

```bash
uv run pytest
uv run ruff check . && uv run ruff format --check .
```

The suite needs no key and no database of its own — `conftest.py` generates a
throwaway signing key when none is configured, so it runs on a bare clone.

## Managing clients

There is no registration endpoint; clients are provisioned out of band. The secret
is shown once and only its argon2 hash is stored, so there is no way to recover it.

```bash
misbot-auth-server register-client --client-id svc --scopes read,write
misbot-auth-server list-clients
misbot-auth-server disable-client --client-id svc   # refuse it new tokens
misbot-auth-server enable-client  --client-id svc
```

Disabling takes effect on the next token request. Already-issued tokens stay valid
until they expire — this server has no revocation endpoint.

## Containers

Four build targets: `prod`, `test`, `dev`, and the shared `base`.

```bash
podman build -t misbot-auth:prod --target prod .
```

The image contains no key material and no database. Both arrive at runtime:

```bash
podman volume create misbot-auth-db

# Create the schema (once per upgrade).
podman run --rm \
    -v misbot-auth-db:/app/db \
    -v ./secrets:/run/secrets:ro,Z \
    -e EXECUTE_MIGRATIONS=true \
    -e MISBOT_AUTH_JWT__ISSUER=https://auth.example.com \
    -e MISBOT_AUTH_JWT__AUDIENCE=https://api.example.com \
    misbot-auth:prod /opt/venv/bin/alembic -c /app/alembic.ini current

# Serve.
podman run -d --name misbot-auth-app -p 8080:8080 \
    -v misbot-auth-db:/app/db \
    -v ./secrets:/run/secrets:ro,Z \
    -e MISBOT_AUTH_JWT__ISSUER=https://auth.example.com \
    -e MISBOT_AUTH_JWT__AUDIENCE=https://api.example.com \
    misbot-auth:prod
```

Inside the image, `MISBOT_AUTH_SECRETS_DIR` is `/run/secrets` and the database is
`/app/db/authdb.sqlite`, so mounting something at `/app/db` is what makes clients
survive a restart. Without it the database is lost with the container.

A named volume is used here, and by `container-compose.yml`, because podman
chowns one to the container user automatically. The quadlet deployment uses a
**bind mount** instead, so the SQLite file is an ordinary host file — see
[Deploying with quadlets](#deploying-with-quadlets) for why that needs
`UserNS=keep-id`.

`EXECUTE_MIGRATIONS` defaults to `false`, so a restart never changes the schema on
its own — run migrations deliberately, as above. When it is `true` and a migration
fails, the entrypoint exits non-zero and the container refuses to start rather than
serving a half-migrated schema.

Registering a client against a running server:

```bash
podman exec misbot-auth-app \
    /opt/venv/bin/misbot-auth-server register-client --client-id svc --scopes read
```

The server runs a single uvicorn process by design: several workers would contend
for one SQLite file. Scale with a reverse proxy in front, not with `--workers`.

### Deploying with quadlets

`quadlets/` holds two rootless podman systemd units: `misbot-auth-app.container`
for the server and `misbot-auth-migrate.container` for the schema. `{IMAGE}` and
`{PORT}` are placeholders for a deploy step to substitute — both units must get
the *same* image, or the migration would apply a different schema than the one
the server expects.

Host layout they expect:

```
~/.config/misbot-auth/.env                                  # 0600, issuer + audience
~/.config/misbot-auth/secrets/misbot_auth_jwt-private_key   # 0600
~/.local/share/misbot-auth/db/                              # must exist beforehand
```

The database directory is a bind mount, and unlike a named volume **podman will
not create it** — the unit fails with `statfs ...: no such file` if it is
missing.

```bash
install -d -m 700 ~/.config/misbot-auth/secrets
install -d ~/.local/share/misbot-auth/db ~/.config/containers/systemd
openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 \
    -out ~/.config/misbot-auth/secrets/misbot_auth_jwt-private_key
chmod 600 ~/.config/misbot-auth/secrets/misbot_auth_jwt-private_key

cat > ~/.config/misbot-auth/.env <<'EOF'
MISBOT_AUTH_JWT__ISSUER=https://auth.example.com
MISBOT_AUTH_JWT__AUDIENCE=https://api.example.com
EOF
chmod 600 ~/.config/misbot-auth/.env

for unit in quadlets/*.container; do
    sed -e "s|{IMAGE}|ghcr.io/you/misbot-auth:sha-abc123|g" -e "s|{PORT}|8080|g" \
        "$unit" > ~/.config/containers/systemd/"$(basename "$unit")"
done

systemctl --user daemon-reload
systemctl --user restart misbot-auth-migrate.service
systemctl --user start misbot-auth-app.service
```

The database is a **bind mount**, not a named volume, so the SQLite file is an
ordinary host file you can back up or open with `sqlite3` directly. That only
works because the unit sets `UserNS=keep-id`, which maps the container's `app`
user onto the host user. Without it, rootless podman maps `app` into the subuid
range and either the container cannot write the directory or `:U` chowns it away
from you.

Migrations belong to `misbot-auth-migrate.service`, a one-shot unit that runs
`alembic upgrade head` and exits. The application unit `Requires=` it, so a
failed migration keeps the server from starting at all rather than letting it
serve a database it has no schema for. `EXECUTE_MIGRATIONS=false` on the
application, so restarting it never touches the schema.

```bash
systemctl --user restart misbot-auth-migrate.service   # blocks; non-zero on failure
systemctl --user start misbot-auth-app.service
```

Use `restart`, not `start`, for the migration unit. It is `RemainAfterExit=yes`,
so it stays active after a successful run and `start` on an active unit does
nothing — every deploy after the first would silently skip its migrations.

Registering a client against the running service:

```bash
podman exec misbot-auth-app \
    /opt/venv/bin/misbot-auth-server register-client --client-id svc --scopes read
```

Quadlet units cannot be `systemctl enable`d — they are generated into
`/run/user/$UID/systemd/generator/` on every `daemon-reload`, and systemd rejects
enabling a generated unit. The `[Install] WantedBy=default.target` inside the
`.container` file is what starts it at boot instead. The one thing you do need is
`loginctl enable-linger $USER`, so the user manager runs without an active login.

### Local development in containers

```bash
podman compose -f container-compose.yml up --build
podman compose -f container-compose.yml run --rm sqlite   # sqlite3 shell on the live DB
```

The dev target bind-mounts the repository for `--reload` and sets
`EXECUTE_MIGRATIONS=true`, so the schema is created on first start.

Both services use `network_mode: pasta` rather than a compose bridge network.
They share a volume, not a socket, so neither needs to reach the other by name,
and pasta forwards published ports without the netfilter rules a bridge needs --
which is what makes this work on kernels without full nftables NAT support, WSL2
among them. Swap it for a bridge network if you ever add a service that has to
resolve another by hostname.

### Tests in a container

```bash
podman build -t misbot-auth:test --target test .
podman run --rm misbot-auth:test
```

No secret or database needs mounting.

## Continuous deployment

`.github/workflows/ci-deploy.yml` runs on a push to `dev` or `main`: tests, then
a build pushed to GHCR, then a deploy to the matching environment.

Set the following on the GitHub **Environment** (`dev` and `prod` separately),
not on the repository — the deploy job declares
`environment: ${{ inputs.environment }}`.

| Name | Kind | Example | Purpose |
|---|---|---|---|
| `SSH_PRIVATE_KEY` | secret | `-----BEGIN OPENSSH PRIVATE KEY-----…` | Key for the deploy user |
| `SSH_HOST` | secret | `auth.example.com` | Target host; also fed to `ssh-keyscan` |
| `SSH_USER` | secret | `authbot` | Login user on the target host |
| `JWT_PRIVATE_KEY` | secret | a full PEM, multi-line | Written to the host as `misbot_auth_jwt-private_key`, mode 600 |
| `JWT_ISSUER` | secret | `https://auth.example.com` | The `iss` claim and the metadata `issuer` |
| `JWT_AUDIENCE` | secret | `https://api.example.com` | The `aud` claim |
| `PORT` | variable | `8080` | Host port in `PublishPort=127.0.0.1:{PORT}:8080` |

`GITHUB_TOKEN` needs no setup; GitHub provides it, and the build job already
requests `packages: write` for GHCR.

`JWT_ISSUER` and `JWT_AUDIENCE` are not really secret — the issuer is published
in every token and at `/.well-known/oauth-authorization-server`. They are secrets
here only to match the sibling misbot project; variables would be a better fit
and would stay readable in logs when debugging a mismatch.

One host-side prerequisite the pipeline assumes rather than creates — without it
the user manager stops when the deploy's SSH session ends, taking the service
with it:

```bash
loginctl enable-linger $SSH_USER
```

Starting at boot needs nothing further: the unit's `[Install]` section already
puts it in `default.target`, and a generated unit cannot be enabled anyway.

### What a failed migration does

Migrations run as a one-shot unit before the server starts, and the failure is
propagated rather than swallowed at every layer: `alembic/env.py` re-raises,
`entrypoint.sh` runs under `set -e`, the container exits non-zero, and
`systemctl restart` on a one-shot unit blocks and returns that status. The deploy
then fails at three points — the migration step, the application start
(`Requires=` refuses it), and the final check, which dumps `systemctl status` and
the container log.

Two things to expect when that happens:

- **It is downtime, not a rollback.** The deploy stops the service before
  migrating, so a failed migration leaves nothing running. Move the stop after
  the migration if you would rather the old container kept serving.
- **SQLite DDL is not fully transactional** — alembic reports
  `Will assume non-transactional DDL` — so a migration with several statements
  can be left partially applied even though the unit correctly reports `failed`.
