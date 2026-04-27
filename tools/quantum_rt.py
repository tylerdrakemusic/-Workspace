"""
quantum_rt.py — tools/ shim (f:\\⊕Workspace\\tools\\quantum_rt.py)

Co-located with tools that do bare `from quantum_rt import ...` without
adding any custom sys.path entries. Delegates to the canonical at:
    f:\\⟨ψ⟩Quantum\\src\\utils\\quantum_rt.py

Do NOT add logic here. Keep this file as a pure redirect.
"""
import importlib.util
import sys
from pathlib import Path

# tools/ -> ⊕Workspace/ -> f:\ -> ⟨ψ⟩Quantum/src/utils/quantum_rt.py
_CANONICAL = (
    Path(__file__).resolve().parents[2]  # f:\
    / "\u27e8\u03c8\u27e9Quantum"
    / "src"
    / "utils"
    / "quantum_rt.py"
)

if not _CANONICAL.exists():
    raise ImportError(
        f"quantum_rt canonical not found at {_CANONICAL}. "
        "Ensure ⟨ψ⟩Quantum project is present on the f:\\ drive."
    )

_spec = importlib.util.spec_from_file_location("quantum_rt", _CANONICAL)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)  # type: ignore[union-attr]
sys.modules[__name__] = _mod
