# TXT News → Excel Sync

A Windows desktop application that continuously monitors **one folder** of
Windows Notepad `.txt` files named `row_01.txt`, `row_02.txt`, ... and keeps
**one Excel workbook** as a **live mirror** of their Hindi news content —
one row number maps to one category, and every individual Hindi news line
inside that file becomes its own Excel row.

```
C:\Users\<you>\Documents\notepad\
├── row_01.txt   -> Category: Top News
├── row_02.txt   -> Category: खबर India
├── row_03.txt   -> Category: खबर बंगाल
├── ...
├── row_11.txt   -> Category: Advertisement
└── All_Content.xlsx   (generated automatically, sheets "News Data" + "News Category")
```

There are **no category subfolders** — every `.txt` file lives directly
inside one root folder. The **row number** parsed from the filename
(`row_XX.txt` → `XX`) determines the category via a configurable mapping.

> **Key design rule:** one `.txt` file = one **category**, not one Excel row.
> Every valid Hindi news line inside that file becomes its own row in the
> `News Data` sheet. The workbook always reflects exactly the files
> currently on disk — delete a `.txt` file and its news disappears from
> Excel; there is no "Deleted" history kept.

---

## 1. What the application does

- Watches a single folder in real time (using `watchdog`) for `row_XX.txt`
  files being created, edited, deleted, or renamed.
- Reads each file with a robust encoding fallback chain (UTF-8 with/without
  BOM, UTF-16, Windows-1252, latin-1) so Hindi text is never corrupted.
- Removes every `<BITMAP>...</BITMAP>` image-placeholder tag (case-
  insensitive) from the text — this metadata is never treated as content.
- Keeps only lines that contain at least one Devanagari (Hindi, U+0900–
  U+097F) character after BITMAP removal. English-only lines are discarded;
  mixed Hindi/English lines are kept in full, exactly as written (no
  translation, summarization, or rewording).
- Stores the currently-existing files' extracted content in a local SQLite
  database (`sync.db`) — an internal cache used to avoid re-parsing unchanged
  files — and fully **regenerates** `All_Content.xlsx` from that database on
  every sync, so the workbook always matches the current folder exactly.
- On startup, performs a full **initial scan** of the folder, then a periodic
  **reconciliation** (also triggerable via **SYNC NOW**) so changes made
  while the app was closed are picked up too.

---

## 2. Installation

Requirements: Windows 10/11, Python 3.10+.

```bash
cd word_to_excel_sync
python -m pip install -r requirements.txt
```

Dependencies: `watchdog`, `openpyxl`, `customtkinter`, `pyinstaller`
(build-only). SQLite and the TXT/BITMAP parsing are both part of the
standard library / hand-written — there is no third-party document-parsing
dependency at all.

---

## 3. How to run (from Python)

```bash
python main.py
```

On first launch a `config.json` is created next to `main.py` (or next to the
`.exe` when running the built binary), defaulting to
`C:\Users\<you>\Documents\notepad`, with the default row/category mapping.

## 4. Final category mapping

| Row | Category |
|---|---|
| 1 | Top News |
| 2 | खबर India |
| 3 | खबर बंगाल |
| 4 | Breaking News |
| 5 | खबर बिहार |
| 6 | खबर झारखंड |
| 7 | Commentary Box |
| 8 | Entertainment |
| 9 | Full Screen Breaking |
| 10 | Upper Band |
| 11 | Advertisement |

Editable any time via the **ROW / CATEGORY MAPPING** button in the GUI
(password-protected, default `2001`). Saving immediately re-applies the new
category names to every currently-tracked file and regenerates Excel — no
need to touch any `.txt` file.

## 5. Excel design

The workbook has exactly two sheets:

### `News Data` (the main output)

| A | B | C |
|---|---|---|
| Visibility | Category | News Data |

- **Category placeholder rows** (`Visibility = 0`, blank `News Data`) come
  first, one per currently-active category, in row-number order.
- **Actual news rows** (`Visibility = 1`) follow, one per Hindi news line,
  grouped by category in row-number order.
- Only categories whose `row_XX.txt` file **currently exists** appear at
  all — no placeholder and no news rows for a row number with no file.
- Header row: bold, bright yellow fill, frozen (`freeze_panes = A2`),
  `AutoFilter` enabled on `A1:C<last row>`.
- Unicode font (`Nirmala UI`) throughout for correct Hindi rendering; long
  news lines (>100 characters) get `wrap_text` enabled automatically.

Example (only `row_02.txt`, `row_03.txt`, `row_05.txt` currently exist):

```
Visibility | Category    | News Data
0          | खबर India   |
0          | खबर बंगाल   |
0          | खबर बिहार   |
1          | खबर India   | आज देश में बड़ी खबर सामने आई है
1          | खबर India   | सरकार ने नई घोषणा की है
1          | खबर बंगाल   | कोलकाता में भारी बारिश हुई
1          | खबर बिहार   | बिहार में मौसम को लेकर चेतावनी
```

### `News Category` (configuration reference)

| A | B |
|---|---|
| Row No. | Category |

Lists the **full** configured mapping (all 11 rows, or however many are
configured) regardless of which files currently exist — this is a reference
sheet, not tied to the live folder state.

## 6. How Hindi is extracted (and how BITMAP tags are removed)

`app/txt_reader.py`'s `clean_and_extract_hindi_lines(text)` (aliased as
`clean_and_extract_news_lines`) implements the exact pipeline required:

1. Remove every `<BITMAP>...</BITMAP>` section (case-insensitive) from the
   whole text first, so tag content never leaks into the output and line
   boundaries outside the tag are preserved.
2. Split the remaining text into its original lines.
3. Collapse the whitespace left behind by tag removal and trim each line.
4. Keep the line only if it contains at least one Devanagari character
   (`contains_devanagari`, U+0900–U+097F); a line that was nothing but a
   BITMAP placeholder becomes empty after step 3 and is dropped here too.
5. Preserve the original line order.
6. Each retained line becomes its own row in `News Data` (joined with `\n`
   internally in the database, split back into individual rows when Excel
   is generated).

| Input | Output |
|---|---|
| `आज बड़ी खबर है <BITMAP>:\newsair\logo.psd</BITMAP>` | `आज बड़ी खबर है` |
| `भारत ने India को हराया <BITMAP>...</BITMAP>` | `भारत ने India को हराया` (kept whole) |
| `India won the match <BITMAP>...</BITMAP>` | *(dropped - no Hindi)* |
| `<BITMAP>...</BITMAP>` (tag only) | *(dropped)* |

## 7. How TXT files are detected

Only files matching `row_XX.txt` (case-insensitive, any number of digits) are
processed. Any other `.txt` file is skipped and logged as
"Skipping non-row TXT file". Temp/lock files (names starting with `~`) and
non-`.txt` extensions are always ignored.

## 8. How modifications/deletions/recreation are handled

- **New file** (`row_08.txt` appears): detected, waited on until its size
  stabilizes, BITMAP-cleaned, Hindi-filtered, and its category's placeholder
  + one row per news line are added to `News Data`.
- **Modified file**: re-read, re-cleaned, and the *same* database record is
  updated in place — its old news rows are replaced by the newly-generated
  ones on the next Excel rebuild (no duplicates).
- **Deleted file**: its database record is removed entirely, and on the next
  Excel rebuild both its placeholder row and all its news rows disappear
  from `News Data` — the workbook is a live mirror, not a history.
- **Recreated file** (same `row_XX.txt` name reappears): treated as a fresh
  new file for that row number - its news reappears with the current content.
- **Duplicate/rapid filesystem events** from one save are debounced
  (coalesced within ~1.5s) so the same save isn't processed multiple times.

## 9. Reconciliation

Filesystem events alone aren't trusted as the sole source of truth. On every
startup — and on demand via **SYNC NOW**, and automatically whenever you
Browse to a new TXT folder or click **START MONITORING** — a full
reconciliation runs: scan the folder, diff against the database, add new
rows, update changed rows, and remove rows for files that vanished.

## 10. Database

SQLite (`sync.db`), single `files` table:

`id, row_number (UNIQUE), category, file_name, full_path, content, file_hash (SHA-256), size, mtime, created_at, modified_at, last_synced_at`

This is purely an internal cache to avoid re-parsing unchanged files
(checked via `size`/`mtime` first, then SHA-256 hash) — it is **not** a
history. A record only exists while its file exists on disk.

## 11. Building the EXE

```powershell
.\build_exe.ps1
```

This installs dependencies, runs PyInstaller (`python -m PyInstaller`) with
`--windowed --onefile`, and produces `dist\WordToExcelHindiSync.exe` — a
single-file, console-less executable that runs on Windows without Python
installed. `config.json` and `logs\` are created next to the `.exe` on first
run.

## 12. Troubleshooting

| Symptom | Cause / Fix |
|---|---|
| A file never shows up | Check its name matches `row_XX.txt` exactly. |
| Category shows "Unassigned" | No mapping exists for that row number yet - add one via **ROW / CATEGORY MAPPING** and Save. |
| `<BITMAP>...` text leaking into Excel | Shouldn't happen - file a bug with the exact `.txt` content if seen. |
| Excel shows "pending" / doesn't update | `All_Content.xlsx` is open in Excel - the app retries automatically every ~2s; just close Excel. |
| A category disappeared from Excel | Its `.txt` file was deleted - this is expected (live mirror). Recreate the file to bring it back. |
| Logs | Check `logs\app.log` (rotated automatically, 5 x 2MB backups). |

---

## Project structure

```
word_to_excel_sync/
├── main.py
├── requirements.txt
├── README.md
├── app/
│   ├── config.py         - load/save config.json, row_categories mapping
│   ├── database.py       - SQLite cache of currently-existing files, keyed by row_number
│   ├── models.py         - FileRecord dataclass
│   ├── errors.py         - shared DocumentReadError
│   ├── txt_reader.py     - BITMAP removal, encoding fallback, Hindi extraction
│   ├── row_mapping.py    - row_XX.txt filename parsing + category lookup
│   ├── hindi_detector.py - Devanagari detection
│   ├── scanner.py        - folder listing helpers
│   ├── watcher.py        - watchdog real-time monitor (debounced)
│   ├── sync_engine.py    - create/modify/delete/recreate orchestration, live-mirror rebuild
│   ├── excel_manager.py  - openpyxl workbook generation (News Data + News Category)
│   ├── gui.py            - CustomTkinter UI + Row/Category Mapping editor + day/night theme
│   ├── logger.py         - rotating file logging
│   └── utils.py          - hashing, retries, stability checks
├── tests/                 - 75 automated unit tests
│   └── manual/e2e_manual_test.py - scripted end-to-end check via the real watcher
├── demo_data/              - row_01.txt .. row_11.txt (mixed Hindi/English + BITMAP) + generator script
├── logs/
└── build_exe.ps1
```

## Limitations

- Windows system tray integration was intentionally left out to avoid an
  extra dependency; the app can still be minimized normally while the watcher
  keeps running in the background thread.
- "Start automatically with Windows" writes a `Run` key under
  `HKEY_CURRENT_USER` pointing at the built `.exe`; it has no effect when
  running from `python main.py` directly (there is no stable exe path to
  register).
- The row/category mapping editor lets you add or rename rows, but does not
  currently offer a delete button for a mapping entry - remove an unwanted
  entry directly in `config.json`'s `row_categories` if needed.
