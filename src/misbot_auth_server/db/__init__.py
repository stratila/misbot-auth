fake_clients_db = {
    "johndoe": {
        "client_id": "johndoe",
        "client_type": "confidential",
        # fakehashedsecret
        "hashed_secret": (
            "$argon2id$v=19$m=65536,t=3,p=4$zFZ9sMeLRB7YDckdmJaxZQ$Z5/NkSXVosl0oiqXDfZ"
            "T4YbdPf9XhyP+gv+dE3B5P0k"
        ),
        "allowed_scopes": ["read"],
        "allowed_grants": ["client_credentials"],
        "enabled": True,
    },
    "alice": {
        "client_id": "alice",
        "client_type": "confidential",
        # fakehashedsecret2
        "hashed_secret": (
            "$argon2id$v=19$m=65536,t=3,p=4$gGDSGtI7sdyCw20FTzgDDg$6bNRLzFcyZdKVCARCVPk"
            "uxn1qvYCf+xVoItdBKG+lkA"
        ),
        "allowed_scopes": ["read", "write"],
        "allowed_grants": ["client_credentials"],
        "enabled": False,
    },
}
