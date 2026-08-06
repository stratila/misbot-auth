from pwdlib import PasswordHash

from misbot_auth_server.db.clients import get_client

password_hash = PasswordHash.recommended()

DUMMY_HASH = password_hash.hash("dummypassword")


def verify_password(plain_password, hashed_password):
    return password_hash.verify(plain_password, hashed_password)


def get_password_hash(password):
    return password_hash.hash(password)


def authenticate_client(client_id: str, client_secret: str):
    client = get_client(client_id=client_id)
    if not client:
        # throwaway against a timing / user-enumeration attack
        verify_password(plain_password=client_secret, hashed_password=DUMMY_HASH)
        return False
    if not verify_password(plain_password=client_secret, hashed_password=client.hashed_secret):
        return False
    return client
