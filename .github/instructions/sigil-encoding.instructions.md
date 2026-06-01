---
description: "Use when encountering encoding issues with workspace sigils (∞ ❤ ⟨ψ⟩ 👁 ⊕), terminal output showing ? or mojibake, file I/O errors on sigil-containing paths, or writing code that handles these characters. Covers UTF-8/16 forms, mojibake recovery, Windows/macOS/Linux console behavior, Python/git/PowerShell quirks."
applyTo: "**"
---

# Sigil Encoding Reference

The workspace uses Unicode sigils as project prefixes. Agents have historically
suffered encoding issues when these characters appear in terminal output, file
paths, git commands, Python source, JSON, HTML, etc. This file is the reference
for recognizing and recovering from those issues.

**Core rule:** always work in UTF-8. Every "sigil issue" traces back to a tool
somewhere on the pipeline assuming cp1252 (Windows), latin1, ASCII, or a legacy
console codepage. Fix the assumption, not the data.

---

## Sigil Quick Reference Table

| Project | Sigil | Name | Codepoint(s) | UTF-8 bytes | UTF-16 | Python escape | JSON escape | HTML entity |
|---|---|---|---|---|---|---|---|---|
| ∞Life | `∞` | INFINITY | U+221E | `E2 88 9E` | `221E` | `\u221e` | `\u221e` | `&infin;` |
| ❤Music | `❤` | HEAVY BLACK HEART | U+2764 | `E2 9D A4` | `2764` | `\u2764` | `\u2764` | `&#10084;` |
| ⟨ψ⟩Quantum | `⟨` `ψ` `⟩` | MATH L-ANGLE · GREEK PSI · MATH R-ANGLE | U+27E8 U+03C8 U+27E9 | `E2 9F A8` + `CF 88` + `E2 9F A9` | `27E8` `03C8` `27E9` | `\u27e8\u03c8\u27e9` | `\u27e8\u03c8\u27e9` | `&#10216;&psi;&#10217;` |
| 👁AI-Manifest | `👁` | EYE | U+1F441 | `F0 9F 91 81` | surrogate pair `D83D DC41` | `\U0001F441` | `\ud83d\udc41` | `&#128065;` |
| ⊕Workspace | `⊕` | CIRCLED PLUS | U+2295 | `E2 8A 95` | `2295` | `\u2295` | `\u2295` | `&oplus;` |
| ΣCapital | `Σ` | GREEK CAPITAL LETTER SIGMA | U+03A3 | `CE A3` | `03A3` | `\u03a3` | `\u03a3` | `&Sigma;` |

**Pitfalls worth memorizing:**

- `⟨ψ⟩` is **3 codepoints**, not 1. `len("⟨ψ⟩") == 3` in Python. Path-length
  assumptions, progress bars, and truncation logic can fail if you assume it's
  one character.
- `👁` is outside the BMP, so in UTF-16 (JavaScript, .NET `char`, Java `char`)
  it's a **surrogate pair**. Naive `string[0]` returns half a character.
  Python 3 strings handle this correctly; JS must use `[...str]` or
  `Array.from(str)` for per-codepoint iteration.
- `❤` on some systems renders as a red emoji (`❤️` with VS16 selector) and on
  others as a monochrome dingbat. Both are `U+2764`. Don't add VS16 — the
  folder name is plain `U+2764`.

---

## Mojibake Cheatsheet (pragmatic — patterns we've actually hit)

When a tool misdecodes UTF-8 bytes as a single-byte encoding (cp1252 or
latin1), each UTF-8 byte becomes a separate character. Recognize these:

| Sigil | UTF-8 bytes | Decoded as cp1252 | Decoded as latin1 |
|---|---|---|---|
| `∞` | `E2 88 9E` | `â\x88\x9e` (often displays as `â^`) | `â^` |
| `❤` | `E2 9D A4` | `â¤` | `â¤` |
| `⟨` | `E2 9F A8` | `â¨` | `â¨` |
| `⟩` | `E2 9F A9` | `â©` | `â©` |
| `ψ` | `CF 88` | `Ï^` | `Ï^` |
| `👁` | `F0 9F 91 81` | `ð\x9f\x91\x81` (often `ð` followed by junk) | same |
| `⊕` | `E2 8A 95` | `â\x8a\x95` | `â^` |
| `Σ` | `CE A3` | `Î£` | `Î£` |

**Reverse lookup heuristics:**

- See `â` at the start of a garbled token? → UTF-8 3-byte sequence starting
  `E2` got misdecoded. One of ∞ ❤ ⟨ ⟩ ⊕ is the intended character.
- See `ð\x9f` or `ðŸ`? → UTF-8 4-byte sequence (`F0 9F ...`) misdecoded.
  Almost certainly `👁` in this workspace.
- See `Ï`? → UTF-8 2-byte sequence (`CF ...`) misdecoded. Likely `ψ` (only
  2-byte sigil-component in the set).
- See `?` placeholders? → **Not mojibake.** Tool replaced unrepresentable
  characters with ASCII `?`. Data is lost; fix the encoding and re-run.
- See boxes `☐` or replacement char `�` (`U+FFFD`)? → Data decoded but font
  lacks the glyph. Bytes are fine; only display is broken.

**Python recovery:**
```python
# If you have mojibake text that was utf-8 misdecoded as cp1252:
garbled = "â¤Music"
recovered = garbled.encode("cp1252").decode("utf-8")  # → "❤Music"
```
This only works if NO characters were lost along the way (i.e. no `?` replacements).

---

## Windows Console Behavior

PowerShell 5.1 and `cmd.exe` default to the legacy OEM codepage (cp437 in US,
cp1252 for output). That is why terminal history shows sigils as `?`.

**Fix for the current session:**
```powershell
chcp 65001                          # set console codepage to UTF-8
$OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::InputEncoding  = [System.Text.Encoding]::UTF8
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"
```

**Permanent fix (PowerShell profile):**
Add the block above to `$PROFILE`. PowerShell 7 defaults to UTF-8 for output
streams and is much better; PowerShell 5.1 needs the manual setup.

**Windows 10 1903+ / 11:** Settings → Time & Language → Language → Administrative
language settings → Change system locale → check **"Beta: Use Unicode UTF-8
for worldwide language support."** This makes ACP = 65001 system-wide. Reboot
required. Fixes nearly every sigil issue in one step, but some legacy apps break.

**VS Code integrated terminal:** already UTF-8 by default. If sigils still
break, the shell profile is overriding it — check settings
`terminal.integrated.defaultProfile.windows` and any profile-level `args`.

---

## macOS & Linux Console Behavior

Terminal.app, iTerm2, and most Linux terminals are UTF-8 by default. Sigil
issues on *nix are rare but come from:

- `LANG` / `LC_ALL` set to `C` or `POSIX` (ASCII-only). Check: `locale`.
  Fix: `export LANG=en_US.UTF-8`.
- SSH sessions from a misconfigured client — `LC_*` env vars inherited from
  the client override the server. Either unset `SendEnv LANG LC_*` client-side
  or set `AcceptEnv` server-side correctly.

**macOS HFS+ / APFS Unicode normalization (REAL GOTCHA):**

macOS filesystems historically store filenames in **NFD** (decomposed form).
Modern APFS is NFC-preserving but not NFD-normalizing. Git on macOS by default
decomposes filenames when you clone, so `❤Music` on Windows (NFC) becomes
the same visually but a different byte sequence.

**When cloning this repo on macOS, set this once:**
```bash
git config --global core.precomposeunicode true
```

This tells git to present filenames as NFC (composed) to match what Windows
and Linux filesystems store. Without it, `git status` will show phantom
changes and `git diff` comparisons may break.

All 5 sigils in this workspace are already composed (single-codepoint or
composed sequences with no combining marks), so NFC == NFD byte-for-byte for
them. But any decorative combining mark (accents, ZWJ emoji) in future
filenames requires this setting.

---

## Git Quirks

**Show unquoted non-ASCII paths in `git status`:**
```bash
git config --global core.quotepath false
```
Without this, `git status` shows `"\342\235\244Music/file.py"` instead of
`❤Music/file.py`. Escapes are correct UTF-8 octal but unreadable.

**Force UTF-8 in git log / diff output:**
```bash
git config --global i18n.logoutputencoding utf-8
git config --global i18n.commitencoding utf-8
```

**Cross-platform normalization (macOS):**
```bash
git config --global core.precomposeunicode true   # see macOS section above
```

**If you see double-encoded paths in `git log`** (`Ã¢Â¤` instead of `â¤`):
the terminal is decoding UTF-8-encoded-as-UTF-8 as cp1252. Fix the console
codepage (Windows) or `LANG` (*nix), not git.

---

## Python, JSON, File I/O

**Always specify `encoding="utf-8"` explicitly.** Python's default on Windows
is `cp1252` (the system ANSI codepage). This is the #1 source of `UnicodeDecodeError`
in this workspace:

```python
# BAD — breaks on Windows if file contains sigils
with open(path) as f:
    data = f.read()

# GOOD
with open(path, encoding="utf-8") as f:
    data = f.read()

# Also GOOD (set once per script)
import sys
sys.stdout.reconfigure(encoding="utf-8")
```

**Environment variable approach (preferred for agents):**
```powershell
$env:PYTHONUTF8 = "1"        # forces UTF-8 for open() defaults + stdio
$env:PYTHONIOENCODING = "utf-8"
```
PEP 540 — `PYTHONUTF8=1` makes Python behave like it does on *nix by default.

**JSON:**
```python
import json
# Preserve sigils as real characters (human-readable files):
json.dump(data, f, ensure_ascii=False, indent=2)

# Portable / safe-over-bad-pipes (everything escaped to \uXXXX):
json.dump(data, f, ensure_ascii=True)
```

**Subprocess output:**
```python
# subprocess inherits the console codepage on Windows — force UTF-8:
subprocess.run([...], capture_output=True, text=True,
               encoding="utf-8", errors="replace")
```
`errors="replace"` substitutes `�` for undecodable bytes instead of raising.
Use `errors="strict"` if you want to hard-fail on encoding errors.

**SQLite:** uses UTF-8 natively; no configuration needed. Sigils in TEXT
columns round-trip correctly.

**CSV:** always open with `encoding="utf-8"` and `newline=""`. Excel on Windows
may need a UTF-8 BOM (`encoding="utf-8-sig"`) to auto-detect encoding when
double-clicking.

---

## Recovery Decision Tree

```
Terminal shows ? where a sigil should be
  └── Console codepage is not UTF-8.
      Windows: chcp 65001; set [Console]::OutputEncoding = UTF8
      *nix: check LANG/LC_ALL, not C/POSIX
      Data is LOST for this session; re-run the command after fix.

Terminal shows â / Ã / ð / Ï junk
  └── UTF-8 bytes being decoded as cp1252 or latin1.
      Fix the CONSUMER, not the producer.
      Python recovery: garbled.encode("cp1252").decode("utf-8")

File read/write raises UnicodeDecodeError / UnicodeEncodeError
  └── Missing encoding= argument on open().
      Always pass encoding="utf-8".

git status shows "\342\235\244"-style escapes
  └── git config --global core.quotepath false

git status shows phantom modifications of sigil-named files on macOS
  └── git config --global core.precomposeunicode true

JSON file looks fine in editor, but API/parser chokes
  └── File may be UTF-8 with BOM. Open with encoding="utf-8-sig" or
      re-save without BOM.

len(sigil_string) returns unexpected number
  └── Remember: ⟨ψ⟩ is 3 codepoints; 👁 is 1 codepoint but 2 UTF-16 code units.
      Use len(s) for codepoints. Use len(s.encode("utf-8")) for bytes.
```

---

## Per-Sigil Pitfalls (concrete)

- **∞ (U+221E)** — safe almost everywhere. Python/JSON/HTML handle fine.
  Watch for: some regex engines treat `∞` as a valid `\w` character and
  some don't; test both.
- **❤ (U+2764)** — appears as monochrome on some renderers, red emoji on
  others. Folder names should NOT include the VS16 emoji selector
  (`U+FE0F`); the workspace uses bare `U+2764`. When typing in tests,
  verify no auto-inserted VS16.
- **⟨ψ⟩ (3 codepoints)** — substring operations and regex character classes
  must handle all three. `"⟨ψ⟩Quantum".startswith("⟨")` is True;
  `...startswith("⟨ψ⟩")` works because Python compares codepoints. But
  fixed-width formatting (`f"{name:20}"`) counts codepoints, not visual
  width; pad manually if aligning columns.
- **👁 (U+1F441, outside BMP)** — breaks in:
  - JavaScript/TS: `"👁".length === 2`; use `[..."👁"].length === 1`.
  - .NET `char` / Java `char`: 16-bit; `char[0]` gets high surrogate only.
    Use `string` or explicit codepoint iteration.
  - Python 2: deprecated. Python 3 handles correctly.
  - Some older fonts lack the glyph → renders as `�` or `☐`. Bytes are fine.
- **⊕ (U+2295)** — safe everywhere. Common in math; won't clash with
  operators in any programming language.
- **Σ (U+03A3)** — single 2-byte UTF-8 codepoint; safe in path names, JSON,
  HTML, Python identifiers, and SQLite TEXT. Visually distinct from Latin
  `E` and Cyrillic `Е` (U+0415); don't confuse the three when typing
  filenames. PowerShell tab-completion handles Σ correctly on UTF-8
  consoles (chcp 65001).

---

## Quick Verification

If you suspect an encoding issue, run this from PowerShell or bash to
verify the console pipeline:

```powershell
# Windows
python -c "print('∞Life ❤Music ⟨ψ⟩Quantum 👁AI-Manifest ⊕Workspace')"
```
```bash
# macOS / Linux
python3 -c "print('∞Life ❤Music ⟨ψ⟩Quantum 👁AI-Manifest ⊕Workspace ΣCapital')"
```

Expected output: all six sigils render correctly. If anything shows as `?`,
mojibake, or raises an error, your environment is misconfigured per the
sections above.

---

**Last updated:** 2026-04-22 (FR-20260422-sigil-encoding-map)
