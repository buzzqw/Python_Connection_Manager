"""
totp_manager.py - TOTP (Time-based One-Time Password) generator for PCM.

Pure Python implementation using only stdlib (hashlib, hmac, time, base64).
Compatible with Google Authenticator, Authy, and other RFC 6238 TOTP apps.
"""

import base64
import hashlib
import hmac
import time
from typing import Optional


def generate_totp(secret: str, digits: int = 6, period: int = 30,
                  algorithm: str = "sha1") -> Optional[str]:
    """Generate a TOTP code from a base32-encoded secret.

    Args:
        secret: Base32-encoded secret key
        digits: Number of digits in the OTP (default 6)
        period: Time step in seconds (default 30)
        algorithm: Hash algorithm: sha1, sha256, or sha512

    Returns:
        TOTP code string, or None if secret is invalid
    """
    if not secret:
        return None

    try:
        key = _decode_base32(secret.strip().upper().replace(" ", ""))
    except Exception:
        print("[totp] Invalid base32 secret")
        return None

    current_step = int(time.time() // period)
    time_bytes = current_step.to_bytes(8, byteorder="big")

    hash_alg = {
        "sha1": hashlib.sha1,
        "sha256": hashlib.sha256,
        "sha512": hashlib.sha512,
    }.get(algorithm, hashlib.sha1)

    hmac_digest = hmac.new(key, time_bytes, hash_alg).digest()
    offset = hmac_digest[-1] & 0x0F
    truncated = hmac_digest[offset : offset + 4]
    code = int.from_bytes(truncated, byteorder="big") & 0x7FFFFFFF
    code = code % (10 ** digits)

    return str(code).zfill(digits)


def generate_totp_with_countdown(secret: str, digits: int = 6,
                                  period: int = 30) -> tuple[Optional[str], int]:
    """Generate a TOTP code with remaining seconds until next code.

    Returns:
        (code, remaining_seconds) tuple
    """
    remaining = period - (int(time.time()) % period)
    return generate_totp(secret, digits, period), remaining


def validate_secret(secret: str) -> bool:
    """Check if a string looks like a valid base32 TOTP secret."""
    if not secret:
        return False
    try:
        cleaned = secret.strip().upper().replace(" ", "")
        if not cleaned:
            return False
        _decode_base32(cleaned)
        return len(cleaned) >= 16
    except Exception:
        return False


def _decode_base32(text: str) -> bytes:
    """Decode base32 string with padding fix."""
    # Add padding if needed
    padding = 8 - (len(text) % 8)
    if padding != 8:
        text += "=" * padding
    return base64.b32decode(text)


def extract_otp_from_uri(uri: str) -> Optional[str]:
    """Extract TOTP secret from an otpauth:// URI.

    Example: otpauth://totp/Example:user@host?secret=JBSWY3DPEHPK3PXP&issuer=Example
    """
    if not uri.startswith("otpauth://"):
        return None
    try:
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(uri)
        params = parse_qs(parsed.query)
        secrets = params.get("secret", [])
        if secrets:
            return secrets[0]
    except Exception:
        pass
    return None


def render_uri_to_secret(text: str) -> str:
    """Convert otpauth:// URI to secret, or return text as-is if not a URI."""
    extracted = extract_otp_from_uri(text.strip())
    return extracted if extracted else text.strip()
