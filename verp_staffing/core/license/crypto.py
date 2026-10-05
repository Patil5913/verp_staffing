"""Ed25519 signing / verification of entitlement payloads.

Central (verp-subscription, lib/licensing/crypto-signer.ts) signs the canonical JSON of a
payload with ONE Ed25519 private key shared across all customer sites; this site only ever
holds central's PUBLIC key (fetched from GET /api/client/public-key) and verifies. Node's
`sign(null, data, key)` / `verify(null, data, key, sig)` use the raw message directly — Ed25519
hashes internally (SHA-512) — so there is no digest algorithm or padding to agree on, only that
both sides sign/verify the exact same bytes.
"""

import json
from functools import lru_cache

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey


def canonical_json(data) -> str:
	"""Matches central's canonicalize(): JSON.stringify(sortedKeys(obj)) — sorted keys, no
	extra whitespace, non-ASCII left unescaped."""
	return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def generate_keypair() -> tuple[str, str]:
	"""(private_pem, public_pem). Only the mock central uses the private half — the real
	dashboard's keypair is generated once, offline, via its own generate-keys script."""
	key = Ed25519PrivateKey.generate()
	private_pem = key.private_bytes(
		serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
	).decode()
	public_pem = key.public_key().public_bytes(
		serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
	).decode()
	return private_pem, public_pem


def sign(payload_json: str, private_pem: str) -> str:
	import base64

	key = serialization.load_pem_private_key(private_pem.encode(), password=None)
	return base64.b64encode(key.sign(payload_json.encode())).decode()


def load_public_key(key_text: str) -> Ed25519PublicKey:
	"""Accepts a PEM block OR the bare base64 SPKI body. The dashboard's /api/client/public-key
	currently returns the bare body (no BEGIN/END lines) even though the field is called
	public_key, so PEM-only parsing rejected every signature as invalid."""
	import base64

	text = key_text.strip()
	if text.startswith("-----BEGIN"):
		return serialization.load_pem_public_key(text.encode())
	return serialization.load_der_public_key(base64.b64decode(text))


@lru_cache(maxsize=32)
def verify(payload_json: str, signature_b64: str, public_pem: str) -> bool:
	"""Cached: the request guard calls this on every request, the answer for the same
	(payload, signature, key) never changes."""
	import base64

	try:
		key: Ed25519PublicKey = load_public_key(public_pem)
		key.verify(base64.b64decode(signature_b64), payload_json.encode())
		return True
	except (InvalidSignature, ValueError, TypeError):
		return False
