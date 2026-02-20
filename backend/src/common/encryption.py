"""AES-256-GCM encryption for vault credentials."""
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes


def derive_key(master_password: str, salt: bytes) -> bytes:
    """Derive a 256-bit key from master password using PBKDF2."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100_000,
    )
    return kdf.derive(master_password.encode())


def encrypt_field(plaintext: str, key: bytes) -> bytes:
    """Encrypt a string field with AES-256-GCM. Returns nonce + ciphertext blob."""
    if not plaintext:
        return b""
    nonce = os.urandom(12)  # 96-bit nonce for GCM
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode(), None)
    return nonce + ciphertext  # Prepend nonce to ciphertext


def decrypt_field(blob: bytes, key: bytes) -> str:
    """Decrypt a nonce + ciphertext blob back to string."""
    if not blob:
        return ""
    nonce = blob[:12]
    ciphertext = blob[12:]
    aesgcm = AESGCM(key)
    plaintext = aesgcm.decrypt(nonce, ciphertext, None)
    return plaintext.decode()
