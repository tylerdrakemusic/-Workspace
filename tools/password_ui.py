"""
password_ui.py — Web UI for quantum-assisted password generation.

Runs a local Flask server; open http://localhost:7777 in browser.

Usage:
    C:\\G\\python.exe f:\\⊕Workspace\\tools\\password_ui.py
    C:\\G\\python.exe f:\\⊕Workspace\\tools\\password_ui.py --port 7777

SECURITY: No passwords are logged, stored, or transmitted.
          All generation happens in-memory; clipboard copy is client-side.
"""

import argparse
import sys
import string
import secrets
import webbrowser
from pathlib import Path
from threading import Timer

# ---------------------------------------------------------------------------
# Bootstrap: load PasswordGenerator from sibling auto_gen_password.py
# ---------------------------------------------------------------------------

_HERE = Path(__file__).resolve().parent

# Ensure quantum_rt shim is findable (drive root = f:\)
_root = str(_HERE.parents[1])
if _root not in sys.path:
    sys.path.insert(0, _root)

try:
    from auto_gen_password import PasswordGenerator  # type: ignore
except Exception as _e:
    # Inline fallback — mirrors the generator without quantum backend
    class PasswordGenerator:  # type: ignore[no-redef]
        def __init__(self, length=13, use_special_chars=False, use_numbers=True,
                     language="en", salt=None):
            self.length = length
            self.use_special_chars = use_special_chars
            self.use_numbers = use_numbers
            self.language = language
            self.salt = salt

        def _get_character_set(self):
            chars = string.ascii_letters
            if self.use_special_chars:
                chars += string.punctuation
            if self.use_numbers:
                chars += string.digits
            return chars

        def generate(self):
            chars = self._get_character_set()
            return "".join(secrets.choice(chars) for _ in range(self.length))

# ---------------------------------------------------------------------------
# Flask app
# ---------------------------------------------------------------------------

try:
    from flask import Flask, request, jsonify
except ImportError:
    sys.exit("Flask not installed. Run: C:\\G\\python.exe -m pip install flask")

app = Flask(__name__)

# ---------------------------------------------------------------------------
# HTML template (single-page, dark themed, no external dependencies)
# ---------------------------------------------------------------------------

HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>🔑 Password Generator</title>
<style>
  :root {
    --bg:       #0a0d12;
    --surface:  #111620;
    --border:   #1e2530;
    --accent:   #6366f1;
    --accent2:  #818cf8;
    --text:     #e2e8f0;
    --muted:    #64748b;
    --success:  #10b981;
    --warn:     #f59e0b;
    --danger:   #ef4444;
    --radius:   10px;
  }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    background: var(--bg);
    color: var(--text);
    font-family: 'Segoe UI', system-ui, sans-serif;
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 2rem 1rem;
  }
  .card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 2rem;
    width: 100%;
    max-width: 480px;
    box-shadow: 0 8px 32px rgba(0,0,0,0.4);
  }
  h1 {
    font-size: 1.3rem;
    font-weight: 700;
    margin-bottom: 0.25rem;
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }
  .subtitle {
    color: var(--muted);
    font-size: 0.78rem;
    margin-bottom: 1.6rem;
  }

  /* Service label */
  .field { margin-bottom: 1.1rem; }
  label {
    display: block;
    font-size: 0.78rem;
    font-weight: 600;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 0.4rem;
  }
  input[type=text] {
    width: 100%;
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 0.55rem 0.75rem;
    color: var(--text);
    font-size: 0.9rem;
    outline: none;
    transition: border-color 0.15s;
  }
  input[type=text]:focus { border-color: var(--accent); }
  input[type=text]::placeholder { color: var(--muted); }

  /* Length slider */
  .slider-row {
    display: flex;
    align-items: center;
    gap: 0.75rem;
  }
  input[type=range] {
    flex: 1;
    -webkit-appearance: none;
    height: 4px;
    background: var(--border);
    border-radius: 2px;
    outline: none;
    cursor: pointer;
  }
  input[type=range]::-webkit-slider-thumb {
    -webkit-appearance: none;
    width: 16px;
    height: 16px;
    border-radius: 50%;
    background: var(--accent);
    cursor: pointer;
    box-shadow: 0 0 6px rgba(99,102,241,0.5);
  }
  .len-badge {
    background: var(--accent);
    color: #fff;
    font-size: 0.82rem;
    font-weight: 700;
    border-radius: 6px;
    padding: 0.2rem 0.5rem;
    min-width: 2.2rem;
    text-align: center;
  }

  /* Toggles */
  .toggles {
    display: flex;
    gap: 0.5rem;
    flex-wrap: wrap;
    margin-bottom: 1.3rem;
  }
  .toggle-btn {
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 20px;
    padding: 0.3rem 0.85rem;
    font-size: 0.82rem;
    color: var(--muted);
    cursor: pointer;
    transition: all 0.15s;
    user-select: none;
  }
  .toggle-btn.on {
    background: rgba(99,102,241,0.15);
    border-color: var(--accent);
    color: var(--accent2);
  }

  /* Output box */
  .output-wrap {
    position: relative;
    margin-bottom: 1rem;
  }
  #pwd-display {
    width: 100%;
    background: var(--bg);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 0.7rem 2.8rem 0.7rem 0.85rem;
    color: #a5f3fc;
    font-family: 'Cascadia Code', 'Consolas', 'Courier New', monospace;
    font-size: 1.05rem;
    letter-spacing: 0.06em;
    word-break: break-all;
    min-height: 2.6rem;
  }
  #copy-btn {
    position: absolute;
    right: 0.5rem;
    top: 50%;
    transform: translateY(-50%);
    background: none;
    border: none;
    cursor: pointer;
    color: var(--muted);
    font-size: 1rem;
    padding: 0.2rem;
    transition: color 0.15s;
  }
  #copy-btn:hover { color: var(--accent2); }
  #copy-feedback {
    font-size: 0.72rem;
    color: var(--success);
    height: 0.9rem;
    margin-bottom: 0.6rem;
    padding-left: 2px;
    transition: opacity 0.3s;
  }

  /* Strength bar */
  .strength-row {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin-bottom: 1.3rem;
  }
  .strength-bar-bg {
    flex: 1;
    height: 4px;
    background: var(--border);
    border-radius: 2px;
    overflow: hidden;
  }
  .strength-bar-fill {
    height: 100%;
    width: 0%;
    border-radius: 2px;
    transition: width 0.3s, background 0.3s;
  }
  .strength-label {
    font-size: 0.72rem;
    color: var(--muted);
    min-width: 4.5rem;
    text-align: right;
  }

  /* Generate button */
  #gen-btn {
    width: 100%;
    background: var(--accent);
    color: #fff;
    border: none;
    border-radius: 8px;
    padding: 0.75rem;
    font-size: 0.95rem;
    font-weight: 700;
    cursor: pointer;
    transition: background 0.15s, transform 0.1s;
    letter-spacing: 0.02em;
  }
  #gen-btn:hover { background: var(--accent2); }
  #gen-btn:active { transform: scale(0.98); }
  #gen-btn:disabled { opacity: 0.5; cursor: not-allowed; }

  /* Salt section (collapsed by default) */
  .advanced-toggle {
    font-size: 0.75rem;
    color: var(--muted);
    cursor: pointer;
    margin-top: 1rem;
    display: inline-flex;
    align-items: center;
    gap: 0.3rem;
    user-select: none;
  }
  .advanced-toggle:hover { color: var(--text); }
  #advanced-section { display: none; margin-top: 0.75rem; }
  #advanced-section.open { display: block; }
</style>
</head>
<body>
<div class="card">
  <h1>🔑 Password Generator</h1>
  <p class="subtitle">Quantum-assisted · stateless · no storage</p>

  <div class="field">
    <label for="service">Service / Label</label>
    <input type="text" id="service" placeholder="e.g. GitHub, ProtonMail, Netlify…"
           autocomplete="off" spellcheck="false">
  </div>

  <div class="field">
    <label>Length — <span id="len-val">16</span> chars</label>
    <div class="slider-row">
      <input type="range" id="len-slider" min="8" max="64" value="16"
             oninput="updateLength(this.value)">
      <span class="len-badge" id="len-badge">16</span>
    </div>
  </div>

  <div class="field">
    <label>Options</label>
    <div class="toggles">
      <span class="toggle-btn on" id="tog-numbers"    onclick="toggle(this)">Numbers</span>
      <span class="toggle-btn"   id="tog-special"     onclick="toggle(this)">Symbols</span>
    </div>
  </div>

  <div class="output-wrap">
    <div id="pwd-display">—</div>
    <button id="copy-btn" title="Copy to clipboard" onclick="copyPwd()">⧉</button>
  </div>
  <div id="copy-feedback"></div>

  <div class="strength-row">
    <div class="strength-bar-bg">
      <div class="strength-bar-fill" id="strength-fill"></div>
    </div>
    <span class="strength-label" id="strength-label">—</span>
  </div>

  <button id="gen-btn" onclick="generate()">Generate Password</button>

  <span class="advanced-toggle" onclick="toggleAdvanced()">
    <span id="adv-arrow">▶</span> Advanced (salt)
  </span>
  <div id="advanced-section">
    <div class="field" style="margin-top:0">
      <label for="salt-input">Salt (interleaved into password)</label>
      <input type="text" id="salt-input" placeholder="Optional salt string"
             autocomplete="off" spellcheck="false">
    </div>
  </div>
</div>

<script>
let currentPwd = '';

function updateLength(v) {
  document.getElementById('len-val').textContent = v;
  document.getElementById('len-badge').textContent = v;
}

function toggle(el) {
  el.classList.toggle('on');
}

function toggleAdvanced() {
  const sec = document.getElementById('advanced-section');
  const arrow = document.getElementById('adv-arrow');
  sec.classList.toggle('open');
  arrow.textContent = sec.classList.contains('open') ? '▼' : '▶';
}

function strengthInfo(pwd) {
  if (!pwd || pwd === '—') return { pct: 0, label: '—', color: '#64748b' };
  const len = pwd.length;
  const hasLower = /[a-z]/.test(pwd);
  const hasUpper = /[A-Z]/.test(pwd);
  const hasNum   = /[0-9]/.test(pwd);
  const hasSym   = /[^a-zA-Z0-9]/.test(pwd);
  const pools = [hasLower, hasUpper, hasNum, hasSym].filter(Boolean).length;
  // entropy bits ≈ log2(pool^length)
  const poolSize = (hasLower?26:0)+(hasUpper?26:0)+(hasNum?10:0)+(hasSym?32:0);
  const bits = poolSize > 0 ? len * Math.log2(poolSize) : 0;
  if (bits < 40)  return { pct: 15,  label: 'Weak',        color: '#ef4444' };
  if (bits < 60)  return { pct: 35,  label: 'Fair',        color: '#f59e0b' };
  if (bits < 80)  return { pct: 60,  label: 'Good',        color: '#eab308' };
  if (bits < 110) return { pct: 80,  label: 'Strong',      color: '#10b981' };
  return             { pct: 100, label: 'Very strong',  color: '#6366f1' };
}

function renderStrength(pwd) {
  const { pct, label, color } = strengthInfo(pwd);
  document.getElementById('strength-fill').style.width = pct + '%';
  document.getElementById('strength-fill').style.background = color;
  document.getElementById('strength-label').style.color = color;
  document.getElementById('strength-label').textContent = label;
}

async function generate() {
  const btn = document.getElementById('gen-btn');
  btn.disabled = true;
  btn.textContent = 'Generating…';
  const display = document.getElementById('pwd-display');

  const length  = parseInt(document.getElementById('len-slider').value);
  const numbers = document.getElementById('tog-numbers').classList.contains('on');
  const special = document.getElementById('tog-special').classList.contains('on');
  const salt    = document.getElementById('salt-input').value.trim() || null;

  try {
    const res = await fetch('/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ length, numbers, special, salt })
    });
    const data = await res.json();
    if (data.error) {
      display.textContent = '⚠ ' + data.error;
      currentPwd = '';
    } else {
      currentPwd = data.password;
      display.textContent = currentPwd;
      renderStrength(currentPwd);
    }
  } catch (e) {
    display.textContent = '⚠ Could not reach generator';
    currentPwd = '';
  } finally {
    btn.disabled = false;
    btn.textContent = 'Generate Password';
  }
}

function copyPwd() {
  if (!currentPwd) return;
  navigator.clipboard.writeText(currentPwd).then(() => {
    const fb = document.getElementById('copy-feedback');
    fb.textContent = '✓ Copied to clipboard';
    setTimeout(() => { fb.textContent = ''; }, 2000);
  });
}

// Generate one on load
window.addEventListener('DOMContentLoaded', generate);
</script>
</body>
</html>
"""

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    from flask import Response
    return Response(HTML, mimetype="text/html")


@app.route("/generate", methods=["POST"])
def generate():
    data = request.get_json(silent=True) or {}
    length  = max(8, min(int(data.get("length", 16)), 128))
    numbers = bool(data.get("numbers", True))
    special = bool(data.get("special", False))
    salt    = data.get("salt") or None

    # Validate salt (ASCII printable only)
    if salt:
        allowed = string.ascii_letters + string.digits + string.punctuation
        if not all(c in allowed for c in salt):
            return jsonify({"error": "Salt must contain only ASCII letters, digits, or punctuation."}), 400

    try:
        gen = PasswordGenerator(
            length=length,
            use_special_chars=special,
            use_numbers=numbers,
            language="en",
            salt=salt,
        )
        pwd = gen.generate()
        return jsonify({"password": pwd})
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Password Generator UI")
    parser.add_argument("--port", type=int, default=7777)
    parser.add_argument("--no-open", action="store_true", help="Don't auto-open browser")
    args = parser.parse_args()

    url = f"http://localhost:{args.port}"
    if not args.no_open:
        Timer(0.8, lambda: webbrowser.open(url)).start()

    print(f"  Password Generator → {url}")
    print("  Press Ctrl+C to stop.\n")
    app.run(host="127.0.0.1", port=args.port, debug=False)


if __name__ == "__main__":
    main()
