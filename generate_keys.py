#!/usr/bin/env python3
"""
Generate VAPID keys for Web Push notifications.
Run: python generate_keys.py
Then copy the output into your .env file.
"""
import base64
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.backends import default_backend


def generate_vapid_keys():
    private_key = ec.generate_private_key(ec.SECP256R1(), default_backend())
    public_key = private_key.public_key()

    # Private key: raw 32 bytes → base64url
    private_value = private_key.private_numbers().private_value
    private_bytes = private_value.to_bytes(32, "big")
    private_b64 = base64.urlsafe_b64encode(private_bytes).rstrip(b"=").decode()

    # Public key: uncompressed EC point (0x04 || x || y) → base64url
    pub_numbers = public_key.public_numbers()
    x = pub_numbers.x.to_bytes(32, "big")
    y = pub_numbers.y.to_bytes(32, "big")
    pub_bytes = b"\x04" + x + y
    pub_b64 = base64.urlsafe_b64encode(pub_bytes).rstrip(b"=").decode()

    return private_b64, pub_b64


if __name__ == "__main__":
    priv, pub = generate_vapid_keys()
    print("Add these to your .env file:")
    print(f"VAPID_PRIVATE_KEY={priv}")
    print(f"VAPID_PUBLIC_KEY={pub}")
