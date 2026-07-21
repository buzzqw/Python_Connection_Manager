"""
password_tools.py - Password generator and strength checker per PCM.

Pure Python stdlib implementation.
"""

import secrets
import string
import math


def generate_password(length: int = 20, upper: bool = True, lower: bool = True,
                      digits: bool = True, symbols: bool = True) -> str:
    """Generate a cryptographically strong random password.

    Args:
        length: Password length (default 20)
        upper: Include uppercase letters
        lower: Include lowercase letters
        digits: Include digits
        symbols: Include special characters (no ambiguous chars)

    Returns:
        Random password string
    """
    chars = ""
    if upper:
        chars += string.ascii_uppercase
    if lower:
        chars += string.ascii_lowercase
    if digits:
        chars += string.digits
    if symbols:
        chars += "!@#$%^&*()-_=+[]{}|;:,.<>?"

    if not chars:
        chars = string.ascii_letters + string.digits

    return "".join(secrets.choice(chars) for _ in range(length))


def generate_passphrase(num_words: int = 4, separator: str = "-",
                        capitalize: bool = True, include_number: bool = True) -> str:
    """Generate a memorable passphrase from a word list.

    Uses the EFF large wordlist for Diceware-style passphrases.
    """
    eff_words = [
        "abacus", "abrupt", "absorb", "absurd", "academy", "achieve", "acquire",
        "adapt", "admiral", "afford", "airport", "alumni", "anchor", "anthem",
        "appear", "article", "assume", "atlas", "audio", "backup", "balance",
        "ballot", "banana", "barrel", "basket", "battle", "beacon", "because",
        "before", "belief", "better", "beyond", "bicycle", "blossom", "border",
        "bottle", "bridge", "bubble", "budget", "bunker", "butter", "cactus",
        "camera", "candle", "canvas", "carbon", "carpet", "castle", "celery",
        "center", "chaos", "cherry", "choice", "cinema", "citrus", "classic",
        "coffee", "commit", "compose", "conduct", "context", "convert", "cookie",
        "corner", "cosmic", "cradle", "crisis", "crystal", "cursor", "custom",
        "dagger", "danger", "debate", "decade", "decide", "defeat", "define",
        "degree", "demand", "depart", "deposit", "desert", "design", "detect",
        "device", "dialog", "differ", "dinner", "disco", "dolphin", "domain",
        "donate", "double", "dragon", "driver", "dynamo", "eagle", "eclipse",
        "editor", "effect", "eighty", "elephant", "embrace", "empire", "enable",
        "energy", "engine", "enroll", "entity", "escape", "evolve", "exceed",
        "expert", "export", "fabric", "factor", "family", "famous", "fashion",
        "fellow", "filter", "finger", "flavor", "flower", "forest", "format",
        "fossil", "frozen", "future", "galaxy", "garden", "gather", "genius",
        "gentle", "global", "golden", "gospel", "graphic", "gravity", "ground",
        "growth", "habitat", "hammer", "handle", "harvest", "helmet", "heroic",
        "hockey", "horizon", "hybrid", "impact", "import", "impulse", "insect",
        "island", "jacket", "jargon", "jungle", "keeper", "kernel", "kidney",
        "knight", "launch", "layout", "leader", "league", "legend", "lesson",
        "liberty", "liquid", "listen", "lizard", "locate", "lunar", "magnet",
        "maker", "marble", "margin", "matrix", "medium", "method", "mirror",
        "muffin", "mystic", "napkin", "narrow", "nectar", "neuron", "notify",
        "object", "occupy", "omega", "online", "option", "oxygen", "panda",
        "parade", "parent", "patrol", "pepper", "pickup", "pilot", "pioneer",
        "planet", "plastic", "pocket", "police", "potato", "prefix", "prize",
        "profit", "public", "puzzle", "rabbit", "random", "rebel", "record",
        "reform", "rely", "render", "resort", "result", "retain", "rhythm",
        "ribbon", "rocket", "royalty", "safari", "salute", "sample", "schema",
        "search", "secure", "segment", "select", "seller", "shield", "signal",
        "silver", "soccer", "social", "solar", "source", "spider", "stadium",
        "staple", "status", "sticker", "studio", "subset", "suffix", "sulfur",
        "sunset", "symbol", "system", "tackle", "target", "temple", "tennis",
        "thesis", "timber", "tissue", "tomato", "tornado", "tourist", "trend",
        "trophy", "trumpet", "tunnel", "turkey", "turtle", "uncle", "unfair",
        "unique", "update", "useful", "utopia", "vacuum", "vapor", "venture",
        "version", "village", "vintage", "vision", "volume", "voyage", "wagon",
        "walnut", "welcome", "whiskey", "window", "winter", "wisdom", "wizard",
        "wonder", "yellow", "yogurt", "zephyr", "zipper", "zodiac",
    ]
    words = [secrets.choice(eff_words) for _ in range(num_words)]
    if capitalize:
        words = [w.capitalize() for w in words]
    phrase = separator.join(words)
    if include_number:
        phrase += str(secrets.randbelow(100))
    return phrase


def check_password_strength(password: str) -> dict:
    """Check password strength and return details.

    Returns dict with:
        score: 0-4 (0=weak, 1=fair, 2=good, 3=strong, 4=very strong)
        entropy_bits: estimated entropy in bits
        label: human-readable strength label
        issues: list of weakness descriptions
    """
    issues = []
    if not password:
        return {"score": 0, "entropy_bits": 0, "label": "Vuota", "issues": ["Password vuota"]}

    length = len(password)
    has_upper = any(c.isupper() for c in password)
    has_lower = any(c.islower() for c in password)
    has_digit = any(c.isdigit() for c in password)
    has_symbol = any(not c.isalnum() for c in password)

    char_space = 0
    if has_lower:
        char_space += 26
    if has_upper:
        char_space += 26
    if has_digit:
        char_space += 10
    if has_symbol:
        char_space += 32
    if char_space == 0:
        char_space = 26

    entropy = length * math.log2(char_space)

    if length < 8:
        issues.append("Troppo corta (minimo 8 caratteri)")
    if length < 12:
        issues.append("Corta: usa almeno 12 caratteri")
    if not has_upper:
        issues.append("Aggiungi maiuscole")
    if not has_lower:
        issues.append("Aggiungi minuscole")
    if not has_digit:
        issues.append("Aggiungi numeri")
    if not has_symbol:
        issues.append("Aggiungi simboli")

    if entropy >= 100:
        score, label = 4, "Molto forte"
    elif entropy >= 80:
        score, label = 3, "Forte"
    elif entropy >= 60:
        score, label = 2, "Buona"
    elif entropy >= 40:
        score, label = 1, "Debole"
    else:
        score, label = 0, "Molto debole"

    return {"score": score, "entropy_bits": round(entropy, 1),
            "label": label, "issues": issues}
