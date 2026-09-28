"""RSA-PSS signing / verification of entitlement payloads.

Central signs the canonical JSON of a payload with its private key; this site
only ever holds central's PUBLIC key and verifies. The same canonical form is
used on both sides, so signing and verifying always agree byte-for-byte.
"""

import base64
import json
from functools import lru_cache

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

_PSS = padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH)


def canonical_json(data) -> str:
	return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def generate_keypair() -> tuple[str, str]:
	"""(private_pem, public_pem). Only the mock central uses the private half."""
	key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
	private_pem = key.private_bytes(
		serialization.Encoding.PEM,
		serialization.PrivateFormat.PKCS8,
		serialization.NoEncryption(),
	).decode()
	public_pem = key.public_key().public_bytes(
		serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
	).decode()
	return private_pem, public_pem


def sign(payload_json: str, private_pem: str) -> str:
	key = serialization.load_pem_private_key(private_pem.encode(), password=None)
	return base64.b64encode(key.sign(payload_json.encode(), _PSS, hashes.SHA256())).decode()


@lru_cache(maxsize=32)
def verify(payload_json: str, signature_b64: str, public_pem: str) -> bool:
	"""Cached: the request guard calls this on every request, the answer for the same
	(payload, signature, key) never changes."""
	try:
		key = serialization.load_pem_public_key(public_pem.encode())
		key.verify(base64.b64decode(signature_b64), payload_json.encode(), _PSS, hashes.SHA256())
		return True
	except (InvalidSignature, ValueError, TypeError):
		return False
