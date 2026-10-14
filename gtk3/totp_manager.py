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
        cleaned = secret.strip().upper().replace(" ", "")
        if not cleaned:
            return None
        key = _decode_base32(cleaned)
    except Exception:
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


def parse_otpauth(uri: str) -> Optional[dict]:
    """Parse an otpauth:// URI into secret + optional generator parameters.

    Ritorna {"secret": str} più, se presenti e validi, "digits", "period" e
    "algorithm" (parametri standard usati da Google Authenticator, Authy & co.).
    Ritorna None se la URI non è valida o manca il secret.
    """
    if not uri or not uri.strip().startswith("otpauth://"):
        return None
    from urllib.parse import urlparse, parse_qs, unquote
    try:
        parsed = urlparse(uri.strip())
        params = parse_qs(parsed.query)
    except ValueError:
        return None

    secrets = params.get("secret") or []
    if not secrets or not secrets[0]:
        return None
    result: dict = {"secret": unquote(secrets[0]).strip()}

    digits = (params.get("digits") or [""])[0]
    try:
        d = int(digits)
        if 6 <= d <= 10:
            result["digits"] = d
    except (TypeError, ValueError):
        pass

    period = (params.get("period") or [""])[0]
    try:
        p = int(period)
        if p > 0:
            result["period"] = p
    except (TypeError, ValueError):
        pass

    algorithm = (params.get("algorithm") or [""])[0].lower()
    if algorithm in ("sha1", "sha256", "sha512"):
        result["algorithm"] = algorithm

    return result


def extract_otp_from_uri(uri: str) -> Optional[str]:
    """Extract TOTP secret from an otpauth:// URI.

    Example: otpauth://totp/Example:user@host?secret=JBSWY3DPEHPK3PXP&issuer=Example
    """
    parsed = parse_otpauth(uri)
    return parsed["secret"] if parsed else None


def render_uri_to_secret(text: str) -> str:
    """Convert otpauth:// URI to secret, or return text as-is if not a URI."""
    extracted = extract_otp_from_uri(text.strip())
    return extracted if extracted else text.strip()
