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
`/app/db/authdb.sqlite`, so mounting a volume at `/app/db` is what makes clients
survive a restart. Without that volume the database is lost with the container.

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

### Local development in containers

```bash
podman compose -f container-compose.yml up --build
podman compose -f container-compose.yml run --rm sqlite   # sqlite3 shell on the live DB
```

The dev target bind-mounts the repository for `--reload` and sets
`EXECUTE_MIGRATIONS=true`, so the schema is created on first start.

### Tests in a container

```bash
podman build -t misbot-auth:test --target test .
podman run --rm misbot-auth:test
```

No secret or database needs mounting.
