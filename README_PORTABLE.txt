Taaza News Excel Sync - Portable (Windows 7 SP1 64-bit build)
================================================================

This folder is fully self-contained: it does NOT require Python or
PyInstaller to be installed on this computer.

REQUIREMENT: Microsoft Visual C++ 2015-2022 Redistributable (x64)
-------------------------------------------------------------------
On Windows 7 SP1, this one-time prerequisite is usually needed (it supplies
the Universal C Runtime, which Windows 7 does not ship by default). If the
app fails to launch, install it from the official Microsoft link:

    https://aka.ms/vs/17/release/vc_redist.x64.exe

Then just double-click vc_redist.x64.exe and follow the prompts (no
restart normally required). This is a standard, official Microsoft
redistributable used by thousands of Windows applications - not a
random/unofficial DLL.

If you used TaazaNewsExcelSync_Win7_Setup.exe instead of this portable
folder, this prerequisite is installed for you automatically.

HOW TO RUN
----------
Double-click TaazaNewsExcelSync.exe.

On first launch, a config.json, sync.db and a logs\ folder are created under:
    %APPDATA%\TaazaNewsExcelSync\

This is a separate folder from the older "TXT News to Excel Sync" app, so
both can be installed and run on the same machine without interfering.

THE FOUR FEEDS
--------------
Each source .txt file is written to its own Excel workbook:

    row_01.txt  ->  TopNewsLT.xlsx            (Top News)
    row_10.txt  ->  Upper Band.xlsx           (Upper Band)
    row_04.txt  ->  Breaking LT.xlsx          (Breaking News)
    row_09.txt  ->  Breaking FF + Top.xlsx    (Full Screen Breaking)

No other file in either folder is read or written.

WHERE TO PUT YOUR FILES
-----------------------
TXT folder   (default): Documents\notepad\
Excel folder (default): Desktop\Excel taza tv\

Change either from inside the app (Browse buttons). The file names above
can be changed under FEED MAPPING (password: 2001).
