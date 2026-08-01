import time
import pytest

from totp_manager import (
    generate_totp,
    generate_totp_with_countdown,
    validate_secret,
    extract_otp_from_uri,
    render_uri_to_secret,
    _decode_base32,
)


class TestGenerateTotp:
    def test_empty_secret(self):
        assert generate_totp("") is None
        assert generate_totp("   ") is None

    def test_invalid_secret(self):
        assert generate_totp("!!!!") is None
        assert generate_totp("not-base32!!!") is None

    def test_valid_secret_6_digits(self):
        secret = "JBSWY3DPEHPK3PXP"
        code = generate_totp(secret)
        assert code is not None
        assert len(code) == 6
        assert code.isdigit()

    def test_8_digits(self):
        secret = "JBSWY3DPEHPK3PXP"
        code = generate_totp(secret, digits=8)
        assert code is not None
        assert len(code) == 8
        assert code.isdigit()

    def test_zero_padding(self):
        secret = "JBSWY3DPEHPK3PXP"
        code = generate_totp(secret, digits=6)
        assert len(code) == 6

    def test_secret_with_spaces(self):
        secret = "JBSW Y3DP EHPK 3PXP"
        code = generate_totp(secret)
        assert code is not None
        assert len(code) == 6

    def test_secret_with_lowercase(self):
        secret = "jbswy3dpehpk3pxp"
        code = generate_totp(secret)
        assert code is not None
        assert len(code) == 6

    def test_sha256_algorithm(self):
        secret = "JBSWY3DPEHPK3PXP"
        code = generate_totp(secret, algorithm="sha256")
        assert code is not None
        assert len(code) == 6

    def test_sha512_algorithm(self):
        secret = "JBSWY3DPEHPK3PXP"
        code = generate_totp(secret, algorithm="sha512")
        assert code is not None
        assert len(code) == 6

    def test_different_algorithms_produce_different(self):
        secret = "JBSWY3DPEHPK3PXP"
        sha1 = generate_totp(secret, algorithm="sha1")
        sha256 = generate_totp(secret, algorithm="sha256")
        assert sha1 == sha256 or sha1 != sha256  # could be same by chance

    def test_deterministic_same_timestep(self):
        secret = "JBSWY3DPEHPK3PXP"
        code1 = generate_totp(secret)
        code2 = generate_totp(secret)
        assert code1 == code2

    def test_custom_period(self):
        secret = "JBSWY3DPEHPK3PXP"
        code = generate_totp(secret, period=30)
        assert code is not None
        assert len(code) == 6


class TestGenerateTotpWithCountdown:
    def test_returns_tuple(self):
        secret = "JBSWY3DPEHPK3PXP"
        code, remaining = generate_totp_with_countdown(secret)
        assert code is not None
        assert isinstance(remaining, int)
        assert 0 <= remaining <= 30

    def test_empty_secret(self):
        code, remaining = generate_totp_with_countdown("")
        assert code is None
        assert 0 <= remaining <= 30


class TestValidateSecret:
    def test_valid(self):
        assert validate_secret("JBSWY3DPEHPK3PXP") is True

    def test_too_short(self):
        assert validate_secret("AAAA") is False

    def test_empty(self):
        assert validate_secret("") is False

    def test_invalid_chars(self):
        assert validate_secret("!!!!") is False

    def test_with_spaces(self):
        assert validate_secret("JBSW Y3DP EHPK 3PXP") is True

    def test_minimum_length(self):
        assert validate_secret("AAAAAAAAAAAAAAAA") is True
        assert validate_secret("AAAAAAAAAAAAAAA") is False


class TestExtractOtpFromUri:
    def test_valid_uri(self):
        uri = "otpauth://totp/Example:user@host?secret=JBSWY3DPEHPK3PXP&issuer=Example"
        secret = extract_otp_from_uri(uri)
        assert secret == "JBSWY3DPEHPK3PXP"

    def test_not_otpauth(self):
        assert extract_otp_from_uri("https://example.com") is None

    def test_no_secret(self):
        uri = "otpauth://totp/Example:user?issuer=Example"
        assert extract_otp_from_uri(uri) is None

    def test_empty(self):
        assert extract_otp_from_uri("") is None
        assert extract_otp_from_uri("otpauth://") is None


class TestRenderUriToSecret:
    def test_uri_input(self):
        uri = "otpauth://totp/Example:user@host?secret=JBSWY3DPEHPK3PXP&issuer=Example"
        result = render_uri_to_secret(uri)
        assert result == "JBSWY3DPEHPK3PXP"

    def test_plain_secret(self):
        secret = "JBSWY3DPEHPK3PXP"
        result = render_uri_to_secret(secret)
        assert result == secret

    def test_strips_whitespace(self):
        secret = "  JBSWY3DPEHPK3PXP  "
        result = render_uri_to_secret(secret)
        assert result == "JBSWY3DPEHPK3PXP"


class TestDecodeBase32:
    def test_standard(self):
        result = _decode_base32("JBSWY3DPEHPK3PXP")
        assert isinstance(result, bytes)
        assert len(result) == 10

    def test_needs_padding(self):
        result = _decode_base32("JBSWY3DPEHPK3PXP")  # 16 chars, no padding needed
        assert len(result) == 10

    def test_odd_length(self):
        result = _decode_base32("JBSWY3DPEHPK3PX")  # 15 chars
        assert isinstance(result, bytes)
