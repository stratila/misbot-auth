"""Administrative commands for managing registered OAuth clients.

Runs outside the web server, so it drives asyncio itself.
"""

import argparse
import asyncio
import secrets
import sys

from sqlalchemy.exc import IntegrityError

from misbot_auth_server.auth.passwords import get_password_hash
from misbot_auth_server.db.clients import create_client, list_clients, set_client_enabled
from misbot_auth_server.db.engine import engine
from misbot_auth_server.models.clients import Client

# 32 bytes of entropy, which token_urlsafe renders as 43 characters.
SECRET_BYTES = 32


def _comma_separated(value: str) -> list[str]:
    items = [item.strip() for item in value.split(",")]
    return [item for item in items if item]


async def _register(args: argparse.Namespace) -> int:
    client_secret = secrets.token_urlsafe(SECRET_BYTES)
    client = Client(
        client_id=args.client_id,
        client_type="confidential",
        hashed_secret=get_password_hash(client_secret),
        allowed_scopes=args.scopes,
        allowed_grants=args.grants,
    )

    try:
        await create_client(engine, client)
    except IntegrityError:
        print(f"error: client {args.client_id!r} is already registered", file=sys.stderr)
        return 1

    print(f"client_id:     {client.client_id}")
    print(f"client_secret: {client_secret}")
    print(f"scopes:        {' '.join(client.allowed_scopes)}")
    print()
    print("Only the hash is stored. Record the secret now; it cannot be recovered.")
    return 0


async def _list(args: argparse.Namespace) -> int:
    registered = await list_clients(engine)
    if not registered:
        print("no clients registered")
        return 0

    width = max(len(client.client_id) for client in registered)
    for client in registered:
        state = "enabled" if client.enabled else "disabled"
        print(f"{client.client_id:<{width}}  {state:<8}  {' '.join(client.allowed_scopes)}")
    return 0


async def _set_enabled(args: argparse.Namespace) -> int:
    found = await set_client_enabled(engine, args.client_id, args.enabled)
    if not found:
        print(f"error: no client {args.client_id!r}", file=sys.stderr)
        return 1

    print(f"{args.client_id} {'enabled' if args.enabled else 'disabled'}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="misbot-auth-server", description=__doc__)
    subcommands = parser.add_subparsers(dest="command", required=True)

    register = subcommands.add_parser(
        "register-client", help="register a client and print its generated secret"
    )
    register.add_argument("--client-id", required=True)
    register.add_argument(
        "--scopes",
        type=_comma_separated,
        default=["read"],
        help="comma-separated scopes the client may request (default: read)",
    )
    register.add_argument(
        "--grants",
        type=_comma_separated,
        default=["client_credentials"],
        help="comma-separated grant types (default: client_credentials)",
    )
    register.set_defaults(handler=_register)

    listing = subcommands.add_parser("list-clients", help="list registered clients")
    listing.set_defaults(handler=_list)

    disable = subcommands.add_parser("disable-client", help="refuse tokens to a client")
    disable.add_argument("--client-id", required=True)
    disable.set_defaults(handler=_set_enabled, enabled=False)

    enable = subcommands.add_parser("enable-client", help="undo disable-client")
    enable.add_argument("--client-id", required=True)
    enable.set_defaults(handler=_set_enabled, enabled=True)

    return parser


async def _run(args: argparse.Namespace) -> int:
    try:
        return await args.handler(args)
    finally:
        await engine.dispose()


def main() -> int:
    args = build_parser().parse_args()
    return asyncio.run(_run(args))


if __name__ == "__main__":
    sys.exit(main())
