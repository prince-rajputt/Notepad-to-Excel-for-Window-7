# Taaza News Excel Sync

A Windows desktop application that keeps the on-air graphics workbooks of
**Taaza TV** in step with the news written in Windows Notepad.

Editors type Hindi (and mixed Hindi/English) news lines into four `.txt`
files. The playout software (WASP3D) reads its tickers, bands and lower thirds
from Excel workbooks. This app watches those four `.txt` files and rebuilds
four Excel workbooks from them within seconds of every save, in the exact
file names, sheet names, columns, fonts and formats the playout software
expects.

```
Desktop\notepad\                   Desktop\Excel taza tv\
├── row_01.txt   ──────────────>   ├── TopNewsLT.xlsx            (Top News)
├── row_10.txt   ──────────────>   ├── Upper Band.xlsx           (Upper Band)
├── row_04.txt   ──────────────>   ├── Breaking LT.xlsx          (Breaking News)
├── row_09.txt   ──────────────>   └── Breaking FF + Top.xlsx    (Full Screen Breaking)
│
├── row_02.txt   (ignored)         (every other .xlsx in the folder
├── row_03.txt   (ignored)          is left completely untouched)
└── ...          (ignored)
```

> **Key design rule:** the app only ever reads the four configured `.txt`
> names, directly inside the TXT folder, and only ever writes the four
> configured workbook names inside the Excel folder. Every other file and
> every subfolder is invisible to it.

---

## Contents

1. [Features](#1-features)
2. [Quick start (operators)](#2-quick-start-operators)
3. [The four feeds](#3-the-four-feeds)
4. [Excel output formats](#4-excel-output-formats)
5. [How `.txt` content is processed](#5-how-txt-content-is-processed)
6. [Using the application](#6-using-the-application)
7. [Configuration reference](#7-configuration-reference)
8. [How syncing works](#8-how-syncing-works)
9. [Architecture](#9-architecture)
10. [Developer guide](#10-developer-guide)
11. [Building and deployment](#11-building-and-deployment)
12. [Troubleshooting](#12-troubleshooting)
13. [Known issues and limitations](#13-known-issues-and-limitations)
14. [Running alongside the older app](#14-running-alongside-the-older-app)
15. [Project structure](#15-project-structure)
16. [Change history](#16-change-history)

---

## 1. Features

- **Real-time watching** of the TXT folder with `watchdog`. Create, edit,
  delete and rename events are handled, debounced so one save is processed
  once.
- **Live-mirror workbooks.** Each workbook is fully rebuilt from its `.txt`
  file on every sync, so deleted lines disappear and nothing stale lingers.
- **Hindi-safe reading.** An encoding fallback chain (UTF-8 with/without BOM,
  UTF-16 with/without BOM, Windows-1252, latin-1) means Devanagari text is
  never corrupted, whichever way Notepad saved the file.
- **`<BITMAP>` placeholder removal.** Image-path tags such as
  `<BITMAP>v:\newsair\logo.psd</BITMAP>` are stripped (case-insensitive); a
  line that was only a tag is dropped.
- **No rewording.** Every remaining line is kept exactly as written, in order,
  with no translation and no summarisation.
- **Exact playout layouts.** Headers, yellow fills, fonts, column widths, time
  formats, freeze panes and filters are reproduced so WASP3D picks the data up
  unchanged.
- **Safe writes.** Each workbook is written to a temporary file first and then
  swapped in, so a half-written `.xlsx` never appears. If the workbook is open
  in Excel, the app keeps retrying until it is closed.
- **Self-healing.** A full reconciliation runs at startup, on demand, after any
  settings change and every 10 seconds in the background, so a missed
  filesystem event is corrected automatically.
- **Unattended 24/7 operation.** Monitoring starts on launch, the app can start
  with Windows, the on-screen log clears itself every 2 hours, and the log file
  rotates.
- **Single instance.** A second copy refuses to start, because two copies would
  overwrite each other's workbooks.
- **Windows 7 to 11.** There are separate builds for Windows 10/11 and
  Windows 7 SP1 64-bit.

---

## 2. Quick start (operators)

1. **Install.** Run the installer:
   - Windows 10/11: `installer_output\TXT_News_Excel_Sync_Setup.exe`
   - Windows 7 SP1 64-bit: `installer_output_win7\TaazaNewsExcelSync_Win7_Setup.exe`
     (it installs the Microsoft VC++ runtime automatically if needed)

   Or unzip `TaazaNewsExcelSync_Portable.zip` and run
   `TaazaNewsExcelSync.exe`. No Python is needed on the target PC.
2. **Launch** *Taaza News Excel Sync* from the Start menu or the desktop
   shortcut. Monitoring starts immediately.
3. **Check the folders** at the top of the window:
   - **TXT Folder**: where `row_01.txt`, `row_04.txt`, `row_09.txt` and
     `row_10.txt` live.
   - **Excel Folder**: where the four workbooks should be written.

   Use **Browse** to change either one. The app re-syncs straight away.
4. **Confirm** that the status shows **● RUNNING** and that all four feeds show
   **✓ Synced** in the list.
5. *(Optional)* Tick **Start automatically with Windows**. This works for the
   installed `.exe` only.

From then on, editors just save their `.txt` files in Notepad, and the
workbooks update about 2–4 seconds later.

---

## 3. The four feeds

| Feed | Source `.txt` | Destination workbook | Sheet(s) | Columns |
|---|---|---|---|---|
| Top News | `row_01.txt` | `TopNewsLT.xlsx` | `TopNews` | Status, News |
| Upper Band | `row_10.txt` | `Upper Band.xlsx` | `Breaking News FF` | Visibility, News |
| Breaking News | `row_04.txt` | `Breaking LT.xlsx` | `Breaking LT News` + `Breaking LT Category` | Visibility, Category, News |
| Full Screen Breaking | `row_09.txt` | `Breaking FF + Top.xlsx` | `Breaking News FF` | Visibility, News |

- **File names** (source and destination) can be changed at runtime under
  **FEED MAPPING**, which is password-protected.
- **Sheet names and column layouts** are fixed in code (`app/feeds.py`,
  `app/excel_manager.py`) because the playout software matches on them.

### Automatic defaults

The `.txt` files carry only the news text, so these columns are filled in by
the app:

| Field | Default | Rule | Configurable in |
|---|---|---|---|
| Visibility / Status | `1` | Every row is visible (`0` would hide it) | FEED MAPPING → *Default Visibility* |
| Category (Breaking LT), first lines | `08:00:00 PM` | Applies to the first **2** news lines | FEED MAPPING → *First N news lines use Category* |
| Category (Breaking LT), other lines | `09:00:00 PM` | Line 3 onward, including every line added later | FEED MAPPING → *Default Category* |

Adding a new line never shifts the 8 PM block. Set *First N* to `0` to give
every line the default time.

---

## 4. Excel output formats

All three layouts were reverse-engineered from the workbooks the playout
software already reads. **Do not "tidy" them**, because the playout system
matches on these exact headers and sheet names.

### 4.1 `TopNewsLT.xlsx`, sheet `TopNews`

| A | B |
|---|---|
| Status | News |

| Property | Value |
|---|---|
| Header | **Bold**, bright yellow fill (`FFFF00`), centred horizontally and vertically |
| Body font | `Nirmala UI` 11, for correct Hindi rendering; vertical align top |
| Column widths | A = 13, B = 100 |
| Freeze panes | `A2` (header row stays visible) |
| AutoFilter | `A1:B<last row>` |

```
Status | News
1      | कोलकाता के जोड़ाबगान में पुराना मकान गिरा
1      | हादसे में एक की मौत, कई घायल, राहत कार्य जारी
1      | रांची: छात्रों का अनशन खत्म, सरकार ने मानी मांगें
```

### 4.2 `Upper Band.xlsx` and `Breaking FF + Top.xlsx`, sheet `Breaking News FF`

| A | B |
|---|---|
| Visibility | News |

| Property | Value |
|---|---|
| Header | Yellow fill, **not** bold |
| Body font | `Arial` 10 |
| Column widths | B = 68.71 |
| Freeze / filter | None |

```
Visibility | News
1          | विदेश मंत्री एस जयशंकर 23-24 अगस्त को करेंगे रूस का दौरा
1          | झारखंड के रामगढ़ में फैक्ट्री के कंट्रोल रूम में लगी आग
```

### 4.3 `Breaking LT.xlsx`, two sheets in one workbook

**Sheet `Breaking LT News`**

| A | B | C |
|---|---|---|
| Visibility | Category | News |

| Property | Value |
|---|---|
| Header | Yellow fill, not bold |
| Body font | `Arial` 10 |
| Category column | A real Excel **time** value, number format `hh:mm:ss AM/PM` |
| Column widths | B = 20.43, C = 57 |

```
Visibility | Category     | News
1          | 08:00:00 PM  | देश के नाम राष्ट्रपति का सम्बोधन
1          | 08:00:00 PM  | भारत को सर्वश्रेष्ठ बनाने का काम करें-राष्ट्रपति
1          | 09:00:00 PM  | आतंक कहीं भी हो जमींदोज होगा-राष्ट्रपति
1          | 09:00:00 PM  | हम आधुनिक भारत के निर्माण की ओर अग्रसर:राष्ट्रपति
```

**Sheet `Breaking LT Category`**

| A | B |
|---|---|
| Visibility | Category |

This sheet lists each distinct Category time used on the News sheet, once, in
the order it first appears. The list is derived from the data, never
hard-coded. Column B width = 23.57.

```
Visibility | Category
1          | 08:00:00 PM
1          | 09:00:00 PM
```

---

## 5. How `.txt` content is processed

The pipeline lives in `app/txt_reader.py`.

### 5.1 Decoding

The raw bytes are decoded with the first encoding that works:

1. UTF-8 **with BOM** (Notepad "UTF-8 with BOM")
2. UTF-16 **with BOM** (Notepad "Unicode")
3. UTF-8 without BOM (Notepad "UTF-8", the modern default)
4. UTF-16 **without BOM**, only if the bytes look like UTF-16 (many null
   bytes). This guard stops garbage "successful" decodes.
5. Windows-1252 (Notepad "ANSI")
6. latin-1, as a last resort that never fails

### 5.2 Cleaning: `clean_and_extract_hindi_lines(text)`

1. Remove every `<BITMAP>...</BITMAP>` section (case-insensitive, may span
   lines) from the whole text **first**, so tag content can never leak into the
   output.
2. Split what remains into its original lines.
3. Collapse runs of spaces/tabs left behind and trim each line.
4. Drop lines that are now empty, such as a line that was only a BITMAP tag.
5. Keep the original order. Each remaining line becomes one Excel row.

| Input line | Output row |
|---|---|
| `आज बड़ी खबर है <BITMAP>v:\newsair\logo.psd</BITMAP>` | `आज बड़ी खबर है` |
| `भारत ने India को हराया <BITMAP>...</BITMAP>` | `भारत ने India को हराया` (mixed line kept whole) |
| `A major fire occurred near the temple.` | kept (English lines are kept too) |
| `<BITMAP>:\newsair\logo.psd</BITMAP>` | *(dropped)* |
| *(blank line)* | *(dropped)* |

---

## 6. Using the application

### 6.1 Main window

| Area | What it does |
|---|---|
| **Title bar / ☀ 🌙 button** | Switches between day and night (black) theme. The choice is remembered in `config.json` (`dark_mode`). |
| **TXT Folder + Browse** | The folder containing the source `.txt` files. Changing it re-scans immediately and re-points the watcher. |
| **Excel Folder + Browse** | Where the workbooks are written. Changing it rebuilds all four workbooks there. |
| **Start automatically with Windows** | Adds or removes a `HKCU\...\Run\TaazaNewsExcelSync` registry value pointing at the installed `.exe`. It has no effect when running from source. |
| **Status line** | **● RUNNING** (green) or **● STOPPED** (red), plus the time of the last sync. |
| **Statistics** | *Feeds Synced*, *Total News Items* (rows across all workbooks), and *Excel Pending* (`yes` while a workbook is locked and waiting to be written). |
| **Feed list** | One row per feed: Feed, TXT File, Excel File, News Lines, Modified At, Status. Status is **✓ Synced** or **🔒 Excel open - pending**. *Modified At* shows **file not found** when the `.txt` file is missing. |
| **Search** | Filters the feed list. |
| **Activity log** | Timestamped events: files detected, lines added or removed, BITMAP tags removed, workbooks written, errors. It clears itself every 2 hours. The full history is in `logs\app.log`. |

### 6.2 Buttons

| Button | Action |
|---|---|
| **START MONITORING** | Starts the folder watcher and runs a full reconciliation. This happens automatically on launch. |
| **STOP MONITORING** | Pauses the watcher. Workbooks stop updating until it is started again. |
| **SYNC NOW** | Re-reads all four `.txt` files and rebuilds every workbook immediately. |
| **OPEN EXCEL FOLDER** | Opens the Excel folder in Explorer. |
| **OPEN TXT FOLDER** | Opens the TXT folder in Explorer. |
| **FEED MAPPING** | Opens the password-protected mapping editor (see below). |

### 6.3 Feed Mapping editor

Protected by a password (default **`2001`**, stored as `mapping_password` in
`config.json`).

For each of the four feeds you can edit:

- **TXT:** the source file name, for example `row_01.txt`
- **Excel:** the destination workbook name, for example `TopNewsLT.xlsx`

The sheet name is shown in grey for reference but cannot be edited.

Global defaults:

- **Default Visibility**, a whole number (usually `1`)
- **Default Category (Breaking LT)**, such as `09:00:00 PM`
- **First N news lines use Category**, such as `2` lines at `08:00:00 PM`

Time values accept `09:00:00 PM`, `09:00 PM`, `21:00:00` or `21:00`, and are
normalised to `hh:mm:ss AM/PM`. Click **Save Mapping**: settings are written to
`config.json` and all workbooks are rebuilt in the background.

---

## 7. Configuration reference

### 7.1 Where settings live

| Run mode | `config.json`, `sync.db`, `logs\` location |
|---|---|
| Installed / portable `.exe` | `%APPDATA%\TaazaNewsExcelSync\` |
| From source (`python main.py`) | Next to `main.py` |

The file is created with defaults on first launch. It is read as `utf-8-sig`,
so a BOM added by Notepad or PowerShell is fine. If it cannot be parsed, the
app warns loudly in a dialog and in the log, because the defaults would point
at different folders.

### 7.2 Keys

| Key | Default | Meaning |
|---|---|---|
| `txt_root` | `%USERPROFILE%\Documents\notepad` | Folder containing the source `.txt` files |
| `excel_root` | `%USERPROFILE%\Desktop\Excel taza tv` | Folder the workbooks are written to |
| `database_file` | `""` | SQLite cache path. Empty means `sync.db` next to `config.json` |
| `watch_extensions` | `[".txt"]` | Extensions the watcher considers |
| `auto_start` | `false` | Start-with-Windows checkbox state |
| `mapping_password` | `"2001"` | Feed Mapping password, stored in plain text |
| `dark_mode` | `false` | Night theme |
| `default_visibility` | `1` | Value written to Visibility/Status |
| `default_category_time` | `"09:00:00 PM"` | Breaking LT category after the first N lines |
| `first_category_time` | `"08:00:00 PM"` | Breaking LT category for the first N lines |
| `first_category_count` | `2` | N. `0` disables the split |
| `feeds` | *(four entries)* | See below |

Each `feeds[]` entry:

```json
{
    "key": "top_news",
    "label": "Top News",
    "txt_file": "row_01.txt",
    "excel_file": "TopNewsLT.xlsx",
    "excel_format": "status_news",
    "sheet_name": "TopNews"
}
```

- `excel_format` is one of `status_news`, `visibility_news` or `breaking_lt`.
- `breaking_lt` entries also carry `category_sheet_name`.
- Malformed entries are skipped. If none are valid, the four built-in defaults
  are used.

### 7.3 Automatic upgrade of old names

When the playout software changes a name it matches on, settings saved by an
older version are upgraded as they load (`LEGACY_FEED_VALUES` in
`app/feeds.py`):

| Feed | Field | Old value | New value |
|---|---|---|---|
| `top_news` | `excel_file` | `Top News LT.xlsx` | `TopNewsLT.xlsx` |
| `top_news` | `sheet_name` | `Top News LT` | `TopNews` |

Only those exact old values are replaced. A name you typed yourself under FEED
MAPPING is never touched.

> **After an upgrade** the old workbook (for example `Top News LT.xlsx`) is
> **not deleted**. It stays in the Excel folder but stops updating. Remove it
> by hand once the new file has appeared.

---

## 8. How syncing works

### 8.1 Events

| Event | Behaviour |
|---|---|
| **New file** appears | Waits until the file size is stable (5 checks, 0.5 s apart, up to 15 s), then reads, cleans and writes the feed's workbook |
| **File modified** | Re-read. The database record is updated in place and the workbook rebuilt, so there are never duplicate rows. The activity log shows which lines were added or removed |
| **File deleted** | The record is removed and the workbook is rewritten with **headers only**. The other three feeds are untouched |
| **File renamed** | Treated as a delete of the old name plus a create of the new name, if the new name is a feed |
| **Rapid repeated events** from one save | Coalesced within **1.5 s**, so the file is processed once |
| **Any non-feed file** | Ignored at both the watcher level and the scan level |

### 8.2 Reconciliation

Filesystem events alone are never trusted as the only source of truth. A full
reconciliation reads each of the four files, compares it with the database
(size and mtime first, then SHA-256) and rewrites every workbook. It runs:

- at **startup**, to catch changes made while the app was closed
- on **SYNC NOW**
- after **Browse** (either folder), **START MONITORING** and **Save Mapping**
- automatically **every 10 seconds** in the background, as a safety net.
  This silent scan rewrites all four workbooks each time, even when nothing
  changed. That is how a workbook that was locked catches up. It also means
  each file's modified time changes about every 10 seconds.

### 8.3 Locked workbooks

If a workbook is open in Excel (or being read by another program), Windows
refuses the write. The app:

1. retries 3 times with back-off (1 s, then 2 s),
2. then marks the feed **pending** (*Excel Pending: yes*), and
3. retries about every 2 seconds until the file is free. Close the workbook in
   Excel and it updates by itself.

A half-written workbook never appears: data goes to a hidden `.~tmp_*.xlsx`
file in the same folder and is swapped in with an atomic replace.

### 8.4 Single instance

A named mutex (`Local\TaazaNewsExcelSync_SingleInstance`) lets only one copy
run per user session. A second launch shows *"already running"* and exits. The
mutex is released automatically if the app crashes.

---

## 9. Architecture

```
            ┌──────────────┐   events    ┌──────────────┐
 .txt  ───► │ watcher.py   │ ──────────► │              │
 files      │ (watchdog,   │  debounced  │ sync_engine  │ ◄── GUI buttons /
            │  1.5 s)      │             │  .py         │     10 s safety scan
            └──────────────┘             │              │
                                         └──┬────┬────┬─┘
                     ┌──────────────────────┘    │    └────────────────────┐
                     ▼                           ▼                         ▼
            ┌──────────────┐            ┌──────────────┐          ┌──────────────┐
            │ txt_reader   │            │ database.py  │          │ excel_manager│
            │ decode +     │            │ SQLite cache │          │ build + atomic│ ──► .xlsx
            │ BITMAP strip │            │ (sync.db)    │          │ write, retry │
            └──────────────┘            └──────────────┘          └──────────────┘
```

### 9.1 Modules

| Module | Responsibility |
|---|---|
| `main.py` | Entry point: chooses the settings folder, sets up logging, single-instance guard, loads config, starts the GUI |
| `app/gui.py` | CustomTkinter UI, Feed Mapping editor, day/night theme, refresh loop (2 s), background scan (10 s), log auto-clear (2 h), Windows startup registry |
| `app/sync_engine.py` | Per-feed create/modify/delete orchestration, strict path filtering, reconciliation, pending-Excel retry, line-diff log messages |
| `app/excel_manager.py` | The three workbook layouts and safe atomic writes with retry |
| `app/feeds.py` | Feed definitions and defaults, legacy-name upgrade, category-time parsing/formatting |
| `app/config.py` | Load/save `config.json` (BOM-safe), typed accessors |
| `app/database.py` | SQLite cache of current source files, keyed by feed |
| `app/watcher.py` | watchdog observer, debounce, file-stability wait, filtered to the four files |
| `app/txt_reader.py` | Encoding fallback chain, BITMAP removal, line extraction |
| `app/scanner.py` | Resolves the configured source-file paths and their stats |
| `app/utils.py` | SHA-256 hashing, retry with back-off, file-stability check, timestamps |
| `app/single_instance.py` | Named-mutex guard |
| `app/logger.py` | Rotating file log `logs\app.log` (5 backups × 2 MB) |
| `app/models.py` | `FeedRecord` dataclass |
| `app/errors.py` | Shared `DocumentReadError` |
| `app/hindi_detector.py` | Devanagari detection helpers (not used by the sync path) |

### 9.2 Database

SQLite `sync.db`, one table `feeds`:

| Column | Notes |
|---|---|
| `id` | Primary key |
| `feed_key` | UNIQUE, for example `top_news` |
| `label`, `txt_file`, `full_path` | Feed identity and source path |
| `content` | Cleaned lines, joined with `\n` |
| `file_hash` | SHA-256 of the source file |
| `size`, `mtime` | Fast change detection |
| `created_at`, `modified_at`, `last_synced_at` | Timestamps |

This is a **cache, not a history**. A row exists only while its source file
exists. Deleting `sync.db` is safe: it is rebuilt on the next scan.

---

## 10. Developer guide

### 10.1 Requirements

- Windows 10/11 for development (Windows 7 SP1 for the legacy build, see §11.2)
- Python 3.10+ recommended (3.8+ supported; tested on 3.14)

```bash
cd word_to_excel_sync
python -m pip install -r requirements.txt
```

| Package | Purpose |
|---|---|
| `watchdog` | Folder monitoring |
| `openpyxl` | Writing `.xlsx` |
| `customtkinter` | GUI |
| `pillow` | Icon generation (build only) |
| `pyinstaller` | Packaging (build only) |

SQLite, TXT decoding and BITMAP parsing are standard library or hand-written.
There is no third-party document-parsing dependency.

### 10.2 Running from source

```bash
python main.py
```

> ⚠️ **Careful on the production PC.** The `config.json` next to `main.py`
> points at the live folders (`Desktop\notepad` → `Desktop\Excel taza tv`).
> Running from source there **writes the real playout workbooks**. For
> development, point both folders at a test location first, using **Browse** or
> by editing `config.json`.

A safe way to try the app against the bundled demo files without touching any
real folder:

```python
# sandbox_run.py  (keep it outside the project folder)
import os, shutil, sys, tempfile
PROJECT = r"C:\path\to\word_to_excel_sync"
sys.path.insert(0, PROJECT)
from app.config import Config
from app.logger import setup_logger
from app.gui import run_app

base = tempfile.mkdtemp(prefix="taaza_sandbox_")
txt, xls = os.path.join(base, "notepad"), os.path.join(base, "excel")
shutil.copytree(os.path.join(PROJECT, "demo_data"), txt)
os.makedirs(xls)
setup_logger(base)
cfg = Config(os.path.join(base, "config.json"), base_dir=base)
cfg.txt_root, cfg.excel_root = txt, xls
cfg.save()
run_app(cfg)
```

### 10.3 Tests

There are 159 unit tests. They use the standard-library `unittest`, so pytest
is optional:

```bash
python -m unittest discover -s tests -t .
```

or, if pytest is installed:

```bash
python -m pytest tests
```

| File | Tests | Covers |
|---|---|---|
| `test_excel.py` | 43 | Exact layouts, fonts, fills, widths, time formats, freeze/filter, atomic writes, lock handling |
| `test_feeds.py` | 30 | Feed defaults, file matching, legacy-name upgrade, category-time parsing |
| `test_sync.py` | 24 | Create / modify / delete / recreate per feed, strict filtering, pending retry |
| `test_txt_reader.py` | 22 | BITMAP removal, encoding fallback, line extraction |
| `test_config.py` | 16 | Load/save, BOM handling, unreadable-config reporting |
| `test_database.py` | 14 | SQLite cache |
| `test_hindi_detector.py` | 10 | Devanagari helpers |

Some console warnings ("Excel locked…", "config.json could not be read…") are
expected. They come from tests that deliberately exercise error handling.

`tests/manual/e2e_manual_test.py` is a manual end-to-end script and is not part
of the automated suite.

### 10.4 Demo data

`demo_data/row_01.txt` … `row_11.txt` are sample source files: Hindi and
English lines with BITMAP tags, including the seven non-feed files that must be
ignored. Regenerate them with:

```bash
python demo_data/generate_demo_data.py
```

### 10.5 Changing a playout name

If WASP3D starts expecting a different file or sheet name:

1. Change the default in `DEFAULT_FEEDS` (`app/feeds.py`).
2. Add an `(feed_key, field, old_value): new_value` entry to
   `LEGACY_FEED_VALUES`, so existing installs upgrade automatically.
3. Update the tests that assert the name (`tests/test_feeds.py`,
   `tests/test_excel.py`, `tests/test_sync.py`) and this README.
4. Rebuild the `.exe` (§11). Installed copies only change once they are
   rebuilt.

---

## 11. Building and deployment

### 11.1 Windows 10/11

```powershell
.\build_exe.ps1
```

This installs `requirements.txt`, regenerates the icon, and runs PyInstaller
(`--onefile --windowed`, custom icon, `customtkinter` collected). The output is
`dist\TaazaNewsExcelSync.exe`. The installer is built from `installer.iss`
with Inno Setup 6:

```powershell
& "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe" installer.iss
```

> `build_installer.ps1` is left over from the older app. It checks for
> `dist\WordToExcelHindiSync.exe` and fails, so call `ISCC.exe` directly as
> shown above (see §13).

### 11.2 Windows 7 SP1 64-bit

```bat
build_win7.bat
```

| Step | What happens |
|---|---|
| 1 | Creates `venv-win7` from **Python 3.8.10**, the last CPython release supporting Windows 7 |
| 2 | Installs the pinned `requirements-win7.txt` (watchdog 4.0.2, openpyxl 3.1.5, customtkinter 5.2.2, PyInstaller 5.13.2) |
| 3–4 | Cleans and builds `dist-win7\TaazaNewsExcelSync.exe` |
| 5 | Packs `TaazaNewsExcelSync_Portable.zip` (exe plus `README_PORTABLE.txt`) |
| 6 | Compiles `installer_win7.iss`, which bundles `win7_prereqs\vc_redist.x64.exe` (Microsoft VC++ runtime) |

The script expects Python 3.8.10 at `F:\PyWin7Build\Python38\python.exe`. The
installer `python-3.8.10-amd64.exe` is kept in `..\win7_build\`. See
[WINDOWS_7_SETUP.md](WINDOWS_7_SETUP.md) for the full background (why
Python 3.9+ fails on Windows 7, the UCRT prerequisite, and a test checklist).

### 11.3 Build outputs

| Output | Target | Approx. size |
|---|---|---|
| `dist\TaazaNewsExcelSync.exe` | Windows 10/11 | 31 MB |
| `installer_output\TXT_News_Excel_Sync_Setup.exe` | Windows 10/11 installer | 34 MB |
| `dist-win7\TaazaNewsExcelSync.exe` | Windows 7 SP1 64-bit | 12 MB |
| `installer_output_win7\TaazaNewsExcelSync_Win7_Setup.exe` | Windows 7 installer (with VC++ runtime) | 38 MB |
| `TaazaNewsExcelSync_Portable.zip` | Portable, no installer | 12 MB |

### 11.4 Installed layout

- **Program files:** `%LOCALAPPDATA%\Programs\Taaza News Excel Sync\` for the
  default per-user install, with no admin needed. If the installer is run
  elevated, it goes to `C:\Program Files\Taaza News Excel Sync\`.
- **Settings, cache and logs:** `%APPDATA%\TaazaNewsExcelSync\`
- **Uninstall:** Start menu → *Uninstall Taaza News Excel Sync*, or Programs
  and Features

### 11.5 Playout (WASP3D) side

WASP3D reads its Taaza TV data connections from
`\\wasp\Wasp3D\Wasp3d\Data Connections\Taaza TV\`. Whatever route gets the
workbooks there (the app writing straight into that folder, or a copy), the
**file names and sheet names must match** what WASP3D's data connections
expect. Check §3 and §13 whenever a name is changed on the WASP side.

To regenerate the app icon only:

```bash
python assets/make_icon.py
```

---

## 12. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| A feed never updates | Only the four configured names are read (`row_01`, `row_04`, `row_09`, `row_10` by default). Check **FEED MAPPING** for exact spelling, and that the file is directly inside the TXT folder, not in a subfolder |
| A workbook shows headers only | Its `.txt` file is missing or contains only blank or BITMAP lines. The feed list shows "file not found" |
| Workbook doesn't update, *Excel Pending: yes* | It is open in Excel or locked by another program. Close it; the app retries every ~2 s |
| `<BITMAP>` text appears in Excel | Shouldn't happen. Report it with the exact `.txt` content |
| Garbled Hindi in Excel | Make sure the body font is installed (`Nirmala UI` ships with Windows 8+; on Windows 7 install it or use a Devanagari font) |
| Wrong category times | Adjust *Default Category* / *First N news lines* in FEED MAPPING |
| Old `Top News LT.xlsx` still in the folder | Left over from before the rename (§7.3). Delete it; `TopNewsLT.xlsx` is the live file |
| WASP3D shows stale or no data | Compare file and sheet names in §3 with the names its data connection expects |
| "Already running" on launch | Only one copy may run. Close the other one (check the tray/taskbar and Task Manager) |
| "Settings file could not be read" warning | `config.json` is not valid JSON. Fix or delete it (it will be recreated with defaults), then re-check both folders |
| Missing DLL on Windows 7 | Use the Windows 7 build, not `dist\`. Install the VC++ 2015–2022 x64 runtime for the portable ZIP. See WINDOWS_7_SETUP.md |
| Need more detail | `logs\app.log` next to `config.json` (rotated, 5 × 2 MB) |

---

## 13. Known issues and limitations

| Item | Details |
|---|---|
| **Window-close handler (bug)** | In `app/gui.py`, `self.protocol("WM_DELETE_WINDOW", self._on_close)` sits inside `_warn_if_config_unreadable()` after its early `return`, so it is only registered when `config.json` failed to load. A normal close therefore skips stopping the watcher and closing the database. Fix: move that line into `App.__init__` |
| **Other WASP names differ** | On the WASP share, `Upper_Band.xlsx` uses sheet `BreakingNewsFF`, and `FullScreenBreaking.xlsx` uses sheet `NewsData` (Nirmala UI). The app still writes `Upper Band.xlsx` / `Breaking FF + Top.xlsx` with sheet `Breaking News FF`. Align them with the procedure in §10.5 if those are the files WASP3D reads |
| **`build_installer.ps1` is stale** | It still checks for the old app's `dist\WordToExcelHindiSync.exe` and stops with an error. Run `ISCC.exe installer.iss` directly, or update the script to check for `dist\TaazaNewsExcelSync.exe` |
| **Installed `.exe` lags the source** | Name changes (such as `TopNewsLT.xlsx`) reach installed PCs only after a rebuild and reinstall |
| **`venv-win7` path** | The build environment points at `F:\PyWin7Build\Python38\python.exe`. If drive `F:` is missing, reinstall Python 3.8.10 there (or edit `build_win7.bat`) and delete `venv-win7` so it is recreated |
| **Plain-text password** | `mapping_password` guards against accidental edits only. Change the default `2001` on production PCs |
| **No system-tray icon** | Intentional, to avoid an extra dependency. Minimise the window; the watcher keeps running |
| **Start with Windows** | Works only for the built `.exe`, not `python main.py` |
| **Sheet names not editable in the GUI** | By design; they are fixed in code because the playout software matches on them |
| **`hindi_detector.py` unused** | Every non-empty line is kept, Hindi or English |
| **Not yet verified on real Windows 7 hardware** | Verified through binary inspection and the test suite under Python 3.8. Run the checklist in WINDOWS_7_SETUP.md on a real machine |

---

## 14. Running alongside the older app

This app is deliberately separate from the older single-workbook
"TXT News to Excel Sync":

| | Old app | This app |
|---|---|---|
| Executable | `WordToExcelHindiSync.exe` | `TaazaNewsExcelSync.exe` |
| Installer AppId | `6A9F1D2E-…` | `B7E4C93A-…` |
| Settings folder | `%APPDATA%\TxtNewsExcelSync\` | `%APPDATA%\TaazaNewsExcelSync\` |
| Startup registry value | `TxtNewsToExcelSync` | `TaazaNewsExcelSync` |
| Icon | PyInstaller default | Custom red ticker icon |
| Output | One `All_Content.xlsx` | Four separate workbooks |

Both can be installed and run at the same time. They share no config, no
database and no output file.

---

## 15. Project structure

```
word_to_excel_sync/
├── main.py                    entry point
├── config.json                settings when run from source (live folders!)
├── requirements.txt           modern build dependencies
├── requirements-win7.txt      pinned Windows 7 build dependencies
├── README.md                  this file
├── README_PORTABLE.txt        shipped inside the portable ZIP
├── WINDOWS_7_SETUP.md         Windows 7 build and deployment guide
├── app/
│   ├── gui.py                 CustomTkinter UI + Feed Mapping editor
│   ├── sync_engine.py         per-feed sync orchestration
│   ├── excel_manager.py       workbook layouts + atomic writes
│   ├── feeds.py               feed definitions, legacy-name upgrade
│   ├── config.py              config.json load/save
│   ├── database.py            SQLite cache
│   ├── watcher.py             watchdog monitor
│   ├── txt_reader.py          decoding + BITMAP removal
│   ├── scanner.py             source-path resolution
│   ├── utils.py               hashing, retries, stability checks
│   ├── single_instance.py     named-mutex guard
│   ├── logger.py              rotating log
│   ├── models.py              FeedRecord dataclass
│   ├── errors.py              shared exceptions
│   └── hindi_detector.py      Devanagari helpers (unused by sync)
├── assets/
│   ├── make_icon.py           regenerates app_icon.ico
│   ├── app_icon.ico           application / installer icon
│   └── logo-en.png
├── tests/                     159 automated tests (+ manual/ e2e script)
├── demo_data/                 sample row_XX.txt files + generator
├── logs/                      app.log (when run from source)
├── build_exe.ps1              Windows 10/11 build
├── build_installer.ps1        Windows 10/11 installer build (stale, see §13)
├── build_win7.bat             Windows 7 SP1 build (exe + zip + installer)
├── installer.iss              Inno Setup script (Win 10/11)
├── installer_win7.iss         Inno Setup script (Win 7)
├── win7_prereqs/              vc_redist.x64.exe for the Win 7 installer
├── dist/, dist-win7/          built executables
└── installer_output/, installer_output_win7/   built installers
```

---

## 16. Change history

| Date | Change |
|---|---|
| 2026-10-13 | Top News output renamed to match WASP3D: file `Top News LT.xlsx` → **`TopNewsLT.xlsx`**, sheet `Top News LT` → **`TopNews`**. Existing settings upgrade automatically (§7.3). Tests: 159 |
| 2026-08-24 | Windows 7 SP1 64-bit build added (Python 3.8.10, PyInstaller 5.13.2, VC++ runtime in the installer) |
| 2026-08 | Rewrite to the four-feed model: one `.txt` → one workbook, single-instance guard, GUI overhaul, Feed Mapping editor, day/night theme |
| Earlier | Initial single-workbook "TXT Row to Excel Sync" (`All_Content.xlsx`) |
