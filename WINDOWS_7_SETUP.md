# Windows 7 SP1 64-bit Build & Deployment Guide

This document covers the Windows 7-compatible build of **TXT News to Excel
Sync** (TaazaNewsExcelSync), added alongside the existing modern build.
Nothing about the application's TXT → Excel logic, Hindi/Unicode handling,
or UI was changed — only the Python version, dependency pins, and packaging
were adjusted for Windows 7 SP1 64-bit compatibility.

---

## 1. Root cause of the original failure

The original EXE was built with **Python 3.13** (the dev machine's system
Python). Starting with **Python 3.9**, CPython's Windows builds require
Windows 8+ because they link against `api-ms-win-core-*.dll` **API-set
stubs** — a Windows 8+ kernel mechanism that does not exist on Windows 7 in
any form. This is not a "missing file" you can download; it's a hard
minimum-OS requirement baked into python3*.dll and the PyInstaller
bootloader built against it. That is exactly why the target machine reported:

```
api-ms-win-core-path-l1-1-0.dll is missing from your computer
```

**Fix:** rebuild with **Python 3.8.10**, the last CPython release with
official Windows 7 SP1 support.

This was verified directly by inspecting the built binaries' PE import
tables (`pefile`): the Windows-7 build's `TaazaNewsExcelSync.exe` and its
bundled `python38.dll` / Tcl-Tk DLLs reference **zero** `api-ms-win-core-*`
DLLs. They do reference `api-ms-win-crt-*` DLLs (Universal CRT) — a
separate, legitimately-fixable dependency, handled in Section 3.

---

## 2. Versions used

| Component | Version | Why |
|---|---|---|
| Python (Win7 build) | **3.8.10** (64-bit) | Last version with official Windows 7 SP1 support |
| PyInstaller | **5.13.2** | Supports Python 3.8; pinned per plan, verified working |
| watchdog | 4.0.2 | cp38-win_amd64 wheel available, no Win8+ API usage (uses `ReadDirectoryChangesW`, available since Windows 2000) |
| openpyxl | 3.1.5 | Pure Python, no OS dependency |
| customtkinter | 5.2.2 | Pure Python (tkinter-based), no OS dependency |
| darkdetect / packaging | 0.8.0 / 24.1 | customtkinter's own dependencies |

Pinned in [requirements-win7.txt](requirements-win7.txt). The existing
[requirements.txt](requirements.txt) (used with your normal Python 3.13
environment) is **untouched**.

Application code in `app/*.py` and `main.py` was **not modified**. All 81
existing automated tests (`pytest tests/`) pass unchanged when run under
the Python 3.8 `venv-win7` environment.

---

## 3. The Universal CRT (UCRT) prerequisite

Python 3.8 frozen apps still call into the Universal C Runtime
(`ucrtbase.dll`, `api-ms-win-crt-*.dll`). Windows 10+ ships this by default;
Windows 7 SP1 does not.

This is fixed the **officially-supported** way: the installer
(`installer_win7.iss`) silently chain-installs the official
**Microsoft Visual C++ 2015–2022 Redistributable (x64)**
(`vc_redist.x64.exe`, downloaded from Microsoft's own `aka.ms/vs/17/release/vc_redist.x64.exe`)
if it isn't already present (checked via the registry key
`HKLM64\SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\X64`). This is the
same redistributable Microsoft ships for essentially every modern
C++/UCRT-based Windows application — not a random DLL, not a System32 file
copy, and it is Microsoft's documented method for bringing UCRT to
Windows 7/8.

The portable ZIP does **not** auto-install this (there's no installer to
hook into) — see `README_PORTABLE.txt` inside it for the one-time manual
step if needed.

---

## 4. Development computer setup (this machine)

Already done in this session; kept separate from your normal environment:

1. **Python 3.8.10 (64-bit)**, installed privately (not on PATH, doesn't
   affect the default `python` command) to:
   ```
   F:\PyWin7Build\Python38\
   ```
   Installer used (official python.org download):
   ```
   https://www.python.org/ftp/python/3.8.10/python-3.8.10-amd64.exe
   ```
2. **Virtual environment** `venv-win7\` inside `word_to_excel_sync\`, created
   from that Python 3.8.10, with `requirements-win7.txt` installed into it
   (includes PyInstaller 5.13.2 as a build-only dependency).
3. **Inno Setup 6** (`ISCC.exe`) - already installed on this machine at
   `C:\Users\<you>\AppData\Local\Programs\Inno Setup 6\ISCC.exe`, used to
   compile the installer.
4. **`win7_prereqs\vc_redist.x64.exe`** - the official Microsoft
   redistributable, downloaded once and bundled into the installer.

Your existing Python 3.13 install, `requirements.txt`, `venv` (if any),
`TaazaNewsExcelSync.spec`, `dist\`, and `installer.iss` were **not
touched** - they still build the modern (non-Windows-7) version exactly as
before.

> **Note:** during this build, `C:` had 0 bytes free at one point, which
> silently breaks Python/PyInstaller/Inno Setup installers (they all need
> `%TEMP%` scratch space on `C:` even when installing elsewhere). Keep a few
> GB free on `C:` before rebuilding, or redirect `TEMP`/`TMP`/`PIP_CACHE_DIR`
> to another drive first.

### Rebuilding later

```bat
build_win7.bat
```

This recreates `venv-win7`, reinstalls the pinned dependencies, cleans old
build folders, runs PyInstaller, zips the portable build, and compiles the
installer. See the script for the exact steps; it assumes Python 3.8.10 is
still at `F:\PyWin7Build\Python38\python.exe` and Inno Setup is installed.

---

## 5. Target Windows 7 computer

| Question | Answer |
|---|---|
| Is Python required? | **No.** |
| Is PyInstaller required? | **No.** |
| Is a Microsoft runtime/UCRT required? | **Yes** - VC++ 2015-2022 x64 Redistributable. The installer (`TaazaNewsExcelSync_Win7_Setup.exe`) installs it automatically if missing. Portable ZIP users may need to install it manually once (link in `README_PORTABLE.txt`, also `https://aka.ms/vs/17/release/vc_redist.x64.exe`). |
| Is internet required to run the app? | No (only needed once, if using the portable ZIP and the VC++ runtime isn't already on the machine). |
| Where is it installed? | `C:\Users\<user>\AppData\Local\Taaza News Excel Sync\` by default (per-user install, no admin required - `PrivilegesRequired=lowest`). Can be redirected to `C:\Program Files\...` if run elevated. |
| Where does it store data? | `%APPDATA%\TaazaNewsExcelSync\` - `config.json`, `logs\app.log`, `sync.db` (unless you point `txt_root`/`excel_file` elsewhere in the app). |
| How to launch it? | Start Menu → "Taaza News Excel Sync", or the desktop shortcut if that task was selected during install. |
| How to uninstall it? | Start Menu → "Uninstall Taaza News Excel Sync", or Control Panel → Programs and Features. |

### Troubleshooting missing-DLL errors on Windows 7

1. **`api-ms-win-core-*.dll is missing`** - this should not happen with this
   build (verified: zero such references). If it somehow does, you are
   likely running the *old* (Python 3.13) EXE by mistake - confirm you're
   launching the one installed by `TaazaNewsExcelSync_Win7_Setup.exe` or
   from the Windows-7 portable ZIP, not `dist\TaazaNewsExcelSync.exe`
   (that's the modern build).
2. **`api-ms-win-crt-*.dll` / `VCRUNTIME140.dll` / `ucrtbase.dll` missing**
   (portable ZIP only) - install the official Microsoft VC++ 2015-2022 x64
   Redistributable: `https://aka.ms/vs/17/release/vc_redist.x64.exe`, then
   relaunch the app. No restart is normally required.
3. **Windows Update prerequisite** - Windows 7 SP1 with recent-enough
   Windows Update servicing should already have modern root certificates
   etc.; if the VC++ redistributable itself refuses to install, run Windows
   Update first, then retry.
4. Check `logs\app.log` next to where `config.json` lives
   (`%APPDATA%\TaazaNewsExcelSync\logs\app.log`) for application-level errors
   unrelated to missing DLLs.

---

## 6. Test procedure (to run on an actual clean Windows 7 SP1 64-bit machine)

This build has been verified on the development machine: it imports cleanly
under Python 3.8, all 157 unit tests pass, PE import tables for the EXE
and its bundled `python38.dll`/`tcl86t.dll`/`tk86t.dll` contain **zero**
`api-ms-win-core-*` references, and the built EXE was actually launched on
the dev machine, ran its initial scan, detected real file changes, wrote
all four Excel workbooks correctly, and ran a clean background sync loop
(most recently re-verified 2026-08-24 after a substantial app rewrite -
four-feed model, single-instance guard, GUI overhaul - see Section 8 for
what changed). **It has not yet been executed on a real Windows 7 machine**
- that hardware/VM was not available in this environment. Run these before
considering it production-ready:

1. Launch the application (double-click the installed EXE, or run the
   installer first).
2. Open/read a sample `.txt` file (use `demo_data\row_02.txt` etc., or point
   the app's Word/TXT root folder at `demo_data\`).
3. Confirm Hindi (Devanagari) text displays correctly in the GUI activity
   log and in the generated Excel.
4. Trigger a sync (create/edit a `row_XX.txt` file, or click **SYNC NOW**)
   and confirm `All_Content.xlsx` is created/updated.
5. Open `All_Content.xlsx` in Excel (or LibreOffice Calc) and verify:
   - `News Data` sheet: header formatting, Hindi text renders correctly,
     placeholder + news rows as described in `README.md`.
   - `News Category` sheet: full row/category mapping.
6. Restart Windows.
7. Launch the application again - confirm `config.json` / `sync.db` /
   `logs\` persisted under `%APPDATA%\TaazaNewsExcelSync\`.
8. Test automatic sync: with the app running and **START MONITORING**
   active, edit/add/delete a `row_XX.txt` file in the watched folder and
   confirm Excel updates without manually clicking SYNC NOW.
9. Confirm this all works with **no Python installed** on the test machine
   at all (verify via `where python` failing, or simply use a machine that
   never had Python).
10. Confirm **no missing-DLL error** appears at any point (launch, sync,
    Excel write, restart-then-relaunch).

Record pass/fail for each step; report back any failure with the exact
error text and which step it occurred at.

---

## 6b. Troubleshooting: rebuild fails even though Python 3.8.10 is at `F:\PyWin7Build\Python38`

If `F:` (an external/removable drive) is ever disconnected and reconnected,
or if the Python 3.8.10 install there gets reinstalled, Windows Installer's
**per-user product registration** for "Python 3.8.10" can end up corrupted
even after `F:` is back and `venv-win7\Scripts\python.exe --version` works
fine. Symptom: a fresh `python-3.8.10-amd64.exe /quiet ... TargetDir=...`
install reports success (exit code 0), but `python38.dll` never gets copied
to the target directory, and the app fails to launch with
`STATUS_DLL_NOT_FOUND`. This happened once during development (2026-08-24)
after `F:` had been temporarily unavailable and a reinstall was attempted to
`C:\PyWin7Build` in the meantime - not needed once `F:` was reconnected, but
it left Windows Installer's bookkeeping confused about whether "Python
3.8.10" was already installed.

**Fix, if this recurs:** Settings/Control Panel -> Programs and Features ->
uninstall "Python 3.8.10 (64-bit)" (it's safe even if it reports errors
about missing files - that's expected and it still clears the stale
registration), then retry the install. This must be done interactively (not
via an automated script) because the underlying per-user Windows Installer
product keys are ACL-protected in a way that even the same user account
cannot delete without going through Windows Installer's own elevated
uninstall flow.

---

## 7. Known limitations

- **Not yet tested on real Windows 7 hardware/VM** (see Section 6) - only
  verified via binary inspection (`pefile`) and by running the app's own
  Python-level test suite under Python 3.8 on the dev machine. Please run
  the Section 6 checklist on an actual Windows 7 SP1 64-bit machine before
  relying on this for production use.
- The portable ZIP does not auto-install the VC++ Redistributable (only the
  installer does) - a first-run failure on a truly clean Windows 7 machine
  is possible if that prerequisite was never separately installed.
- `MinVersion=6.1sp1` in `installer_win7.iss` blocks the installer from
  running on anything older than Windows 7 SP1 (e.g. Vista, or Windows 7
  without SP1) - this is intentional, not a bug.
- Existing functional limitations from `README.md` (no delete button in the
  row/category mapping editor, no system tray icon) are unchanged - out of
  scope for this Windows 7 compatibility work.

---

## 8. File map (what's new vs. unchanged)

**New (Windows 7 build only):**
- `requirements-win7.txt`
- `installer_win7.iss`
- `build_win7.bat`
- `README_PORTABLE.txt`
- `WINDOWS_7_SETUP.md` (this file)
- `venv-win7\` (build environment, not shipped)
- `win7_prereqs\vc_redist.x64.exe` (bundled into the installer)
- `dist-win7\TaazaNewsExcelSync.exe` (build output)
- `build-win7\` (PyInstaller intermediate work dir, not shipped)
- `installer_output_win7\TaazaNewsExcelSync_Win7_Setup.exe` (final installer)
- `TaazaNewsExcelSync_Portable.zip` (final portable package)

**Unchanged (still your existing modern build):**
- `requirements.txt`, `TaazaNewsExcelSync.spec`, `build_exe.ps1`,
  `installer.iss`, `build_installer.ps1`, `dist\`, `installer_output\`
- All of `app\*.py`, `main.py`, `tests\`, `demo_data\`, `assets\`
