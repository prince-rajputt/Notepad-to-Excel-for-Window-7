TXT News to Excel Sync - Portable (Windows 7 SP1 64-bit build)
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

If you used WordToExcelHindiSync_Win7_Setup.exe instead of this portable
folder, this prerequisite is installed for you automatically.

HOW TO RUN
----------
Double-click WordToExcelHindiSync.exe.

On first launch, a config.json and a logs\ folder are created under:
    %APPDATA%\TxtNewsExcelSync\

WHERE TO PUT YOUR .txt FILES
-----------------------------
By default: Documents\notepad\  (row_01.txt, row_02.txt, ...)
Change this from inside the app if needed.
