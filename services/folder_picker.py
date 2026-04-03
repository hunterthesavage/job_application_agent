from __future__ import annotations

import os
import subprocess
from pathlib import Path


def pick_folder_dialog(initial_path: str, *, title: str = "Select Folder") -> tuple[str, str | None]:
    start_path = str(Path(initial_path).expanduser()) if initial_path else str(Path.home())

    if os.name == "nt":
        try:
            import tkinter as tk
            from tkinter import filedialog

            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            selected = filedialog.askdirectory(
                initialdir=start_path,
                title=title,
                mustexist=False,
            )
            root.destroy()
            if selected:
                return selected, None
            return initial_path, None
        except Exception as exc:
            return initial_path, str(exc)

    script = f'''
set startFolder to POSIX file "{start_path}" as alias
try
    set chosenFolder to choose folder with prompt "{title}" default location startFolder
on error
    set chosenFolder to choose folder with prompt "{title}"
end try
POSIX path of chosenFolder
'''.strip()

    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode == 0:
            selected = result.stdout.strip()
            if selected:
                return selected, None

        stderr_text = (result.stderr or "").strip()
        if stderr_text and "User canceled" not in stderr_text:
            return initial_path, stderr_text
    except Exception as exc:
        return initial_path, str(exc)

    return initial_path, None
