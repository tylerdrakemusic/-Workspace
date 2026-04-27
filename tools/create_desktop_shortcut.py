"""Create the ⊕ Workspace Portal desktop shortcut with the custom icon.

WScript.Shell cannot write Unicode characters in shortcut paths directly.
Workaround: create with an ASCII temp name, then rename via Python (os.rename
handles Unicode filenames correctly on NTFS/Windows).
"""
import os
import win32com.client  # type: ignore[import]
from pathlib import Path

desktop = Path(os.path.expanduser("~")) / "Desktop"
tmp_lnk = desktop / "_workspace_portal_tmp.lnk"
final_lnk = desktop / "\u2295 Workspace Portal.lnk"
workspace = Path(r"f:\⊕Workspace")
ico = workspace / "src" / "data" / "portal_icon.ico"
ps1 = workspace / "open_portal.ps1"

# Remove stale files
for p in (tmp_lnk, final_lnk):
    if p.exists():
        p.unlink()

# Create shortcut with ASCII-safe temp name
shell = win32com.client.Dispatch("WScript.Shell")
sc = shell.CreateShortcut(str(tmp_lnk))
sc.TargetPath = "powershell.exe"
sc.Arguments = f'-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "{ps1}"'
sc.WorkingDirectory = str(workspace)
sc.IconLocation = f"{ico},0"
sc.Description = "\u2295 Workspace Portal \u2014 unified project dashboard"
sc.Save()

# Rename to Unicode name
tmp_lnk.rename(final_lnk)
print(f"Created : {final_lnk}")
print(f"Exists  : {final_lnk.is_file()}")
