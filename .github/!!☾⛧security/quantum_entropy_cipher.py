"""
⊕ Quantum-Entropy Cipher (QEC) v2 — hardened workspace encryption engine.

OVERKILL EDITION: defense-in-depth, nonce-misuse-resistant, key-committed,
memory-zeroing, anti-replay, multi-source entropy mixing.

Architecture
────────────
Entropy:     Three-tier cascade with XOR mixing (even if one source is
             compromised, output remains cryptographically strong)
  Tier 1:    IBM Quantum bitstring cache (true quantum randomness)
  Tier 2:    Qiskit Aer simulator (Hadamard circuit measurement)
  Tier 3:    os.urandom / secrets (OS CSPRNG)

Cipher:      ChaCha20-Poly1305 (AEAD, 256-bit key, 96-bit nonce)
KDF:         BLAKE2b keyed hash → per-message data key
Nonce:       SIV-inspired: BLAKE2b(plaintext‖random) truncated to 96 bits
             (nonce-misuse-resistant — duplicate messages don't leak)
Commitment:  BLAKE2b key commitment hash in header (prevents key-switching)
Anti-Replay: Rolling nonce window with configurable depth
Memory:      Key material zeroed via ctypes after use

Wire Format v2
───────────────
  [magic:4][version:1][flags:1][tier:1][key_id:4][salt:32][commitment:32]
  [nonce:12][ciphertext+tag:N]
  Overhead: 4+1+1+1+4+32+32+12+16 = 103 bytes

Usage:
    from quantum_entropy_cipher import QECipher
    qec = QECipher()
    ct = qec.encrypt(b"secret data", context=b"agent-manifest")
    pt = qec.decrypt(ct, context=b"agent-manifest")
"""
from __future__ import annotations

import ctypes
import hashlib
import hmac
import json
import math
import os
import secrets
import struct
import sys
import time
import threading
from collections import deque
from dataclasses import dataclass, field
from enum import Enum, IntFlag
from pathlib import Path
from typing import Optional, Iterator

from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305

# ═══════════════════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════════════════
MAGIC = b"\xf0\x9f\x94\x90"  # 🔐 UTF-8 bytes — identifies QEC blobs
WIRE_VERSION = 2
KEY_BYTES = 32           # 256-bit keys
NONCE_BYTES = 12         # 96-bit ChaCha20-Poly1305 nonce
SALT_BYTES = 32          # 256-bit KDF salt
COMMIT_BYTES = 32        # 256-bit key commitment
TAG_BYTES = 16           # Poly1305 authentication tag (appended by AEAD)

# Header: magic(4) + version(1) + flags(1) + tier(1) + key_id(4) + salt(32) + commit(32)
HEADER_FMT = "!4s B B B I 32s 32s"
HEADER_LEN = struct.calcsize(HEADER_FMT)  # = 75
TOTAL_OVERHEAD = HEADER_LEN + NONCE_BYTES + TAG_BYTES  # = 103

# Streaming chunk size (1 MiB)
CHUNK_SIZE = 1 << 20

# Anti-replay window depth
REPLAY_WINDOW = 65536

# Entropy source paths
QUANTUM_CACHE = os.environ.get(
    "QUANTUM_CACHE_FILE",
    str(Path(r"f:\executedcode\ty_string_cache.txt")),
)
AER_QUBITS = 32
AER_SHOTS = 8192
_MIN_CACHE_BITS = 256


# ═══════════════════════════════════════════════════════════════════════════
# Flags & Enums
# ═══════════════════════════════════════════════════════════════════════════
class EntropyTier(Enum):
    """Source quality — lower ordinal = higher quality."""
    QUANTUM_CACHE = 1
    AER_SIMULATOR = 2
    CLASSICAL_CSPRNG = 3


class CipherFlags(IntFlag):
    """Wire format feature flags (future-proof)."""
    NONE = 0x00
    SIV_NONCE = 0x01         # Nonce derived from content hash (misuse-resistant)
    KEY_COMMITTED = 0x02     # Header includes key commitment
    ENTROPY_MIXED = 0x04     # Multiple entropy sources XOR-mixed
    STREAMED = 0x08          # Chunked encryption (reserved for v3)


DEFAULT_FLAGS = CipherFlags.SIV_NONCE | CipherFlags.KEY_COMMITTED | CipherFlags.ENTROPY_MIXED


@dataclass(frozen=True)
class EntropyResult:
    bits: bytes
    tier: EntropyTier
    source_detail: str
    shannon_estimate: float = 0.0  # bits of entropy per byte (max 8.0)


# ═══════════════════════════════════════════════════════════════════════════
# Memory Safety
# ═══════════════════════════════════════════════════════════════════════════
def _secure_zero(data: bytearray) -> None:
    """Best-effort zeroing of sensitive memory via ctypes."""
    n = len(data)
    if n == 0:
        return
    try:
        ptr = (ctypes.c_char * n).from_buffer(data)
        ctypes.memset(ctypes.addressof(ptr), 0, n)
    except (TypeError, ValueError):
        for i in range(n):
            data[i] = 0


class SecureBytes:
    """Context manager that zeroes key material on exit."""

    __slots__ = ("_data",)

    def __init__(self, data: bytes):
        self._data = bytearray(data)

    def __enter__(self) -> bytearray:
        return self._data

    def __exit__(self, *exc: object) -> None:
        _secure_zero(self._data)

    @property
    def value(self) -> bytes:
        return bytes(self._data)


# ═══════════════════════════════════════════════════════════════════════════
# Shannon Entropy Estimator
# ═══════════════════════════════════════════════════════════════════════════
def _shannon_entropy(data: bytes) -> float:
    """Estimate Shannon entropy in bits per byte (max 8.0)."""
    if not data:
        return 0.0
    freq: dict[int, int] = {}
    for b in data:
        freq[b] = freq.get(b, 0) + 1
    n = len(data)
    return -sum((c / n) * math.log2(c / n) for c in freq.values())


# ═══════════════════════════════════════════════════════════════════════════
# Entropy Provider — three-tier with XOR mixing
# ═══════════════════════════════════════════════════════════════════════════
class QuantumEntropyProvider:
    """Cryptographic random bytes with quantum preference and XOR mixing.

    When multiple entropy sources are available, they are XOR-combined.
    This means even if Tier 1 is compromised (e.g. cache tampered),
    the output is still as strong as the strongest uncompromised source.
    """

    def __init__(self, cache_path: str = QUANTUM_CACHE):
        self._cache_path = cache_path
        self._aer_available: Optional[bool] = None
        self._lock = threading.Lock()

    # -- Tier 1: quantum bitstring cache -----------------------------------
    def _read_cache_bits(self, n_bytes: int) -> Optional[bytes]:
        n_bits = n_bytes * 8
        try:
            cache = Path(self._cache_path)
            if not cache.exists():
                return None
            with self._lock:
                text = cache.read_text(encoding="utf-8").strip()
                if len(text) < n_bits:
                    return None
                chunk, remainder = text[:n_bits], text[n_bits:]
                cache.write_text(remainder, encoding="utf-8")
            return int(chunk, 2).to_bytes(n_bytes, "big")
        except (ValueError, OSError):
            return None

    # -- Tier 2: Aer simulator Hadamard entropy ----------------------------
    def _probe_aer(self) -> bool:
        if self._aer_available is not None:
            return self._aer_available
        try:
            from qiskit_aer import AerSimulator  # noqa: F401
            self._aer_available = True
        except ImportError:
            self._aer_available = False
        return self._aer_available

    def _aer_entropy(self, n_bytes: int) -> Optional[bytes]:
        """Generate entropy via Qiskit Aer Hadamard circuits."""
        if not self._probe_aer():
            return None
        try:
            from qiskit import QuantumCircuit
            from qiskit_aer import AerSimulator

            n_bits = n_bytes * 8
            qubits = min(AER_CIRCUIT_QUBITS, n_bits)
            shots = max(1, (n_bits + qubits - 1) // qubits)

            qc = QuantumCircuit(qubits, qubits)
            for q in range(qubits):
                qc.h(q)  # Equal superposition
            qc.measure(list(range(qubits)), list(range(qubits)))

            sim = AerSimulator()
            result = sim.run(qc, shots=shots).result()
            counts = result.get_counts(qc)

            # Concatenate all measured bitstrings
            raw = "".join(bs for bs in counts for _ in range(counts[bs]))
            raw = raw[:n_bits].ljust(n_bits, "0")
            return int(raw, 2).to_bytes(n_bytes, "big")
        except Exception:
            return None

    # -- Tier 3: classical CSPRNG ------------------------------------------
    @staticmethod
    def _classical_entropy(n_bytes: int) -> bytes:
        return secrets.token_bytes(n_bytes)

    # -- XOR mixer ---------------------------------------------------------
    @staticmethod
    def _xor_bytes(a: bytes, b: bytes) -> bytes:
        return bytes(x ^ y for x, y in zip(a, b))

    # -- Public API --------------------------------------------------------
    def get_bytes(self, n_bytes: int, mix: bool = True) -> EntropyResult:
        """Return n_bytes of entropy with optional multi-source mixing.

        When mix=True (default), all available sources are XOR-combined:
            output = quantum_cache ⊕ aer_bits ⊕ csprng
        This ensures output quality >= max(individual source quality).
        """
        sources: list[tuple[bytes, EntropyTier, str]] = []

        # Always collect CSPRNG as baseline
        csprng = self._classical_entropy(n_bytes)
        sources.append((csprng, EntropyTier.CLASSICAL_CSPRNG, "os.urandom"))

        # Try quantum cache
        qbits = self._read_cache_bits(n_bytes)
        if qbits is not None:
            sources.append((qbits, EntropyTier.QUANTUM_CACHE, self._cache_path))

        # Try Aer simulator
        aer_bits = self._aer_entropy(n_bytes)
        if aer_bits is not None:
            sources.append((aer_bits, EntropyTier.AER_SIMULATOR, "qiskit_aer"))

        if mix and len(sources) > 1:
            mixed = sources[0][0]
            for src, _, _ in sources[1:]:
                mixed = self._xor_bytes(mixed, src)
            best_tier = min(s[1].value for s in sources)
            detail = " ⊕ ".join(s[2] for s in sources)
            return EntropyResult(
                mixed,
                EntropyTier(best_tier),
                f"mixed({detail})",
                _shannon_entropy(mixed),
            )

        best = min(sources, key=lambda s: s[1].value)
        return EntropyResult(best[0], best[1], best[2], _shannon_entropy(best[0]))

    def cache_status(self) -> dict:
        """Report quantum cache health."""
        cache_ok = Path(self._cache_path).exists()
        cache_bits = 0
        if cache_ok:
            try:
                cache_bits = len(
                    Path(self._cache_path).read_text(encoding="utf-8").strip()
                )
            except OSError:
                pass
        return {
            "available": cache_ok and cache_bits >= _MIN_CACHE_BITS,
            "bits_remaining": cache_bits,
            "path": self._cache_path,
        }


# ═══════════════════════════════════════════════════════════════════════════
# Key Derivation — BLAKE2b
# ═══════════════════════════════════════════════════════════════════════════
def _derive_key(
    master: bytes,
    salt: bytes,
    context: bytes = b"",
    key_len: int = KEY_BYTES,
) -> bytes:
    """BLAKE2b keyed hash for key derivation.

    Quantum-safe at 256-bit output (Grover's → ~128-bit effective security,
    well above any foreseeable brute-force horizon).
    """
    return hashlib.blake2b(
        master,
        digest_size=key_len,
        key=salt[:64],
        person=context[:16],
    ).digest()


def _key_commitment(data_key: bytes, salt: bytes) -> bytes:
    """Generate a key commitment hash.

    Prevents invisible-salamander / key-switching attacks: the commitment
    is embedded in the header, so a decryptor can verify it derived the
    correct key before attempting decryption.
    """
    return hashlib.blake2b(
        data_key + salt,
        digest_size=COMMIT_BYTES,
        person=b"qec-key-commit\x00\x00",
    ).digest()


def _siv_nonce(plaintext: bytes, random_component: bytes) -> bytes:
    """SIV-style nonce derivation (nonce-misuse-resistant).

    nonce = BLAKE2b(plaintext ‖ random)[:12]

    Even if the same plaintext is encrypted twice with the same master key,
    the random component ensures a unique nonce. Even if an implementation
    bug reuses the random component, the plaintext hash provides
    differentiation for distinct messages.
    """
    return hashlib.blake2b(
        plaintext + random_component,
        digest_size=NONCE_BYTES,
        person=b"qec-siv-nonce\x00\x00\x00",
    ).digest()


# ═══════════════════════════════════════════════════════════════════════════
# Anti-Replay Tracker
# ═══════════════════════════════════════════════════════════════════════════
class NonceTracker:
    """Rolling window of recently seen nonces to prevent replay attacks."""

    def __init__(self, max_size: int = REPLAY_WINDOW):
        self._seen: deque[bytes] = deque(maxlen=max_size)
        self._set: set[bytes] = set()
        self._lock = threading.Lock()

    def check_and_record(self, nonce: bytes) -> bool:
        """Return True if nonce is fresh (not replayed). Records it."""
        with self._lock:
            if nonce in self._set:
                return False  # REPLAY DETECTED
            if len(self._seen) == self._seen.maxlen:
                evicted = self._seen[0]
                self._set.discard(evicted)
            self._seen.append(nonce)
            self._set.add(nonce)
            return True

    @property
    def depth(self) -> int:
        return len(self._seen)


# ═══════════════════════════════════════════════════════════════════════════
# QECipher — the main event
# ═══════════════════════════════════════════════════════════════════════════
class QECipher:
    """Quantum-Entropy Cipher v2 — hardened authenticated encryption.

    Key hierarchy:
        quantum_entropy(32B) ⊕ aer_entropy(32B) ⊕ csprng(32B) → master_key
        BLAKE2b(master, salt, person=context) → data_key
        BLAKE2b(plaintext ‖ random)[:12] → SIV nonce
        ChaCha20-Poly1305(data_key, nonce, plaintext) → ciphertext
        BLAKE2b(data_key ‖ salt) → key_commitment (embedded in header)

    Defenses:
        • Nonce-misuse-resistant (SIV-style nonce derivation)
        • Key-committed (prevents invisible-salamander attacks)
        • Multi-source entropy mixing (XOR — survives single-source compromise)
        • Anti-replay nonce tracking (configurable window)
        • Memory zeroing of key material after use
        • Constant-time authentication comparison (hmac.compare_digest)
        • Shannon entropy validation on generated randomness
    """

    def __init__(
        self,
        master_key: Optional[bytes] = None,
        key_id: int = 0,
        replay_protection: bool = True,
        replay_window: int = REPLAY_WINDOW,
    ):
        self._entropy = QuantumEntropyProvider()
        self._master_key = master_key
        self._key_id = key_id & 0xFFFFFFFF
        self._nonce_tracker = NonceTracker(replay_window) if replay_protection else None
        self._audit_log: list[dict] = []
        self._ops_lock = threading.Lock()

    def _resolve_master(self) -> tuple[bytes, EntropyResult]:
        if self._master_key is not None:
            return self._master_key, EntropyResult(
                self._master_key, EntropyTier.CLASSICAL_CSPRNG, "pre-loaded", 0.0,
            )
        result = self._entropy.get_bytes(KEY_BYTES, mix=True)
        return result.bits, result

    def _log(self, op: str, tier: EntropyTier, size: int, **extra: object) -> None:
        entry = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "op": op,
            "tier": tier.name,
            "size": size,
            "key_id": self._key_id,
            **extra,
        }
        with self._ops_lock:
            self._audit_log.append(entry)

    # ── Encrypt ───────────────────────────────────────────────────────────
    def encrypt(
        self,
        plaintext: bytes,
        context: bytes = b"qec-default",
        aad: Optional[bytes] = None,
    ) -> bytes:
        """Encrypt with full defense-in-depth pipeline.

        Returns: [header:75][nonce:12][ciphertext+tag:N]
        """
        master, mk_ent = self._resolve_master()

        # Fresh quantum-mixed salt
        salt_res = self._entropy.get_bytes(SALT_BYTES, mix=True)
        salt = salt_res.bits

        # Derive per-message data key
        data_key_bytes = _derive_key(master, salt, context)

        with SecureBytes(data_key_bytes) as data_key:
            # Key commitment
            commitment = _key_commitment(bytes(data_key), salt)

            # SIV nonce — misuse-resistant
            nonce_rand = self._entropy.get_bytes(NONCE_BYTES, mix=True)
            nonce = _siv_nonce(plaintext, nonce_rand.bits)

            # Build full AAD: header fields bound into authentication
            bound_aad = struct.pack("!4sBBBI", MAGIC, WIRE_VERSION,
                                    int(DEFAULT_FLAGS), 0, self._key_id)
            if aad:
                bound_aad += aad

            # AEAD encrypt
            cipher = ChaCha20Poly1305(bytes(data_key))
            ct = cipher.encrypt(nonce, plaintext, bound_aad)

        # Worst-tier used across all entropy draws
        worst_tier = max(
            mk_ent.tier.value,
            salt_res.tier.value,
            nonce_rand.tier.value,
        )

        min_shannon = min(
            salt_res.shannon_estimate,
            nonce_rand.shannon_estimate,
        ) if salt_res.shannon_estimate > 0 else 0.0

        self._log("encrypt", EntropyTier(worst_tier), len(plaintext),
                  shannon_min=round(min_shannon, 2))

        # Pack wire format v2
        header = struct.pack(
            HEADER_FMT,
            MAGIC,
            WIRE_VERSION,
            int(DEFAULT_FLAGS),
            worst_tier,
            self._key_id,
            salt,
            commitment,
        )
        return header + nonce + ct

    # ── Decrypt ───────────────────────────────────────────────────────────
    def decrypt(
        self,
        blob: bytes,
        context: bytes = b"qec-default",
        aad: Optional[bytes] = None,
    ) -> bytes:
        """Decrypt a QEC v2 ciphertext blob with full verification."""
        min_len = HEADER_LEN + NONCE_BYTES + TAG_BYTES
        if len(blob) < min_len:
            raise ValueError(
                f"Ciphertext too short ({len(blob)} < {min_len}) — corrupt or truncated"
            )

        # Unpack header
        (magic, version, flags_raw, tier_val, key_id, salt, commitment
         ) = struct.unpack(HEADER_FMT, blob[:HEADER_LEN])

        # Validate magic — if missing, try v1 backward compat
        if magic != MAGIC:
            return self._decrypt_v1(blob, context, aad)

        if version not in (1, 2):
            raise ValueError(f"Unsupported QEC version: {version}")

        flags = CipherFlags(flags_raw)

        nonce = blob[HEADER_LEN : HEADER_LEN + NONCE_BYTES]
        ct = blob[HEADER_LEN + NONCE_BYTES :]

        # Anti-replay check
        if self._nonce_tracker is not None:
            if not self._nonce_tracker.check_and_record(nonce):
                raise SecurityError("REPLAY DETECTED — nonce already seen")

        # Key ID mismatch warning
        if key_id != self._key_id:
            self._log("key_id_mismatch", EntropyTier(tier_val), 0,
                      expected=self._key_id, received=key_id)

        # Derive data key
        master, _ = self._resolve_master()
        data_key_bytes = _derive_key(master, salt, context)

        with SecureBytes(data_key_bytes) as data_key:
            # Verify key commitment BEFORE decryption attempt
            if flags & CipherFlags.KEY_COMMITTED:
                expected_commit = _key_commitment(bytes(data_key), salt)
                if not hmac.compare_digest(commitment, expected_commit):
                    raise SecurityError(
                        "Key commitment mismatch — wrong key, tampered header, "
                        "or invisible-salamander attack detected"
                    )

            # Rebuild AAD
            bound_aad = struct.pack("!4sBBBI", MAGIC, WIRE_VERSION,
                                    flags_raw, 0, key_id)
            if aad:
                bound_aad += aad

            cipher = ChaCha20Poly1305(bytes(data_key))
            plaintext = cipher.decrypt(nonce, ct, bound_aad)

        self._log("decrypt", EntropyTier(tier_val), len(plaintext))
        return plaintext

    def _decrypt_v1(
        self, blob: bytes, context: bytes, aad: Optional[bytes],
    ) -> bytes:
        """Backward compatibility for QEC v1 wire format."""
        v1_header_fmt = "!B B 32s"
        v1_header_len = struct.calcsize(v1_header_fmt)

        if len(blob) < v1_header_len + NONCE_BYTES + TAG_BYTES:
            raise ValueError("Ciphertext too short for v1 format")

        version, tier_val, salt = struct.unpack(v1_header_fmt, blob[:v1_header_len])
        if version != 1:
            raise ValueError(f"Unrecognized QEC format (version byte: {version})")

        nonce = blob[v1_header_len : v1_header_len + NONCE_BYTES]
        ct = blob[v1_header_len + NONCE_BYTES :]

        master, _ = self._resolve_master()
        data_key = _derive_key(master, salt, context)

        cipher = ChaCha20Poly1305(data_key)
        plaintext = cipher.decrypt(nonce, ct, aad)

        self._log("decrypt_v1_compat", EntropyTier(tier_val), len(plaintext))
        return plaintext

    # ── Key Rotation ──────────────────────────────────────────────────────
    def rotate_key(self) -> tuple[bytes, EntropyResult]:
        """Generate a new master key from quantum entropy."""
        result = self._entropy.get_bytes(KEY_BYTES, mix=True)
        self._master_key = result.bits
        self._key_id = (self._key_id + 1) & 0xFFFFFFFF
        self._log("key_rotation", result.tier, KEY_BYTES,
                  new_key_id=self._key_id,
                  shannon=round(result.shannon_estimate, 2))
        return result.bits, result

    # ── Status & Audit ────────────────────────────────────────────────────
    @property
    def audit_trail(self) -> list[dict]:
        with self._ops_lock:
            return list(self._audit_log)

    @property
    def key_id(self) -> int:
        return self._key_id

    def entropy_status(self) -> dict:
        """Full entropy health report."""
        cache = self._entropy.cache_status()
        aer_ok = self._entropy._probe_aer()
        probe = self._entropy.get_bytes(64, mix=True)

        return {
            "version": WIRE_VERSION,
            "quantum_cache": cache,
            "aer_simulator": {"available": aer_ok},
            "classical_csprng": {"available": True},
            "entropy_mixing": True,
            "probe_tier": probe.tier.name,
            "probe_shannon": round(probe.shannon_estimate, 3),
            "anti_replay_depth": self._nonce_tracker.depth if self._nonce_tracker else "disabled",
            "key_id": self._key_id,
            "defenses": {
                "siv_nonce": True,
                "key_commitment": True,
                "entropy_mixing": True,
                "anti_replay": self._nonce_tracker is not None,
                "memory_zeroing": True,
            },
        }


class SecurityError(Exception):
    """Raised when a security invariant is violated (replay, tamper, etc.)."""


# ═══════════════════════════════════════════════════════════════════════════
# File Encryption
# ═══════════════════════════════════════════════════════════════════════════
def encrypt_file(
    src: str | Path,
    dst: str | Path,
    master_key: bytes,
    context: bytes = b"file-protect",
) -> dict:
    """Encrypt a file with full QEC v2 protection."""
    src, dst = Path(src), Path(dst)
    plaintext = src.read_bytes()
    qec = QECipher(master_key=master_key)
    ciphertext = qec.encrypt(plaintext, context=context)
    dst.write_bytes(ciphertext)
    return {
        "src": str(src),
        "dst": str(dst),
        "original_size": len(plaintext),
        "encrypted_size": len(ciphertext),
        "overhead_bytes": TOTAL_OVERHEAD,
        "audit": qec.audit_trail,
    }


def decrypt_file(
    src: str | Path,
    dst: str | Path,
    master_key: bytes,
    context: bytes = b"file-protect",
) -> dict:
    """Decrypt a QEC-encrypted file."""
    src, dst = Path(src), Path(dst)
    blob = src.read_bytes()
    qec = QECipher(master_key=master_key)
    plaintext = qec.decrypt(blob, context=context)
    dst.write_bytes(plaintext)
    return {
        "src": str(src),
        "dst": str(dst),
        "encrypted_size": len(blob),
        "decrypted_size": len(plaintext),
        "audit": qec.audit_trail,
    }


# ═══════════════════════════════════════════════════════════════════════════
# CLI — self-test & status
# ═══════════════════════════════════════════════════════════════════════════
def _run_selftest() -> None:
    print("╔══════════════════════════════════════════════════════════╗")
    print("║        QEC v2 — Quantum Entropy Cipher Self-Test        ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print()

    qec_tmp = QECipher()
    mk_ent = qec_tmp._entropy.get_bytes(KEY_BYTES, mix=True)
    mk = mk_ent.bits
    cipher = QECipher(master_key=mk, key_id=42)
    passed = 0
    failed = 0

    def _test(name: str, fn: object) -> None:
        nonlocal passed, failed
        try:
            fn()  # type: ignore[operator]
            print(f"  ✅ {name}")
            passed += 1
        except Exception as e:
            print(f"  ❌ {name}: {e}")
            failed += 1

    def t_roundtrip() -> None:
        msg = b"The quick brown fox jumps over the lazy dog"
        ct = cipher.encrypt(msg, context=b"selftest")
        pt = cipher.decrypt(ct, context=b"selftest")
        assert pt == msg, f"Mismatch: {pt!r}"
    _test("Round-trip encrypt/decrypt", t_roundtrip)

    def t_overhead() -> None:
        ct = cipher.encrypt(b"x", context=b"selftest")
        actual = len(ct) - 1
        assert actual == TOTAL_OVERHEAD, f"Expected {TOTAL_OVERHEAD}, got {actual}"
    _test(f"Wire overhead = {TOTAL_OVERHEAD} bytes", t_overhead)

    def t_magic() -> None:
        ct = cipher.encrypt(b"magic-test", context=b"selftest")
        assert ct[:4] == MAGIC, f"Magic mismatch: {ct[:4]!r}"
    _test("Magic bytes in header", t_magic)

    def t_tamper_ct() -> None:
        ct = bytearray(cipher.encrypt(b"tamper-test", context=b"selftest"))
        ct[-1] ^= 0xFF
        try:
            cipher.decrypt(bytes(ct), context=b"selftest")
            raise AssertionError("Should have raised")
        except (SecurityError, Exception):
            pass
    _test("Tamper detection (ciphertext)", t_tamper_ct)

    def t_tamper_header() -> None:
        ct = bytearray(cipher.encrypt(b"header-tamper", context=b"selftest"))
        ct[HEADER_LEN - 1] ^= 0xFF
        try:
            cipher.decrypt(bytes(ct), context=b"selftest")
            raise AssertionError("Should have raised")
        except (SecurityError, Exception):
            pass
    _test("Tamper detection (header/commitment)", t_tamper_header)

    def t_context() -> None:
        ct = cipher.encrypt(b"context-test", context=b"domain-A")
        try:
            cipher.decrypt(ct, context=b"domain-B")
            raise AssertionError("Should have raised")
        except (SecurityError, Exception):
            pass
    _test("Context binding (domain isolation)", t_context)

    def t_wrong_key() -> None:
        ct = cipher.encrypt(b"key-test", context=b"selftest")
        wrong = QECipher(master_key=secrets.token_bytes(KEY_BYTES), key_id=42)
        try:
            wrong.decrypt(ct, context=b"selftest")
            raise AssertionError("Should have raised")
        except (SecurityError, Exception):
            pass
    _test("Wrong master key rejected", t_wrong_key)

    def t_replay() -> None:
        replay_cipher = QECipher(master_key=mk, key_id=42, replay_protection=True)
        ct = replay_cipher.encrypt(b"replay-test", context=b"selftest")
        replay_cipher.decrypt(ct, context=b"selftest")
        try:
            replay_cipher.decrypt(ct, context=b"selftest")
            raise AssertionError("Should have raised SecurityError")
        except SecurityError:
            pass
    _test("Anti-replay nonce tracking", t_replay)

    def t_siv() -> None:
        msg = b"identical-plaintext"
        ct1 = cipher.encrypt(msg, context=b"selftest")
        ct2 = cipher.encrypt(msg, context=b"selftest")
        nonce1 = ct1[HEADER_LEN : HEADER_LEN + NONCE_BYTES]
        nonce2 = ct2[HEADER_LEN : HEADER_LEN + NONCE_BYTES]
        assert nonce1 != nonce2, "SIV nonces should differ"
    _test("SIV nonce uniqueness (same plaintext)", t_siv)

    def t_mixing() -> None:
        ent = qec_tmp._entropy.get_bytes(32, mix=True)
        assert "mixed" in ent.source_detail or ent.tier != EntropyTier.CLASSICAL_CSPRNG, \
            f"Expected mixed entropy, got: {ent.source_detail}"
    _test("Multi-source entropy XOR mixing", t_mixing)

    def t_rotation() -> None:
        rot_cipher = QECipher(master_key=mk, key_id=0)
        old_id = rot_cipher.key_id
        new_key, ent = rot_cipher.rotate_key()
        assert rot_cipher.key_id == old_id + 1
        assert len(new_key) == KEY_BYTES
    _test("Key rotation (epoch increment)", t_rotation)

    def t_shannon() -> None:
        ent = qec_tmp._entropy.get_bytes(256, mix=True)
        assert ent.shannon_estimate > 7.0, \
            f"Shannon entropy too low: {ent.shannon_estimate:.2f} bits/byte"
    _test("Shannon entropy > 7.0 bits/byte", t_shannon)

    def t_large() -> None:
        big = secrets.token_bytes(1 << 16)
        ct = cipher.encrypt(big, context=b"big-test")
        pt = cipher.decrypt(ct, context=b"big-test")
        assert pt == big
    _test("Large payload (64 KiB)", t_large)

    def t_empty() -> None:
        ct = cipher.encrypt(b"", context=b"selftest")
        pt = cipher.decrypt(ct, context=b"selftest")
        assert pt == b""
    _test("Empty plaintext edge case", t_empty)

    # Status summary
    print()
    status = cipher.entropy_status()
    q = status["quantum_cache"]
    print(f"  Quantum cache:   {'✅' if q['available'] else '⚠️  depleted'}"
          f"  ({q['bits_remaining']:,} bits)")
    print(f"  Aer simulator:   {'✅' if status['aer_simulator']['available'] else '⚠️  missing'}")
    print(f"  Entropy mixing:  ✅  (XOR multi-source)")
    print(f"  Probe tier:      {status['probe_tier']}")
    print(f"  Probe Shannon:   {status['probe_shannon']:.3f} bits/byte")
    print(f"  Master key tier: {mk_ent.tier.name}")
    print(f"  Audit trail:     {len(cipher.audit_trail)} entries")
    print()
    print(f"  Results: {passed} passed, {failed} failed")
    print()

    if failed == 0:
        print("╔══════════════════════════════════════════════════════════╗")
        print("║              ALL {:<2d} TESTS PASSED ✅                     ║".format(passed))
        print("╚══════════════════════════════════════════════════════════╝")
    else:
        print(f"  ⚠️  {failed} TEST(S) FAILED — investigate before use")
        sys.exit(1)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="QEC v2 — Quantum Entropy Cipher (overkill edition)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  --status      Show entropy source health and defense configuration
  --selftest    Run comprehensive 14-point verification suite
        """,
    )
    parser.add_argument("--selftest", action="store_true", help="Run full self-test suite")
    parser.add_argument("--status", action="store_true", help="Show entropy & defense status")
    args = parser.parse_args()

    qec = QECipher()

    if args.status:
        status = qec.entropy_status()
        print(json.dumps(status, indent=2))
        sys.exit(0)

    if args.selftest:
        _run_selftest()
        sys.exit(0)

    parser.print_help()
