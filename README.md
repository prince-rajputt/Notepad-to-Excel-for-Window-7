# TXT Row to Excel Sync

A Windows desktop application that continuously monitors **one folder** of
Windows Notepad `.txt` files named `row_01.txt`, `row_02.txt`, ... and
automatically synchronizes their Hindi (Devanagari) content into **one Excel
workbook** — mapping each row number to a configurable category.

```
C:\Users\<you>\Documents\notepad\
├── row_01.txt   -> Serial 1  | Top News
├── row_02.txt   -> Serial 2  | National
├── row_03.txt   -> Serial 3  | Bengal
├── ...
├── row_11.txt   -> Serial 11 | Unassigned
└── All_Content.xlsx   (generated automatically, one sheet "Content")
```

There are **no category subfolders** — every `.txt` file lives directly
inside one root folder. The **row number** parsed from the filename
(`row_XX.txt` → `XX`) is both the permanent Excel serial number and the key
used to look up the file's category from a configurable mapping — the
filename itself does **not** determine the category.

> **Format note:** this version replaces the earlier Word/WordPad
> (`.docx`/`.rtf`) pipeline entirely. The application now reads plain `.txt`
> files only; there is no dependency on Microsoft Word, WordPad, or
> `python-docx`.

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
- Stores everything in a local SQLite database (`sync.db`) — the source of
  truth — and regenerates a single Excel workbook (`All_Content.xlsx`,
  worksheet `Content`) from it after every change.
- The **row number is the permanent identity**: `row_02.txt`'s Serial No. is
  always `2`, whether it's created, edited, deleted, or deleted-and-recreated
  later. Recreating a deleted `row_XX.txt` reuses the same Excel row rather
  than creating a new one.
- On startup, performs a full **initial scan** of the folder, then a periodic
  **reconciliation** (also triggerable via the "SYNC NOW" button) so changes
  made while the app was closed are picked up too.

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
`C:\Users\<you>\Documents\notepad`:

```json
{
    "txt_root": "C:\\Users\\<you>\\Documents\\notepad",
    "excel_file": "C:\\Users\\<you>\\Documents\\notepad\\All_Content.xlsx",
    "database_file": "C:\\Users\\<you>\\Documents\\notepad\\sync.db",
    "watch_extensions": [".txt"],
    "keep_deleted_records": true,
    "auto_start": false,
    "row_categories": {
        "1": "Top News", "2": "National", "3": "Bengal",
        "4": "Breaking News", "5": "Khabar Bihar", "6": "Khabar Jharkhand",
        "7": "Commentary Box", "8": "Entertainment Ticket",
        "9": "Full Screen Breaking", "10": "Upper Band", "11": "Unassigned"
    }
}
```

## 4. How TXT files are detected

Only files matching `row_XX.txt` (case-insensitive, any number of digits) are
processed. Any other `.txt` file is skipped and logged as
"Skipping non-row TXT file". Temp/lock files (names starting with `~`) and
non-`.txt` extensions (`.docx`, `.rtf`, `.xlsx`, `.xls`, `.pdf`, `.jpg`,
`.png`, `.exe`, `.tmp`) are always ignored.

## 5. How row numbers are mapped to serial numbers and categories

- **Serial No.** = the number parsed out of the filename (`row_02.txt` → `2`).
  It is never dynamically renumbered.
- **Category** = looked up from `row_categories` in `config.json` using that
  same row number, defaulting to `"Unassigned"` for any row with no explicit
  mapping.
- Use the **ROW / CATEGORY MAPPING** button in the GUI to edit category names
  for any row (existing or new). Saving immediately re-applies the mapping to
  every existing Excel row (via `SyncEngine.refresh_categories()`) — no need
  to touch any `.txt` file to see the new category name appear.
- The mapping editor is password-protected. The default password is `2001`;
  change it by editing `"mapping_password"` in `config.json`.

## 6. How Hindi is extracted (and how BITMAP tags are removed)

`app/txt_reader.py`'s `clean_and_extract_hindi_lines(text)` implements the
exact pipeline required:

1. Remove every `<BITMAP>...</BITMAP>` section (case-insensitive) from the
   whole text first, so tag content never leaks into the output and line
   boundaries outside the tag are preserved.
2. Split the remaining text into its original lines.
3. Collapse the whitespace left behind by tag removal and trim each line.
4. Keep the line only if it contains at least one Devanagari character
   (`contains_devanagari`, U+0900–U+097F); a line that was nothing but a
   BITMAP placeholder becomes empty after step 3 and is dropped here too.
5. Preserve the original line order.
6. Join the retained lines with `\n` — this becomes the Excel cell value.

| Input | Output |
|---|---|
| `आज बड़ी खबर है <BITMAP>:\newsair\logo.psd</BITMAP>` | `आज बड़ी खबर है` |
| `भारत ने India को हराया <BITMAP>...</BITMAP>` | `भारत ने India को हराया` (kept whole) |
| `India won the match <BITMAP>...</BITMAP>` | *(dropped - no Hindi)* |
| `<BITMAP>...</BITMAP>` (tag only) | *(dropped)* |

## 7. Excel synchronization

The `Content` worksheet has these columns:

| A | B | C | D | E | F | G | H | I |
|---|---|---|---|---|---|---|---|---|
| Serial No. | Category | File Name | Hindi Message | Created At | Modified At | Deleted At | Status | Last Synced At |

- The **Hindi Message** cell contains all retained Hindi lines from that one
  `.txt` file, joined with real line breaks (`\n`), with `wrap_text = True`
  and top vertical alignment — never split across multiple rows.
- Rows are always sorted by Serial No. (i.e. row number), **not**
  alphabetically by category.
- The header row is bold, frozen, and auto-filtered.
- A second **Summary** worksheet reports total/active/deleted file counts and
  the last sync time.
- If Excel has the file open (locked), the app retries with backoff
  (1s, 2s, 4s), keeps the database updated regardless, marks the sync as
  pending, and **automatically keeps retrying every ~2 seconds in the
  background** until the file is closed — no need to touch another `.txt`
  file to trigger the recovery. Writes go to a temp file first, then an
  atomic `os.replace`, so `All_Content.xlsx` is never left corrupted.

## 8. How modifications/deletions/recreation are handled

- **New file** (`row_12.txt` appears): detected, waited on until its size
  stabilizes, BITMAP-cleaned, Hindi-filtered, and inserted with
  Serial No. = 12, Category = whatever `row_categories["12"]` says (or
  `Unassigned`).
- **Modified file**: re-read, re-cleaned, and the *same* row is updated in
  place — Serial No. and Category are untouched, only `Hindi Message`,
  `Modified At`, and `Last Synced At` change.
- **Deleted file**: the Excel row is **not** removed. `Status` becomes
  `Deleted` and `Deleted At` is stamped; the last-known Hindi content stays
  visible for history.
- **Recreated file** (same `row_XX.txt` name reappears): because the row
  number is the permanent key, this updates the *same* database row back to
  `Status = Active` with the new content — it does **not** create a second
  row or a new serial number.
- **Duplicate/rapid filesystem events** from one save are debounced
  (coalesced within ~1.5s) so the same save isn't processed multiple times.

## 9. Reconciliation

Filesystem events alone aren't trusted as the sole source of truth (the PC
could be off, the app not running, or Windows could drop an event). On every
startup — and on demand via **SYNC NOW**, and automatically whenever you
Browse to a new TXT folder or click **START SYNC** — a full reconciliation
runs: scan the folder, diff against the database, add new rows, update
changed rows, and mark vanished rows as `Deleted`.

## 10. Database

SQLite (`sync.db`), single `files` table:

`id, row_number (UNIQUE), category, file_name, full_path, content, file_hash (SHA-256), size, mtime, created_at, modified_at, deleted_at, status, last_synced_at`

`row_number` is the single source of identity — there is no separate UUID,
because the row number is already permanent and unique by construction
(one filename pattern, one row). `size`/`mtime` are checked first so
unchanged files are never unnecessarily re-parsed or re-hashed.

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
| A file never shows up | Check its name matches `row_XX.txt` exactly (e.g. `National.txt` is ignored - only the row-number pattern is recognized). |
| Category shows "Unassigned" | No mapping exists for that row number yet - add one via **ROW / CATEGORY MAPPING** and Save. |
| `<BITMAP>...` text leaking into Excel | Shouldn't happen - file a bug with the exact `.txt` content if seen. |
| Excel shows "pending" / doesn't update | `All_Content.xlsx` is open in Excel - the app retries automatically every ~2s; just close Excel. |
| Hindi Message is empty | The document contains no Devanagari text after BITMAP removal - this is expected; the row stays `Active` with an empty message. |
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
│   ├── database.py       - SQLite source of truth, keyed by row_number
│   ├── models.py         - FileRecord dataclass
│   ├── errors.py         - shared DocumentReadError
│   ├── txt_reader.py     - BITMAP removal, encoding fallback, Hindi extraction
│   ├── row_mapping.py    - row_XX.txt filename parsing + category lookup
│   ├── hindi_detector.py - Devanagari detection
│   ├── scanner.py        - folder listing helpers
│   ├── watcher.py        - watchdog real-time monitor (debounced)
│   ├── sync_engine.py    - create/modify/delete/recreate orchestration
│   ├── excel_manager.py  - openpyxl workbook generation
│   ├── gui.py            - CustomTkinter UI + Row/Category Mapping editor
│   ├── logger.py         - rotating file logging
│   └── utils.py          - hashing, retries, stability checks
├── tests/                 - 74 automated unit tests
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
