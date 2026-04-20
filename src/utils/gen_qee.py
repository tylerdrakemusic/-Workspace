"""
⊕Workspace — gen_qee.py  (Quantum Entropy Engine)

Quantum-assisted password / key generator for all workspace projects.
Migrated from f:\executedcode\^auto_gen_password.py and promoted to a
shared workspace utility so any project can invoke it.

OUTPUT POLICY (UNCHANGED FROM ORIGINAL):
  - Passwords are generated ONLY in-memory and written to stdout.
  - Nothing is stored, logged, persisted, or transmitted.
  - DO NOT add persistence. See security notice in original file.

Importable API:
    from gen_qee import PasswordGenerator, generate_key
    key = generate_key(length=40, special_chars=False)

CLI (same interface as original auto_gen_password.py):
    C:\G\python.exe src/utils/gen_qee.py
    C:\G\python.exe src/utils/gen_qee.py --length 40 --special_chars false
    C:\G\python.exe src/utils/gen_qee.py --length 20 --language zh
"""

import argparse
import logging
import string
import sys
from pathlib import Path

# ── Quantum RNG bootstrap ─────────────────────────────────────────────────────
# quantum_rt.py shim lives at f:\executedcode\quantum_rt.py and delegates to
# ⟨ψ⟩Quantum/src/core/quantum_rt.py. Add executedcode root to sys.path so the
# import works regardless of invocation working directory.

_EXECUTEDCODE_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_EXECUTEDCODE_ROOT) not in sys.path:
    sys.path.insert(0, str(_EXECUTEDCODE_ROOT))

try:
    from quantum_rt import qhoice  # noqa: E402
except Exception as _qe:
    # Fallback: use secrets module if quantum backend unavailable
    import secrets as _secrets
    def qhoice(seq):  # type: ignore[misc]
        return _secrets.choice(seq)
    logging.getLogger(__name__).warning(
        "quantum_rt unavailable (%s) — falling back to secrets.choice", _qe
    )

# ── Utility helpers ───────────────────────────────────────────────────────────

def _sanitize(text: str) -> str:
    """Sanitize text for Windows consoles."""
    enc = sys.stdout.encoding or "utf-8"
    try:
        return text.encode(enc, errors="replace").decode(enc)
    except Exception:
        return "".join(c if ord(c) < 128 else "?" for c in text)


def _str2bool(value: str) -> bool:
    if isinstance(value, bool):
        return value
    v = value.lower()
    if v in ("yes", "true", "t", "y", "1"):
        return True
    if v in ("no", "false", "f", "n", "0"):
        return False
    raise argparse.ArgumentTypeError("Boolean value expected.")


# ── Core generator ────────────────────────────────────────────────────────────

class PasswordGenerator:
    """Stateless quantum-assisted password generator.

    SECURITY: No persistence. Do not add storage to this class.
    """

    def __init__(
        self,
        length: int = 13,
        use_special_chars: bool = False,
        use_numbers: bool = True,
        language: str = "en",
        salt: str | None = None,
    ) -> None:
        self.length = length
        self.use_special_chars = use_special_chars
        self.use_numbers = use_numbers
        self.language = language
        self.salt = salt

        if self.salt:
            allowed = string.ascii_letters + string.digits + string.punctuation
            if not all(c in allowed for c in self.salt):
                raise ValueError(
                    "Salt contains invalid characters (must be ASCII letters/digits/punctuation)."
                )

    def _charset(self) -> str:
        lang = self.language
        if lang == "en":
            chars = string.ascii_letters
            if self.use_special_chars:
                chars += string.punctuation
            if self.use_numbers:
                chars += string.digits
        elif lang == "zh":
            chars = "".join(chr(i) for i in range(0x4E00, 0x9FFF))
        elif lang == "ja":
            chars = "".join(chr(i) for i in range(0x3040, 0x30FF))
            chars += "".join(chr(i) for i in range(0x4E00, 0x9FFF))
        elif lang == "ar":
            chars = "".join(chr(i) for i in range(0x0600, 0x06FF))
        elif lang == "hi":
            chars = "".join(chr(i) for i in range(0x0900, 0x097F))
        else:
            raise ValueError(f"Unsupported language: {lang!r}. Choose: en, zh, ja, ar, hi")
        return chars

    def _interleave_salt(self, base: str, salt: str) -> str:
        pieces: list[str] = []
        b, s = list(base), list(salt)
        n = min(len(b), len(s))
        for i in range(n):
            pieces.append(b[i])
            pieces.append(s[i])
        pieces.extend(b[n:])
        pieces.extend(s[n:])
        return "".join(pieces)[: self.length]

    def generate(self) -> str:
        chars = self._charset()
        if not chars:
            raise ValueError("Character set is empty.")
        try:
            base = "".join(qhoice(chars) for _ in range(self.length))
        except Exception as e:
            raise RuntimeError(f"Password generation failed: {e}") from e
        return self._interleave_salt(base, self.salt) if self.salt else base


# ── Convenience function ──────────────────────────────────────────────────────

def generate_key(
    length: int = 40,
    special_chars: bool = False,
    numbers: bool = True,
    salt: str | None = None,
) -> str:
    """Generate and return a single key string. No side effects."""
    return PasswordGenerator(
        length=length,
        use_special_chars=special_chars,
        use_numbers=numbers,
        salt=salt,
    ).generate()


# ── CLI entry point ───────────────────────────────────────────────────────────

def _setup_logging(level: int = logging.INFO) -> None:
    logging.basicConfig(
        level=level,
        format="[%(asctime)s] %(levelname)s: %(message)s",
        handlers=[logging.StreamHandler(sys.stderr)],
    )


def main() -> None:
    _setup_logging()
    parser = argparse.ArgumentParser(
        description="gen_qee — Quantum Entropy Engine password/key generator"
    )
    parser.add_argument("--length", type=int, default=13, help="Output length (default: 13)")
    parser.add_argument(
        "--special_chars", type=_str2bool, default=False, nargs="?", const=True,
        help="Include special characters (default: False)",
    )
    parser.add_argument(
        "--numbers", type=_str2bool, default=True, nargs="?", const=True,
        help="Include numbers (default: True)",
    )
    parser.add_argument(
        "--language", type=str, default="en", choices=["en", "zh", "ja", "ar", "hi"],
        help="Character set language (default: en)",
    )
    parser.add_argument("--salt", type=str, default=None, help="Optional salt to interleave")
    parser.add_argument("--loglevel", type=str, default="INFO", help="Logging level (default: INFO)")
    args = parser.parse_args()

    lvl = args.loglevel.upper()
    if lvl not in logging._nameToLevel:
        lvl = "INFO"
    _setup_logging(logging._nameToLevel[lvl])

    try:
        pw = PasswordGenerator(
            length=args.length,
            use_special_chars=args.special_chars,
            use_numbers=args.numbers,
            language=args.language,
            salt=args.salt,
        ).generate()
        print(_sanitize(pw))  # stdout: password only
        logging.info("Key generated.")
    except ValueError as e:
        logging.error("Value error: %s", e)
        sys.exit(1)
    except Exception as e:
        logging.error("Unexpected error: %s", e, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
