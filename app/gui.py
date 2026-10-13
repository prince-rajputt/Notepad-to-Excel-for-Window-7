"""CustomTkinter desktop GUI for Taaza News Excel Sync."""
import logging
import os
import queue
import sys
import threading
import time

import customtkinter as ctk
from tkinter import filedialog, messagebox, ttk

from app.database import Database
from app.feeds import Feed, format_category_time, parse_category_time
from app.sync_engine import SyncEngine
from app.utils import now_str
from app.watcher import FolderWatcher

logger = logging.getLogger("taaza_news_excel_sync")

APP_TITLE = "Taaza News → Excel Sync"
REFRESH_MS = 2000
BACKGROUND_SCAN_SECONDS = 10  # safety-net reconciliation, in case a filesystem event is missed
LOG_AUTO_CLEAR_SECONDS = 2 * 60 * 60  # activity log view auto-clears every 2 hours (app runs 24/7)

STARTUP_REGISTRY_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
STARTUP_VALUE_NAME = "TaazaNewsExcelSync"

NIGHT_MODE_COLOR = "#000000"


def _set_windows_startup(enabled, exe_path):
    if sys.platform != "win32":
        return
    try:
        import winreg

        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, STARTUP_REGISTRY_KEY, 0, winreg.KEY_SET_VALUE)
        if enabled:
            winreg.SetValueEx(key, STARTUP_VALUE_NAME, 0, winreg.REG_SZ, f'"{exe_path}"')
        else:
            try:
                winreg.DeleteValue(key, STARTUP_VALUE_NAME)
            except FileNotFoundError:
                pass
        winreg.CloseKey(key)
    except OSError as exc:
        logger.error("Failed to update Windows startup registry: %s", exc)


class App(ctk.CTk):
    def __init__(self, config):
        super().__init__()
        self.config_obj = config
        self.title(APP_TITLE)
        self.geometry("1050x960")

        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")

        self.db = Database(self.config_obj.database_file)
        self.engine = SyncEngine(self.db, self.config_obj)
        self.engine.on_event = self._on_engine_event
        self.watcher = FolderWatcher(self.engine)

        self._log_queue = queue.Queue()
        self._log_cleared_at = time.monotonic()
        self._excel_retry_in_progress = False
        self._background_scan_in_progress = False
        self._mapping_window = None
        self._mapping_entries = {}
        self._themed_widgets = []  # (widget, original_fg_color) pairs, for light/night toggling

        self._build_ui()
        self._dark_mode = bool(self.config_obj.get("dark_mode", False))
        self._apply_theme(self._dark_mode)
        self._warn_if_config_unreadable()
        # Monitoring runs automatically the moment the app opens - no button
        # click required for normal (unattended) operation. START/STOP MONITORING
        # stay available for manually pausing/resuming it. The initial scan
        # covers files already changed while the app was closed; the watcher
        # then takes over for everything from this point on.
        self._start_initial_scan_async()
        self._start_watcher_only()
        self._last_background_scan = time.monotonic()
        self.after(REFRESH_MS, self._periodic_refresh)

    def _warn_if_config_unreadable(self):
        """A config.json that failed to parse means the app is about to use the
        DEFAULT folders, not the configured ones. That must never pass
        unnoticed - it would write to the wrong Excel folder."""
        error = getattr(self.config_obj, "load_error", None)
        if not error:
            return
        self._log_queue.put(f"✗ {error}")
        messagebox.showwarning(
            APP_TITLE,
            "Your settings file could not be read, so DEFAULT folders are in use:\n\n"
            f"TXT folder:   {self.config_obj.txt_root}\n"
            f"Excel folder: {self.config_obj.excel_root}\n\n"
            f"{error}\n\n"
            "Check the folders above before starting monitoring.",
        )

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # -- UI construction -------------------------------------------------------

    def _build_ui(self):
        pad = {"padx": 10, "pady": 6}

        header = ctk.CTkFrame(self)
        header.pack(fill="x", **pad)
        self._register_themed(header)

        ctk.CTkLabel(
            header, text="TAAZA NEWS → EXCEL SYNC", font=ctk.CTkFont(size=20, weight="bold")
        ).pack(side="left", padx=10, pady=8)
        self.theme_toggle_btn = ctk.CTkButton(
            header, text="☀", width=36, command=self._toggle_theme,
        )
        self.theme_toggle_btn.pack(side="right", padx=10, pady=8)

        paths_frame = ctk.CTkFrame(self)
        paths_frame.pack(fill="x", **pad)
        self._register_themed(paths_frame)

        ctk.CTkLabel(paths_frame, text="TXT Folder:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        self.txt_folder_var = ctk.StringVar(value=self.config_obj.txt_root)
        ctk.CTkEntry(paths_frame, textvariable=self.txt_folder_var, width=500).grid(
            row=0, column=1, padx=5, pady=5
        )
        ctk.CTkButton(paths_frame, text="Browse", command=self._browse_txt_folder).grid(
            row=0, column=2, padx=5, pady=5
        )

        ctk.CTkLabel(paths_frame, text="Excel Folder:").grid(row=1, column=0, sticky="w", padx=5, pady=5)
        self.excel_folder_var = ctk.StringVar(value=self.config_obj.excel_root)
        ctk.CTkEntry(paths_frame, textvariable=self.excel_folder_var, width=500).grid(
            row=1, column=1, padx=5, pady=5
        )
        ctk.CTkButton(paths_frame, text="Browse", command=self._browse_excel_folder).grid(
            row=1, column=2, padx=5, pady=5
        )

        self.startup_var = ctk.BooleanVar(value=self.config_obj.get("auto_start", False))
        ctk.CTkCheckBox(
            paths_frame, text="Start automatically with Windows",
            variable=self.startup_var, command=self._toggle_startup,
        ).grid(row=2, column=0, columnspan=3, sticky="w", padx=5, pady=5)

        status_frame = ctk.CTkFrame(self)
        status_frame.pack(fill="x", **pad)
        self._register_themed(status_frame)

        self.status_label = ctk.CTkLabel(status_frame, text="● STOPPED", text_color="red",
                                          font=ctk.CTkFont(size=14, weight="bold"))
        self.status_label.pack(side="left", padx=10, pady=8)

        self.last_sync_label = ctk.CTkLabel(status_frame, text="Last Sync: -")
        self.last_sync_label.pack(side="left", padx=20, pady=8)

        stats_frame = ctk.CTkFrame(self)
        stats_frame.pack(fill="x", **pad)
        self._register_themed(stats_frame)
        self.stat_total = ctk.CTkLabel(stats_frame, text="Feeds Synced: 0")
        self.stat_news_items = ctk.CTkLabel(stats_frame, text="Total News Items: 0")
        self.stat_pending = ctk.CTkLabel(stats_frame, text="Excel Pending: no")
        for w in (self.stat_total, self.stat_news_items, self.stat_pending):
            w.pack(side="left", padx=15, pady=8)

        buttons_frame = ctk.CTkFrame(self)
        buttons_frame.pack(fill="x", **pad)
        self._register_themed(buttons_frame)
        ctk.CTkButton(buttons_frame, text="START MONITORING", command=self._start_sync).pack(
            side="left", padx=5, pady=8
        )
        ctk.CTkButton(buttons_frame, text="STOP MONITORING", command=self._stop_sync).pack(
            side="left", padx=5, pady=8
        )
        ctk.CTkButton(buttons_frame, text="SYNC NOW", command=self._sync_now).pack(
            side="left", padx=5, pady=8
        )
        ctk.CTkButton(buttons_frame, text="OPEN EXCEL FOLDER", command=self._open_excel_folder).pack(
            side="left", padx=5, pady=8
        )
        ctk.CTkButton(buttons_frame, text="OPEN TXT FOLDER", command=self._open_txt_folder).pack(
            side="left", padx=5, pady=8
        )
        ctk.CTkButton(buttons_frame, text="FEED MAPPING", command=self._open_mapping_editor).pack(
            side="left", padx=5, pady=8
        )

        search_frame = ctk.CTkFrame(self)
        search_frame.pack(fill="x", **pad)
        self._register_themed(search_frame)
        ctk.CTkLabel(search_frame, text="Search:").pack(side="left", padx=5)
        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", lambda *_: self._refresh_file_list())
        ctk.CTkEntry(search_frame, textvariable=self.search_var, width=200).pack(side="left", padx=5)

        list_frame = ctk.CTkFrame(self)
        list_frame.pack(fill="both", expand=True, **pad)
        self._register_themed(list_frame)
        columns = ("feed", "txt_file", "excel_file", "news_lines", "modified", "status")
        self.tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=6)
        for col, label, width in (
            ("feed", "Feed", 170), ("txt_file", "TXT File", 110),
            ("excel_file", "Excel File", 200), ("news_lines", "News Lines", 90),
            ("modified", "Modified At", 170), ("status", "Status", 170),
        ):
            self.tree.heading(col, text=label)
            self.tree.column(col, width=width)
        self.tree.tag_configure("pending", foreground="#e67e22")
        self.tree.tag_configure("synced", foreground="#2ecc71")
        self.tree.pack(fill="both", expand=True, side="left")
        self.tree.bind("<Double-1>", self._on_row_double_click)
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")

        log_label = ctk.CTkLabel(self, text="ACTIVITY LOG", font=ctk.CTkFont(weight="bold"))
        log_label.pack(anchor="w", padx=10)
        self.log_box = ctk.CTkTextbox(self, height=340, font=ctk.CTkFont(family="Consolas", size=12))
        self.log_box.pack(fill="both", expand=True, **pad)
        self.log_box.configure(state="disabled")
        self.log_box.tag_config("added", foreground="#2ecc71")
        self.log_box.tag_config("removed", foreground="#e74c3c")
        self.log_box.tag_config("modified", foreground="#f39c12")
        self.log_box.tag_config("info", foreground="#5dade2")
        self._register_themed(self.log_box)
        self._register_themed(self)

    # -- Day / Night theme -----------------------------------------------------

    def _register_themed(self, widget):
        """Remember a widget's original (light-mode) fg_color so night mode can
        override it to pure black and day mode can restore it exactly."""
        self._themed_widgets.append((widget, widget.cget("fg_color")))

    def _apply_theme(self, dark):
        ctk.set_appearance_mode("Dark" if dark else "Light")

        for widget, original_fg_color in self._themed_widgets:
            widget.configure(fg_color=NIGHT_MODE_COLOR if dark else original_fg_color)

        style = ttk.Style()
        style.theme_use("default")
        if dark:
            style.configure(
                "Treeview", background=NIGHT_MODE_COLOR, fieldbackground=NIGHT_MODE_COLOR,
                foreground="white", borderwidth=0,
            )
            style.configure("Treeview.Heading", background="#1a1a1a", foreground="white")
            style.map("Treeview", background=[("selected", "#333333")], foreground=[("selected", "white")])
        else:
            style.configure(
                "Treeview", background="white", fieldbackground="white", foreground="black", borderwidth=0,
            )
            style.configure("Treeview.Heading", background="#f0f0f0", foreground="black")
            style.map("Treeview", background=[("selected", "#0078D7")], foreground=[("selected", "white")])

        self.theme_toggle_btn.configure(text="🌙" if dark else "☀")

    def _toggle_theme(self):
        self._dark_mode = not self._dark_mode
        self._apply_theme(self._dark_mode)
        self.config_obj.set("dark_mode", self._dark_mode)
        self.config_obj.save()

    # -- Feed mapping editor -----------------------------------------------

    def _prompt_password(self):
        """Show a modal password dialog. Returns True only if the correct
        password (config.json's "mapping_password", default "2001") was entered."""
        result = {"ok": False}
        expected = str(self.config_obj.get("mapping_password", "2001"))

        dialog = ctk.CTkToplevel(self)
        dialog.title("Enter Password")
        dialog.geometry("340x170")
        dialog.resizable(False, False)
        dialog.transient(self)

        ctk.CTkLabel(
            dialog, text="Enter password to access Feed Mapping:", wraplength=300
        ).pack(padx=15, pady=(20, 10))

        pw_var = ctk.StringVar()
        entry = ctk.CTkEntry(dialog, textvariable=pw_var, show="*", width=220)
        entry.pack(padx=15, pady=5)

        error_label = ctk.CTkLabel(dialog, text="", text_color="red")
        error_label.pack(pady=(0, 5))

        def submit():
            if pw_var.get() == expected:
                result["ok"] = True
                dialog.destroy()
            else:
                error_label.configure(text="Incorrect password")
                pw_var.set("")

        entry.bind("<Return>", lambda _e: submit())

        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(pady=10)
        ctk.CTkButton(btn_frame, text="OK", command=submit, width=80).pack(side="left", padx=5)
        ctk.CTkButton(btn_frame, text="Cancel", command=dialog.destroy, width=80).pack(side="left", padx=5)

        dialog.grab_set()
        entry.focus_set()
        dialog.wait_window()
        return result["ok"]

    def _open_mapping_editor(self):
        if self._mapping_window is not None and self._mapping_window.winfo_exists():
            self._mapping_window.lift()
            self._mapping_window.focus_force()
            return

        if not self._prompt_password():
            return

        win = ctk.CTkToplevel(self)
        win.title("Feed Mapping")
        win.geometry("620x620")
        self._mapping_window = win

        ctk.CTkLabel(win, text="Feed Mapping", font=ctk.CTkFont(size=16, weight="bold")).pack(
            padx=10, pady=(10, 5)
        )
        ctk.CTkLabel(
            win,
            text=(
                "Each feed reads one .txt file from the TXT folder and writes one .xlsx "
                "file in the Excel folder. Only these files are ever touched."
            ),
            wraplength=560, justify="left",
        ).pack(padx=10, pady=(0, 10))

        scroll = ctk.CTkScrollableFrame(win, width=570, height=340)
        scroll.pack(fill="both", expand=True, padx=10, pady=5)

        self._mapping_entries = {}
        for feed in self.config_obj.feeds:
            self._add_mapping_row(scroll, feed)

        defaults_frame = ctk.CTkFrame(win)
        defaults_frame.pack(fill="x", padx=10, pady=(5, 0))
        ctk.CTkLabel(defaults_frame, text="Default Visibility:").grid(
            row=0, column=0, sticky="w", padx=5, pady=5
        )
        self._default_visibility_var = ctk.StringVar(value=str(self.config_obj.default_visibility))
        ctk.CTkEntry(defaults_frame, textvariable=self._default_visibility_var, width=60).grid(
            row=0, column=1, padx=5, pady=5
        )
        ctk.CTkLabel(defaults_frame, text="Default Category (Breaking LT):").grid(
            row=0, column=2, sticky="w", padx=5, pady=5
        )
        self._default_category_var = ctk.StringVar(value=self.config_obj.default_category_time)
        ctk.CTkEntry(defaults_frame, textvariable=self._default_category_var, width=130).grid(
            row=0, column=3, padx=5, pady=5
        )

        ctk.CTkLabel(defaults_frame, text="First").grid(row=1, column=0, sticky="e", padx=5, pady=5)
        self._first_category_count_var = ctk.StringVar(
            value=str(self.config_obj.first_category_count)
        )
        ctk.CTkEntry(defaults_frame, textvariable=self._first_category_count_var, width=60).grid(
            row=1, column=1, padx=5, pady=5
        )
        ctk.CTkLabel(defaults_frame, text="news lines use Category:").grid(
            row=1, column=2, sticky="w", padx=5, pady=5
        )
        self._first_category_var = ctk.StringVar(value=self.config_obj.first_category_time)
        ctk.CTkEntry(defaults_frame, textvariable=self._first_category_var, width=130).grid(
            row=1, column=3, padx=5, pady=5
        )
        ctk.CTkLabel(
            defaults_frame,
            text="Every line after those - including newly added ones - uses the Default Category.",
            text_color="gray", wraplength=540, justify="left",
        ).grid(row=2, column=0, columnspan=4, sticky="w", padx=5, pady=(0, 5))

        button_frame = ctk.CTkFrame(win)
        button_frame.pack(fill="x", padx=10, pady=10)
        ctk.CTkButton(button_frame, text="Save Mapping", command=self._save_mapping).pack(
            side="left", padx=5
        )
        ctk.CTkButton(button_frame, text="Close", command=win.destroy).pack(side="left", padx=5)

    def _add_mapping_row(self, parent, feed):
        row_frame = ctk.CTkFrame(parent)
        row_frame.pack(fill="x", pady=4)

        ctk.CTkLabel(
            row_frame, text=feed.label, width=150, anchor="w",
            font=ctk.CTkFont(weight="bold"),
        ).grid(row=0, column=0, rowspan=2, sticky="w", padx=5, pady=4)

        ctk.CTkLabel(row_frame, text="TXT:", width=40, anchor="w").grid(
            row=0, column=1, sticky="w", padx=2
        )
        txt_var = ctk.StringVar(value=feed.txt_file)
        ctk.CTkEntry(row_frame, textvariable=txt_var, width=140).grid(row=0, column=2, padx=5, pady=2)

        ctk.CTkLabel(row_frame, text="Excel:", width=40, anchor="w").grid(
            row=1, column=1, sticky="w", padx=2
        )
        excel_var = ctk.StringVar(value=feed.excel_file)
        ctk.CTkEntry(row_frame, textvariable=excel_var, width=200).grid(row=1, column=2, padx=5, pady=2)

        ctk.CTkLabel(
            row_frame, text=f"sheet: {feed.sheet_name}", anchor="w", text_color="gray",
        ).grid(row=1, column=3, sticky="w", padx=5)

        self._mapping_entries[feed.key] = (feed, txt_var, excel_var)

    def _save_mapping(self):
        updated = []
        for feed, txt_var, excel_var in self._mapping_entries.values():
            txt_file = txt_var.get().strip() or feed.txt_file
            excel_file = excel_var.get().strip() or feed.excel_file
            updated.append(
                Feed(
                    key=feed.key, label=feed.label, txt_file=txt_file,
                    excel_file=excel_file, excel_format=feed.excel_format,
                    sheet_name=feed.sheet_name,
                    category_sheet_name=feed.category_sheet_name,
                )
            )
        self.config_obj.save_feeds(updated)

        try:
            visibility = int(self._default_visibility_var.get().strip())
        except ValueError:
            messagebox.showerror(APP_TITLE, "Default Visibility must be a whole number.")
            return
        self.config_obj.set("default_visibility", visibility)

        try:
            first_count = int(self._first_category_count_var.get().strip())
        except ValueError:
            messagebox.showerror(APP_TITLE, "The 'First N news lines' value must be a whole number.")
            return
        if first_count < 0:
            messagebox.showerror(APP_TITLE, "The 'First N news lines' value cannot be negative.")
            return
        self.config_obj.set("first_category_count", first_count)

        for key, var in (
            ("default_category_time", self._default_category_var),
            ("first_category_time", self._first_category_var),
        ):
            self.config_obj.set(
                key, format_category_time(parse_category_time(var.get().strip()))
            )

        self.config_obj.save()
        threading.Thread(target=self.engine.run_reconciliation, daemon=True).start()
        messagebox.showinfo(APP_TITLE, "Mapping saved. Excel files are being updated.")

    # -- actions -----------------------------------------------------------

    def _browse_txt_folder(self):
        folder = filedialog.askdirectory(initialdir=self.txt_folder_var.get() or "C:\\")
        if not folder:
            return
        self.txt_folder_var.set(folder)
        self.config_obj.txt_root = folder
        self.config_obj.save()
        # The watcher only reacts to NEW filesystem events; files already
        # sitting in the newly-selected folder need an explicit scan to be
        # picked up. Also re-point the watcher (if running) at the new folder.
        was_running = self.watcher.is_running()
        if was_running:
            self.watcher.stop()
        threading.Thread(
            target=self._rescan_and_restart_watcher, args=(was_running,), daemon=True
        ).start()

    def _rescan_and_restart_watcher(self, restart_watcher):
        self.engine.run_reconciliation()
        if restart_watcher:
            try:
                self.watcher.start()
            except FileNotFoundError:
                pass

    def _browse_excel_folder(self):
        folder = filedialog.askdirectory(initialdir=self.excel_folder_var.get() or "C:\\")
        if not folder:
            return
        self.excel_folder_var.set(folder)
        self.config_obj.excel_root = folder
        self.config_obj.save()
        threading.Thread(target=self.engine.regenerate_all_excel, daemon=True).start()

    def _toggle_startup(self):
        enabled = self.startup_var.get()
        self.config_obj.set("auto_start", enabled)
        self.config_obj.save()
        exe_path = sys.executable if getattr(sys, "frozen", False) else os.path.abspath(sys.argv[0])
        _set_windows_startup(enabled, exe_path)

    def _start_initial_scan_async(self):
        threading.Thread(target=self.engine.run_initial_scan, daemon=True).start()

    def _start_watcher_only(self):
        """Start the filesystem watcher without an extra reconciliation pass -
        used at startup, where _start_initial_scan_async() already covers it."""
        try:
            self.watcher.start()
            self.status_label.configure(text="● RUNNING", text_color="green")
        except FileNotFoundError as exc:
            self.status_label.configure(text="● STOPPED", text_color="red")
            messagebox.showerror(APP_TITLE, str(exc))

    def _start_sync(self):
        try:
            self.watcher.start()
            self.status_label.configure(text="● RUNNING", text_color="green")
            # Cover any file created/edited/deleted while the watcher was stopped
            # (or before the folder was pointed here in the first place).
            threading.Thread(target=self.engine.run_reconciliation, daemon=True).start()
        except FileNotFoundError as exc:
            messagebox.showerror(APP_TITLE, str(exc))

    def _stop_sync(self):
        self.watcher.stop()
        self.status_label.configure(text="● STOPPED", text_color="red")

    def _sync_now(self):
        threading.Thread(target=self.engine.run_reconciliation, daemon=True).start()

    def _startfile(self, path):
        """os.startfile() wrapped so a failure is surfaced to the user instead
        of vanishing silently - the --windowed build has no console, so an
        unhandled exception here would otherwise just make the button appear
        to do nothing."""
        try:
            os.startfile(path)  # noqa: S606 - user-initiated open of their own file
        except OSError as exc:
            logger.error("Failed to open %s: %s", path, exc)
            messagebox.showerror(APP_TITLE, f"Could not open:\n{path}\n\n{exc}")

    def _open_excel_folder(self):
        path = self.config_obj.excel_root
        if os.path.isdir(path):
            self._startfile(path)
        else:
            messagebox.showinfo(APP_TITLE, "Excel folder does not exist yet.")

    def _open_txt_folder(self):
        path = self.config_obj.txt_root
        if os.path.isdir(path):
            self._startfile(path)
        else:
            messagebox.showinfo(APP_TITLE, "TXT folder does not exist.")

    def _on_row_double_click(self, _event):
        """Open the double-clicked feed's Excel workbook."""
        selection = self.tree.selection()
        if not selection:
            return
        excel_file = self.tree.item(selection[0], "values")[2]
        path = os.path.join(self.config_obj.excel_root, excel_file)
        if os.path.exists(path):
            self._startfile(path)
        else:
            messagebox.showinfo(APP_TITLE, f"{excel_file} has not been generated yet.")

    def _on_engine_event(self, message):
        self._log_queue.put(message)

    def _on_close(self):
        self.watcher.stop()
        self.db.close()
        self.destroy()

    # -- refresh loop --------------------------------------------------------

    def _periodic_refresh(self):
        self._maybe_auto_clear_log()
        self._drain_log_queue()
        self._refresh_stats()
        self._refresh_file_list()
        self._retry_pending_excel()
        self._maybe_run_background_scan()
        self.after(REFRESH_MS, self._periodic_refresh)

    def _maybe_run_background_scan(self):
        """Safety-net reconciliation so sync stays automatic even if a single
        filesystem-change notification is ever missed (e.g. how some ticker
        software writes files, or a flaky network TXT folder) - the user should
        never have to press SYNC NOW for normal operation."""
        if not self.watcher.is_running() or self._background_scan_in_progress:
            return
        if time.monotonic() - self._last_background_scan < BACKGROUND_SCAN_SECONDS:
            return
        self._last_background_scan = time.monotonic()
        self._background_scan_in_progress = True

        def _run():
            try:
                self.engine.run_full_scan(reason="Background scan", silent=True)
            finally:
                self._background_scan_in_progress = False

        threading.Thread(target=_run, daemon=True).start()

    def _maybe_auto_clear_log(self):
        """Clear the on-screen activity log every LOG_AUTO_CLEAR_SECONDS so it
        stays readable during 24/7 use. The rotating file log (logs/app.log)
        is untouched - this only resets what's shown in the GUI panel."""
        if time.monotonic() - self._log_cleared_at < LOG_AUTO_CLEAR_SECONDS:
            return
        self.log_box.configure(state="normal")
        self.log_box.delete("1.0", "end")
        self.log_box.configure(state="disabled")
        self._log_cleared_at = time.monotonic()
        self._log_queue.put(f"— Activity log auto-cleared at {now_str()} (refreshes every 2 hours) —")

    def _retry_pending_excel(self):
        """If a previous write failed because Excel had a workbook open, keep
        retrying in the background so it catches up as soon as it's closed -
        without requiring the user to touch another TXT file first."""
        if not self.engine.excel_pending or self._excel_retry_in_progress:
            return
        self._excel_retry_in_progress = True

        def _run():
            try:
                self.engine.retry_pending_excel()
            finally:
                self._excel_retry_in_progress = False

        threading.Thread(target=_run, daemon=True).start()

    @staticmethod
    def _tag_for_message(message):
        if message.startswith(("✓", "+")):
            return "added"
        if message.startswith(("✗", "−")):
            return "removed"
        if message.startswith(("↻", "~")):
            return "modified"
        return None

    def _drain_log_queue(self):
        drained = False
        self.log_box.configure(state="normal")
        while True:
            try:
                message = self._log_queue.get_nowait()
            except queue.Empty:
                break
            timestamp = now_str().split(" ")[1]
            self.log_box.insert("end", f"{timestamp} {message}\n", self._tag_for_message(message))
            drained = True
        self.log_box.configure(state="disabled")
        if drained:
            self.log_box.see("end")
            self.last_sync_label.configure(text=f"Last Sync: {now_str()}")

    def _refresh_stats(self):
        stats = self.db.stats()
        self.stat_total.configure(text=f"Feeds Synced: {stats['total_files']}")
        self.stat_news_items.configure(text=f"Total News Items: {stats['news_items']}")
        self.stat_pending.configure(
            text=f"Excel Pending: {'yes' if self.engine.excel_pending else 'no'}"
        )

    def _refresh_file_list(self):
        """Show one row per configured feed, whether or not its source file
        currently exists - a missing file is itself useful information."""
        query = self.search_var.get().strip().lower()
        records = {rec.feed_key: rec for rec in self.db.get_all()}

        selected = {self.tree.item(i, "values")[0] for i in self.tree.selection()}
        for item in self.tree.get_children():
            self.tree.delete(item)

        for feed in self.config_obj.feeds:
            haystack = f"{feed.label} {feed.txt_file} {feed.excel_file}".lower()
            if query and query not in haystack:
                continue
            rec = records.get(feed.key)
            pending = self.engine.is_feed_pending(feed.key)
            status = "🔒 Excel open - pending" if pending else "✓ Synced"
            item_id = self.tree.insert(
                "", "end",
                values=(
                    feed.label,
                    feed.txt_file,
                    feed.excel_file,
                    len(rec.news_lines) if rec else "—",
                    rec.modified_at if rec else "file not found",
                    status,
                ),
                tags=("pending" if pending else "synced",),
            )
            if feed.label in selected:
                self.tree.selection_add(item_id)


def run_app(config):
    app = App(config)
    app.mainloop()
