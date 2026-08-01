import pytest
import string

from password_tools import generate_password, generate_passphrase, check_password_strength


class TestGeneratePassword:
    def test_default_length(self):
        pwd = generate_password()
        assert len(pwd) == 20

    def test_custom_length(self):
        pwd = generate_password(length=32)
        assert len(pwd) == 32

    def test_only_uppercase(self):
        pwd = generate_password(length=50, upper=True, lower=False, digits=False, symbols=False)
        assert len(pwd) == 50
        assert all(c in string.ascii_uppercase for c in pwd)

    def test_only_lowercase(self):
        pwd = generate_password(length=50, upper=False, lower=True, digits=False, symbols=False)
        assert len(pwd) == 50
        assert all(c in string.ascii_lowercase for c in pwd)

    def test_only_digits(self):
        pwd = generate_password(length=30, upper=False, lower=False, digits=True, symbols=False)
        assert len(pwd) == 30
        assert all(c in string.digits for c in pwd)

    def test_only_symbols(self):
        pwd = generate_password(length=40, upper=False, lower=False, digits=False, symbols=True)
        assert len(pwd) == 40
        symbol_set = "!@#$%^&*()-_=+[]{}|;:,.<>?"
        assert all(c in symbol_set for c in pwd)

    def test_empty_charset_fallback(self):
        pwd = generate_password(length=10, upper=False, lower=False, digits=False, symbols=False)
        assert len(pwd) == 10
        assert all(c in string.ascii_letters + string.digits for c in pwd)

    def test_randomness_generates_different(self):
        pwds = {generate_password(length=20) for _ in range(10)}
        assert len(pwds) == 10

    def test_all_charsets(self):
        pwd = generate_password(length=100, upper=True, lower=True, digits=True, symbols=True)
        assert any(c.isupper() for c in pwd)
        assert any(c.islower() for c in pwd)
        assert any(c.isdigit() for c in pwd)
        symbol_set = "!@#$%^&*()-_=+[]{}|;:,.<>?"
        assert any(c in symbol_set for c in pwd)


class TestGeneratePassphrase:
    def test_default_four_words(self):
        phrase = generate_passphrase()
        # Format: Word-Word-Word-WordNN where NN is a number (no separator before number)
        # Count words by splitting on separator and checking non-digit parts
        parts = phrase.split("-")
        word_count = 0
        for p in parts:
            # Remove trailing digits (from the last word+number combo)
            word = p.rstrip("0123456789")
            if word:
                word_count += 1
        assert word_count == 4

    def test_custom_word_count(self):
        phrase = generate_passphrase(num_words=6, separator="_", include_number=False)
        assert len(phrase.split("_")) == 6

    def test_include_number(self):
        phrase = generate_passphrase(include_number=True)
        assert phrase[-2:].isdigit() or phrase[-1:].isdigit()

    def test_no_number(self):
        phrase = generate_passphrase(include_number=False)
        assert not any(c.isdigit() for c in phrase)

    def test_capitalize(self):
        phrase = generate_passphrase(capitalize=True, include_number=False)
        for word in phrase.split("-"):
            assert word[0].isupper()

    def test_no_capitalize(self):
        phrase = generate_passphrase(capitalize=False, include_number=False)
        for word in phrase.split("-"):
            assert word[0].islower()

    def test_randomness(self):
        phrases = {generate_passphrase() for _ in range(10)}
        assert len(phrases) == 10

    def test_separator(self):
        phrase = generate_passphrase(separator=".", include_number=False)
        assert "." in phrase
        assert "-" not in phrase


class TestCheckPasswordStrength:
    def test_empty_password(self):
        result = check_password_strength("")
        assert result["score"] == 0
        assert result["entropy_bits"] == 0
        assert len(result["issues"]) > 0

    def test_weak_short(self):
        result = check_password_strength("abc")
        assert result["score"] == 0
        assert result["entropy_bits"] < 40

    def test_fair(self):
        result = check_password_strength("abcdefgh")
        assert result["score"] <= 2
        assert len(result["issues"]) > 0

    def test_strong(self):
        result = check_password_strength("Tr0ub4dor&3Secure!")
        assert result["score"] >= 2
        assert result["entropy_bits"] > 60

    def test_very_strong(self):
        result = check_password_strength("Correct-Horse-Battery-Staple-99!")
        assert result["score"] >= 3
        assert result["entropy_bits"] > 80

    def test_issues_for_missing_categories(self):
        result = check_password_strength("abcdefgh")
        issues = result["issues"]
        assert any("maiuscole" in i.lower() for i in issues)
        assert any("numeri" in i.lower() for i in issues)

    def test_monotonic_entropy(self):
        weak = check_password_strength("abc")["entropy_bits"]
        strong = check_password_strength("abcABC123!@#defGHI")["entropy_bits"]
        assert strong > weak
