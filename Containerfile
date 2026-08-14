FROM python:3.12-slim AS base
COPY --from=ghcr.io/astral-sh/uv:0.11.28 /uv /uvx /bin/

ENV UV_LINK_MODE=copy
ENV VIRTUAL_ENV=/opt/venv
ENV PATH="/opt/venv/bin:$PATH"
WORKDIR /app

# ---------------------------------
# Production stage
# ---------------------------------
FROM base AS deps_prod
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --active --no-install-project --no-editable --no-dev

FROM deps_prod AS builder_prod
COPY . /app
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --active --no-editable


FROM python:3.12-slim AS prod
# The uid is pinned, not left to useradd's "next free id". Deployments map the
# host user onto this uid (UserNS=keep-id:uid=1000,gid=1000), so if it ever
# drifted, the bind-mounted database would silently become unwritable. Being
# explicit also makes the build fail loudly if the base image ever claims 1000,
# instead of quietly handing out 1001.
RUN groupadd --gid 1000 app \
    && useradd --create-home --uid 1000 --gid 1000 app

# Set here rather than inherited from `base`: this stage starts from a clean
# image, and without it the working directory would be `/`, which would leave
# every relative path in the settings resolving somewhere unintended.
WORKDIR /app
ENV VIRTUAL_ENV=/opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# The application source is not copied: `--no-editable` installed it into the
# virtualenv. Alembic is a data directory, so it has to come across explicitly.
COPY --from=builder_prod --chown=app:app /opt/venv/ /opt/venv/
COPY --from=builder_prod --chown=app:app /app/alembic /app/alembic
COPY --from=builder_prod --chown=app:app /app/alembic.ini /app/alembic.ini
COPY --chown=app:app entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# SQLite will not create this itself, and a volume mounted over it inherits the
# ownership, so creating it here is what lets the unprivileged user write.
RUN install -d -o app -g app /app/db

# The signing key is mounted at runtime and never baked into a layer.
ENV MISBOT_AUTH_SECRETS_DIR=/run/secrets
ENV MISBOT_AUTH_DATABASE__DB_FILE=/app/db/authdb.sqlite

EXPOSE 8080
USER app
ENTRYPOINT ["/app/entrypoint.sh"]
# One process on purpose: several uvicorn workers would contend for the same
# SQLite file. Scale by putting a reverse proxy in front, not by adding workers.
CMD ["/opt/venv/bin/uvicorn", "misbot_auth_server.server:app", "--host", "0.0.0.0", "--port", "8080"]

# ---------------------------------
# Test stage
# ---------------------------------
FROM builder_prod AS test_builder_prod
COPY . /app
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --active --only-group test --inexact


FROM prod AS test
USER root
COPY --from=test_builder_prod --chown=app:app /opt/venv/ /opt/venv/
COPY --chown=app:app tests /app/tests
# `conftest.py` seeds a throwaway signing key before the settings are imported,
# so the suite runs with no secret mounted; `pyproject.toml` carries the pytest
# configuration the suite depends on.
COPY --chown=app:app conftest.py /app/conftest.py
COPY --chown=app:app pyproject.toml /app/pyproject.toml
WORKDIR /app
USER app
ENTRYPOINT []
# `/app` belongs to root and the suite runs unprivileged, so the cache would
# only produce a warning about a directory it cannot create.
CMD ["/opt/venv/bin/pytest", "-p", "no:cacheprovider"]


# ---------------------------------
# Development stage
# ---------------------------------
FROM base AS deps_dev
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --active --no-install-project


FROM deps_dev AS dev
WORKDIR /app
# Install project as editable (points to /app)
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=.,target=. \
    uv sync --locked --active

# Copied rather than relied upon from the bind mount, so this stage is runnable
# on its own and not only under compose.
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh
RUN install -d /app/db

ENV EXECUTE_MIGRATIONS=true
ENV MISBOT_AUTH_SECRETS_DIR=/run/secrets
ENV MISBOT_AUTH_DATABASE__DB_FILE=/app/db/authdb.sqlite

EXPOSE 8080
ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["/opt/venv/bin/uvicorn", "misbot_auth_server.server:app", "--host", "0.0.0.0", "--port", "8080", "--reload"]
