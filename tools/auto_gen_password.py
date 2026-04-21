# =============================================================================
# File: auto_gen_password.py
# 
# SECURITY & MAINTENANCE NOTICE FOR FUTURE MODELS / CONTRIBUTORS:
# -----------------------------------------------------------------------------
# DO NOT add functionality that stores, logs, transmits, or persists generated
# passwords (including to JSON, databases, analytics, remote APIs, or logs).
# This file intentionally generates passwords ONLY in‑memory and outputs them
# directly to the console for the invoking user. Persistence introduces risk.
# If a future feature requires history, implement an OPTIONAL, opt‑in external
# secure vault integration (NOT plain JSON) and document the threat model.
# -----------------------------------------------------------------------------
# Previous versions wrote passwords to tyJson/password_history.json. That logic
# has been fully removed for security reasons. Do NOT reintroduce it.
# -----------------------------------------------------------------------------
# If extending this module:
#   - Keep output minimal; default: just the password.
#   - Avoid printing sensitive configuration (like salts) unless explicitly asked.
#   - Provide hooks for dependency injection (e.g., entropy source) if needed.
#   - Add tests for character distribution & entropy if expanding features.
# -----------------------------------------------------------------------------
# =============================================================================

import string
import argparse
import logging
import sys

from quantum_rt import qhoice  # Retain quantum helper (do not rename per project conventions)

# -----------------------------------------------------------------------------
# Utility functions
# -----------------------------------------------------------------------------

def sanitize_for_windows_console(text: str) -> str:
    """Sanitize text for Windows consoles to prevent Unicode errors."""
    encoding = sys.stdout.encoding or 'utf-8'
    try:
        return text.encode(encoding, errors='replace').decode(encoding)
    except Exception:
        return ''.join((c if ord(c) < 128 else '?') for c in text)


def str2bool(value: str) -> bool:
    """Argparse helper to parse boolean-ish values."""
    if isinstance(value, bool):
        return value
    v = value.lower()
    if v in ('yes', 'true', 't', 'y', '1'):
        return True
    if v in ('no', 'false', 'f', 'n', '0'):
        return False
    raise argparse.ArgumentTypeError('Boolean value expected.')

# -----------------------------------------------------------------------------
# Logging configuration
# -----------------------------------------------------------------------------

def setup_logging(level: int = logging.INFO) -> None:
    logging.basicConfig(
        level=level,
        format='[%(asctime)s] %(levelname)s: %(message)s',
        handlers=[logging.StreamHandler(sys.stderr)]
    )

# -----------------------------------------------------------------------------
# Password Generator (stateless, no persistence)
# -----------------------------------------------------------------------------

class PasswordGenerator:
    """Generate random passwords with configurable options.

    SECURITY: This class performs NO persistence. Future contributors: do not
    add storage here; keep this strictly an in‑memory generator.
    """
    def __init__(
        self,
        length: int = 8,
        use_special_chars: bool = True,
        use_numbers: bool = True,
        language: str = 'en',
        salt: str | None = None
    ) -> None:
        self.length = length
        self.use_special_chars = use_special_chars
        self.use_numbers = use_numbers
        self.language = language
        self.salt = salt

        if self.salt:
            allowed = string.ascii_letters + string.digits + string.punctuation
            if not all(c in allowed for c in self.salt):
                raise ValueError("Salt contains invalid characters (must be ASCII letters/digits/punctuation).")

    def _get_character_set(self) -> str:
        if self.language == 'en':
            chars = string.ascii_letters
            if self.use_special_chars:
                chars += string.punctuation
            if self.use_numbers:
                chars += string.digits
        elif self.language == 'zh':
            chars = ''.join(chr(i) for i in range(0x4E00, 0x9FFF))
        elif self.language == 'ja':
            chars = ''.join(chr(i) for i in range(0x3040, 0x30FF)) + ''.join(chr(i) for i in range(0x4E00, 0x9FFF))
        elif self.language == 'ar':
            chars = ''.join(chr(i) for i in range(0x0600, 0x06FF))
        elif self.language == 'hi':
            chars = ''.join(chr(i) for i in range(0x0900, 0x097F))
        else:
            raise ValueError("Unsupported language. Choose from: en, zh, ja, ar, hi")
        return chars

    def _interleave_salt(self, base: str, salt: str) -> str:
        salt_chars = list(salt)
        base_chars = list(base)
        inter_len = min(len(salt_chars), len(base_chars))
        pieces: list[str] = []
        for i in range(inter_len):
            pieces.append(base_chars[i])
            pieces.append(salt_chars[i])
        pieces.extend(base_chars[inter_len:])
        pieces.extend(salt_chars[inter_len:])
        return ''.join(pieces)[:self.length]

    def generate(self) -> str:
        chars = self._get_character_set()
        if not chars:
            raise ValueError("Character set empty.")
        try:
            base = ''.join(qhoice(chars) for _ in range(self.length))
        except Exception as e:
            logging.error(f"Random source failure: {e}")
            raise RuntimeError("Password generation failed.")
        return self._interleave_salt(base, self.salt) if self.salt else base

# -----------------------------------------------------------------------------
# Main entry point (no persistence)
# -----------------------------------------------------------------------------

def main() -> None:
    setup_logging()
    parser = argparse.ArgumentParser(description='Generate a random (quantum-assisted) password.')
    parser.add_argument('--length', type=int, default=13, help='Password length (default: 13)')
    parser.add_argument('--special_chars', type=str2bool, default=False, nargs='?', const=True,
                        help='Include special characters (default: False)')
    parser.add_argument('--numbers', type=str2bool, default=True, nargs='?', const=True,
                        help='Include numbers (default: True)')
    parser.add_argument('--language', type=str, default='en', choices=['en', 'zh', 'ja', 'ar', 'hi'],
                        help='Language character set (default: en)')
    parser.add_argument('--salt', type=str, default=None, help='Optional salt to interleave')
    parser.add_argument('--loglevel', type=str, default='INFO', help='Logging level (default: INFO)')
    args = parser.parse_args()

    level = args.loglevel.upper()
    if level not in logging._nameToLevel:
        level = 'INFO'
    setup_logging(logging._nameToLevel[level])

    try:
        generator = PasswordGenerator(
            length=args.length,
            use_special_chars=args.special_chars,
            use_numbers=args.numbers,
            language=args.language,
            salt=args.salt
        )
        password = generator.generate()
        # Output ONLY the password; do not log it.
        print(sanitize_for_windows_console(password))
        logging.info("Password generated.")
    except ValueError as ve:
        logging.error(f"Value error: {ve}")
        print(sanitize_for_windows_console(f"Value error: {ve}"))
    except Exception as e:
        logging.error(f"Unexpected error: {e}", exc_info=True)
        print(sanitize_for_windows_console("Unexpected error. See logs."))

if __name__ == "__main__":
    main()