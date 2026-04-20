---
name: scope-creep
description: "Use when auditing for artifacts created in the wrong project scope. Detects files (code, integrations, data, docs) that logically belong to a different project (∞Life, ❤Music, ⟨ψ⟩Quantum, ⊕Workspace) than where they currently live. Handles safe move with import/reference impact analysis, consumer update, and verification. USE FOR: integration files landing in wrong project, shared utilities duplicated across projects, research docs in wrong scope, DB schemas drifting into wrong project. DO NOT USE FOR: cross-cutting concerns intentionally shared (e.g. QAOA algorithm in ⟨ψ⟩Quantum is correct even if it serves ❤Music and ∞Life via integrations)."
user-invocable: true
---

# Scope Creep Detection & Remediation

Artifacts created during integration work frequently land in the wrong project scope.
This skill detects misplaced files, validates the correct home, moves them safely,
and updates all referencing consumers.

---

## When to Use

- Integration work produced files that cross project boundaries
- A `src/integrations/` folder in one project contains logic that belongs to another
- Data files, DB schemas, or research docs are in the wrong project's directory tree
- A new module was added to the wrong `src/` folder (e.g. ❤Music logic inside ⟨ψ⟩Quantum)

---

## Project Scope Rules

| Sigil | Project Root | Owns |
|-------|-------------|------|
| **∞** | `f:\executedcode\∞Life\` | Health data, supplements, biomarkers, longevity protocols, body composition |
| **❤** | `f:\executedcode\❤Music\` | Songs, setlists, gigs, albums, music production, catalog |
| **⟨ψ⟩** | `f:\executedcode\⟨ψ⟩Quantum\` | Quantum algorithms, circuits, IBM QPU, QAOA core, quantum RNG |
| **⊕** | `f:\executedcode\⊕Workspace\` | Cross-project utilities, perf tracking, agent orchestration |

### Integration Boundary Rule

> **Cross-project integration code belongs to the project that OWNS the algorithm/engine,
> but the data adapter belongs to the project that OWNS the data.**

Examples:
- `qaoa.py` (algorithm) → ⟨ψ⟩Quantum ✅
- `setlist_optimizer.py` (adapts ❤Music data for QAOA) → **should live in ❤Music**, imported from ⟨ψ⟩Quantum
- `supplement_scheduler.py` (adapts ∞Life data for QAOA) → **should live in ∞Life**, imported from ⟨ψ⟩Quantum
- `perf_cli.py` (cross-project utility) → ⊕Workspace ✅

---

## Procedure

### Step 1 — Detect

Scan each project's `src/integrations/`, `src/utils/`, `src/`, and root for files
whose **domain content** belongs to a different project:

```
Signals of misplacement:
- Imports from another project's DB or data files
- File name contains another project's domain terms (setlist, supplement, gig, biomarker)
- Data paths hardcoded to another project's directory
- File was created during a cross-project integration task
```

For each suspect file, determine:
- **Current location:** (which project folder it lives in)
- **Logical owner:** (which project owns the domain)
- **Algorithm dependency:** (which project provides the core engine it calls)

### Step 2 — Assess Impact Before Moving

Before moving anything, answer:

1. **Who imports this file?**
   - Run `grep -r "from <module>" --include="*.py"` across all projects
   - Run `grep -r "import <module>"` across all projects
   - Check test files for direct imports

2. **What does this file import?**
   - Does it use relative imports that will break after move?
   - Does it import from the current project's `core/` or `utils/`?

3. **Are there hardcoded paths?**
   - Scan for `Path(__file__)` chains — these will drift after a move
   - Scan for absolute path strings

4. **Is there a `__init__.py` that re-exports this module?**

Output a move plan:
```
FILE: ⟨ψ⟩Quantum/src/integrations/setlist_optimizer.py
MOVE TO: ❤Music/src/integrations/setlist_optimizer.py
REASON: Adapts ❤Music DB data (heartmusic.db) for QAOA. Domain owner is ❤Music.
IMPORTS FROM ⟨ψ⟩Quantum: core.qaoa (algorithm) — will need updated import path
CURRENT CONSUMERS: ⟨ψ⟩Quantum/tests/test_qaoa_integrations.py
IMPACT: test file must update import path after move
```

### Step 3 — Move

```bash
# Create destination directory if needed
mkdir -p <destination_project>/src/integrations/

# Move file
mv <source_path> <destination_path>
```

**Do NOT move yet if:**
- The file has more than 3 consumers that would need updating and you haven't mapped them all
- The file is actively being run (check for running processes or async terminals)
- The move would break a test suite and you can't update the tests immediately

### Step 4 — Fix Imports in Moved File

After moving, update the moved file's own imports:

- Relative imports from the old `core/` → use full cross-project path or add to PYTHONPATH
- Suggested pattern: import the algorithm module explicitly, document the cross-project dependency

```python
# In ❤Music/src/integrations/setlist_optimizer.py after move:
# Cross-project dependency: requires ⟨ψ⟩Quantum/src on PYTHONPATH
from core.qaoa import QAOAConfig, QAOASolver, maxcut_hamiltonian, evaluate_maxcut
```

Document the dependency in the moved file's module docstring:
```python
"""
❤Music Setlist Optimizer — QAOA integration.

Cross-project dependency: requires ⟨ψ⟩Quantum/src on PYTHONPATH.
Run with: PYTHONPATH=f:/executedcode/⟨ψ⟩Quantum/src python setlist_optimizer.py
"""
```

### Step 5 — Update Consumers

For each consumer identified in Step 2:
- Update import paths to reflect new location
- Update any `PYTHONPATH` instructions or test fixtures
- Update `conftest.py` sys.path if tests depended on old location

### Step 6 — Verify

```bash
# Run tests in the source project (should still pass — logic not changed)
pytest <source_project>/tests/ -v --tb=short

# Run tests in the destination project (new home)
pytest <destination_project>/tests/ -v --tb=short

# Smoke-test the moved module directly
PYTHONPATH=... python <destination_path> --demo
```

### Step 7 — Report

Output a summary:
```
SCOPE CREEP REMEDIATION REPORT
================================
Files moved: N
  - <old_path> → <new_path>

Import updates: N files updated
  - <consumer_file>: updated import X → Y

Tests: N/N passing
Issues remaining: <any outstanding items>
```

---

## Common Misplacements to Watch For

| Pattern | Likely Misplacement | Correct Home |
|---------|--------------------|----|
| `setlist_*.py`, `gig_*.py`, `song_*.py` in non-❤Music project | ❤Music |
| `supplement_*.py`, `biomarker_*.py`, `budget_*.py` in non-∞Life project | ∞Life |
| `quantum_*.py`, `qaoa_*.py`, `circuit_*.py` in non-⟨ψ⟩Quantum project | ⟨ψ⟩Quantum |
| `perf_*.py`, `agent_*.py`, `workspace_*.py` in any single project | ⊕Workspace |
| `heartmusic.db` access in non-❤Music project | Integration, not misplacement — flag for review |
| `infinitelife.db` access in non-∞Life project | Integration, not misplacement — flag for review |

---

## Integration vs Misplacement

Not all cross-project references are misplacements. Use this test:

> **Question:** If the ⟨ψ⟩Quantum project were deleted, would this file still make sense?

- If **yes** → it belongs in another project (misplaced)
- If **no** → it's a true integration and may be correct where it is (flag for review, don't auto-move)
