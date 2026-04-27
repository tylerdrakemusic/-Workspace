"""Create the ⊕ Workspace Portal desktop shortcut with the custom icon.

WScript.Shell has three Unicode bugs we work around:
  1. Shortcut filename  → create with ASCII temp name, then Path.rename()
  2. IconLocation path  → stage ICO to %LOCALAPPDATA%\WorkspacePortal\ (ASCII path)
  3. Arguments path     → stage a PS1 launcher to the same ASCII directory,
                          written with UTF-8 BOM so PowerShell 5.1 reads ⊕ correctly
"""
import ctypes
import os
import shutil
import subprocess
import win32com.client  # type: ignore[import]
from pathlib import Path

workspace  = Path(r"f:\⊕Workspace")
desktop    = Path(os.path.expanduser("~")) / "Desktop"
tmp_lnk    = desktop / "_workspace_portal_tmp.lnk"
final_lnk  = desktop / "\u2295 Workspace Portal.lnk"
src_ico    = workspace / "src" / "data" / "portal_icon.ico"
portal_url = workspace / "reports" / "portal.html"

# ── stage ICO + PS1 to an ASCII path so WScript.Shell doesn't corrupt them ───
staging    = Path(os.environ["LOCALAPPDATA"]) / "WorkspacePortal"
staging.mkdir(parents=True, exist_ok=True)
staged_ico = staging / "portal_icon.ico"
staged_ps1 = staging / "open_portal.ps1"
shutil.copy2(src_ico, staged_ico)
# UTF-8 BOM so PowerShell 5.1 reads the ⊕ in the path correctly
staged_ps1.write_text(f'Start-Process "{portal_url}"\n', encoding="utf-8-sig")

# ── remove stale shortcuts ────────────────────────────────────────────────────
for p in (tmp_lnk, final_lnk):
    if p.exists():
        p.unlink()

# ── create shortcut with ASCII-safe temp name ─────────────────────────────────
powershell = r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
shell = win32com.client.Dispatch("WScript.Shell")
sc = shell.CreateShortcut(str(tmp_lnk))
sc.TargetPath       = powershell
sc.Arguments        = f'-WindowStyle Hidden -NonInteractive -File "{staged_ps1}"'
sc.WindowStyle      = 7
sc.WorkingDirectory = str(workspace / "reports")
sc.IconLocation     = f"{staged_ico},0"
sc.Description      = "\u2295 Workspace Portal \u2014 unified project dashboard"
sc.Save()

# ── rename to Unicode name (Path.rename handles NTFS Unicode correctly) ───────
tmp_lnk.rename(final_lnk)

# ── flush Windows icon cache so new icon appears immediately ──────────────────
ctypes.windll.shell32.SHChangeNotify(0x08000000, 0x0000, None, None)
subprocess.run(["ie4uinit.exe", "-show"], capture_output=True)

print(f"Created : {final_lnk}")
print(f"Exists  : {final_lnk.is_file()}")
