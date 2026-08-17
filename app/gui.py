"""CustomTkinter desktop GUI for TXT Row to Excel Sync."""
import logging
import os
import queue
import sys
import threading

import customtkinter as ctk
from tkinter import filedialog, messagebox, ttk

from app.database import Database
from app.models import STATUS_ACTIVE, STATUS_DELETED
from app.sync_engine import SyncEngine
from app.utils import now_str
from app.watcher import FolderWatcher

logger = logging.getLogger("word_to_excel_sync")

APP_TITLE = "TXT Row to Excel Sync"
REFRESH_MS = 2000

STARTUP_REGISTRY_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
STARTUP_VALUE_NAME = "TxtRowToExcelSync"


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
        self.geometry("1050x820")

        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")

        self.db = Database(self.config_obj.database_file)
        self.engine = SyncEngine(self.db, self.config_obj)
        self.engine.on_event = self._on_engine_event
        self.watcher = FolderWatcher(self.engine)

        self._log_queue = queue.Queue()
        self._excel_retry_in_progress = False
        self._mapping_window = None
        self._mapping_entries = {}

        self._build_ui()
        self._start_initial_scan_async()
        self.after(REFRESH_MS, self._periodic_refresh)

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # -- UI construction -------------------------------------------------------

    def _build_ui(self):
        pad = {"padx": 10, "pady": 6}

        header = ctk.CTkLabel(self, text="TXT ROW TO EXCEL SYNC", font=ctk.CTkFont(size=20, weight="bold"))
        header.pack(fill="x", **pad)

        paths_frame = ctk.CTkFrame(self)
        paths_frame.pack(fill="x", **pad)

        ctk.CTkLabel(paths_frame, text="TXT Folder:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        self.txt_folder_var = ctk.StringVar(value=self.config_obj.txt_root)
        ctk.CTkEntry(paths_frame, textvariable=self.txt_folder_var, width=500).grid(row=0, column=1, padx=5, pady=5)
        ctk.CTkButton(paths_frame, text="Browse", command=self._browse_txt_folder).grid(row=0, column=2, padx=5, pady=5)

        ctk.CTkLabel(paths_frame, text="Excel File:").grid(row=1, column=0, sticky="w", padx=5, pady=5)
        self.excel_file_var = ctk.StringVar(value=self.config_obj.excel_file)
        ctk.CTkEntry(paths_frame, textvariable=self.excel_file_var, width=500).grid(row=1, column=1, padx=5, pady=5)
        ctk.CTkButton(paths_frame, text="Browse", command=self._browse_excel_file).grid(row=1, column=2, padx=5, pady=5)

        self.startup_var = ctk.BooleanVar(value=self.config_obj.get("auto_start", False))
        ctk.CTkCheckBox(
            paths_frame, text="Start automatically with Windows",
            variable=self.startup_var, command=self._toggle_startup,
        ).grid(row=2, column=0, columnspan=3, sticky="w", padx=5, pady=5)

        status_frame = ctk.CTkFrame(self)
        status_frame.pack(fill="x", **pad)

        self.status_label = ctk.CTkLabel(status_frame, text="● STOPPED", text_color="red",
                                          font=ctk.CTkFont(size=14, weight="bold"))
        self.status_label.pack(side="left", padx=10, pady=8)

        self.last_sync_label = ctk.CTkLabel(status_frame, text="Last Sync: -")
        self.last_sync_label.pack(side="left", padx=20, pady=8)

        stats_frame = ctk.CTkFrame(self)
        stats_frame.pack(fill="x", **pad)
        self.stat_total = ctk.CTkLabel(stats_frame, text="Total Files: 0")
        self.stat_active = ctk.CTkLabel(stats_frame, text="Active: 0")
        self.stat_deleted = ctk.CTkLabel(stats_frame, text="Deleted: 0")
        self.stat_lines = ctk.CTkLabel(stats_frame, text="Hindi Lines: 0")
        for w in (self.stat_total, self.stat_active, self.stat_deleted, self.stat_lines):
            w.pack(side="left", padx=15, pady=8)

        buttons_frame = ctk.CTkFrame(self)
        buttons_frame.pack(fill="x", **pad)
        ctk.CTkButton(buttons_frame, text="START SYNC", command=self._start_sync).pack(side="left", padx=5, pady=8)
        ctk.CTkButton(buttons_frame, text="STOP SYNC", command=self._stop_sync).pack(side="left", padx=5, pady=8)
        ctk.CTkButton(buttons_frame, text="SYNC NOW", command=self._sync_now).pack(side="left", padx=5, pady=8)
        ctk.CTkButton(buttons_frame, text="OPEN EXCEL", command=self._open_excel).pack(side="left", padx=5, pady=8)
        ctk.CTkButton(buttons_frame, text="OPEN TXT FOLDER", command=self._open_txt_folder).pack(side="left", padx=5, pady=8)
        ctk.CTkButton(buttons_frame, text="ROW / CATEGORY MAPPING", command=self._open_mapping_editor).pack(
            side="left", padx=5, pady=8
        )

        search_frame = ctk.CTkFrame(self)
        search_frame.pack(fill="x", **pad)
        ctk.CTkLabel(search_frame, text="Search:").pack(side="left", padx=5)
        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", lambda *_: self._refresh_file_list())
        ctk.CTkEntry(search_frame, textvariable=self.search_var, width=200).pack(side="left", padx=5)

        ctk.CTkLabel(search_frame, text="Status:").pack(side="left", padx=(20, 5))
        self.filter_var = ctk.StringVar(value="All")
        ctk.CTkOptionMenu(
            search_frame, values=["All", "Active", "Deleted"], variable=self.filter_var,
            command=lambda _v: self._refresh_file_list(),
        ).pack(side="left", padx=5)

        list_frame = ctk.CTkFrame(self)
        list_frame.pack(fill="both", expand=True, **pad)
        columns = ("serial", "category", "file_name", "status", "modified")
        self.tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=8)
        for col, label, width in (
            ("serial", "Serial No.", 80), ("category", "Category", 180),
            ("file_name", "File Name", 140), ("status", "Status", 90),
            ("modified", "Modified At", 180),
        ):
            self.tree.heading(col, text=label)
            self.tree.column(col, width=width)
        self.tree.pack(fill="both", expand=True, side="left")
        self.tree.bind("<Double-1>", self._on_row_double_click)
        scrollbar = ttk.Scrollbar(list_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")

        log_label = ctk.CTkLabel(self, text="ACTIVITY LOG", font=ctk.CTkFont(weight="bold"))
        log_label.pack(anchor="w", padx=10)
        self.log_box = ctk.CTkTextbox(self, height=160)
        self.log_box.pack(fill="both", expand=False, **pad)
        self.log_box.configure(state="disabled")

    # -- Row/Category mapping editor -----------------------------------------

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
            dialog, text="Enter password to access Row/Category Mapping:", wraplength=300
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
        win.title("Row / Category Mapping")
        win.geometry("480x560")
        self._mapping_window = win

        ctk.CTkLabel(win, text="Row / Category Mapping", font=ctk.CTkFont(size=16, weight="bold")).pack(
            padx=10, pady=(10, 5)
        )
        ctk.CTkLabel(
            win, text="row_XX.txt -> Serial No. XX. Edit the category name for each row.",
            wraplength=440, justify="left",
        ).pack(padx=10, pady=(0, 10))

        scroll = ctk.CTkScrollableFrame(win, width=440, height=380)
        scroll.pack(fill="both", expand=True, padx=10, pady=5)

        self._mapping_entries = {}
        self._mapping_scroll_frame = scroll
        row_categories = self.config_obj.row_categories
        for row_number in sorted((int(k) for k in row_categories.keys())):
            self._add_mapping_row(row_number, row_categories[str(row_number)])

        add_frame = ctk.CTkFrame(win)
        add_frame.pack(fill="x", padx=10, pady=(0, 5))
        ctk.CTkLabel(add_frame, text="Add Row No.:").pack(side="left", padx=5)
        new_row_var = ctk.StringVar()
        ctk.CTkEntry(add_frame, textvariable=new_row_var, width=60).pack(side="left", padx=5)
        new_cat_var = ctk.StringVar()
        ctk.CTkEntry(add_frame, textvariable=new_cat_var, width=180, placeholder_text="Category name").pack(
            side="left", padx=5
        )

        def _add_new_row():
            try:
                row_number = int(new_row_var.get().strip())
            except ValueError:
                messagebox.showerror(APP_TITLE, "Row number must be an integer.")
                return
            if row_number in self._mapping_entries:
                messagebox.showerror(APP_TITLE, f"Row {row_number} already exists.")
                return
            self._add_mapping_row(row_number, new_cat_var.get().strip() or "Unassigned")
            new_row_var.set("")
            new_cat_var.set("")

        ctk.CTkButton(add_frame, text="Add", command=_add_new_row, width=60).pack(side="left", padx=5)

        button_frame = ctk.CTkFrame(win)
        button_frame.pack(fill="x", padx=10, pady=10)
        ctk.CTkButton(button_frame, text="Save Mapping", command=self._save_mapping).pack(side="left", padx=5)
        ctk.CTkButton(button_frame, text="Close", command=win.destroy).pack(side="left", padx=5)

    def _add_mapping_row(self, row_number, category_name):
        row_frame = ctk.CTkFrame(self._mapping_scroll_frame)
        row_frame.pack(fill="x", pady=2)
        ctk.CTkLabel(row_frame, text=f"Row {row_number:02d} \u2192", width=90).pack(side="left", padx=5)
        var = ctk.StringVar(value=category_name)
        ctk.CTkEntry(row_frame, textvariable=var, width=260).pack(side="left", padx=5)
        self._mapping_entries[row_number] = var

    def _save_mapping(self):
        for row_number, var in self._mapping_entries.items():
            self.config_obj.set_category(row_number, var.get().strip() or "Unassigned")
        self.config_obj.save()
        threading.Thread(target=self.engine.refresh_categories, daemon=True).start()
        messagebox.showinfo(APP_TITLE, "Mapping saved. Excel is being updated.")

    # -- actions -----------------------------------------------------------

    def _browse_txt_folder(self):
        folder = filedialog.askdirectory(initialdir=self.txt_folder_var.get() or "C:\\")
        if folder:
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

    def _browse_excel_file(self):
        path = filedialog.asksaveasfilename(
            initialdir=os.path.dirname(self.excel_file_var.get() or "C:\\"),
            defaultextension=".xlsx", filetypes=[("Excel Workbook", "*.xlsx")],
        )
        if path:
            self.excel_file_var.set(path)
            self.config_obj.excel_file = path
            self.config_obj.save()
            threading.Thread(target=self.engine.regenerate_excel, daemon=True).start()

    def _toggle_startup(self):
        enabled = self.startup_var.get()
        self.config_obj.set("auto_start", enabled)
        self.config_obj.save()
        exe_path = sys.executable if getattr(sys, "frozen", False) else os.path.abspath(sys.argv[0])
        _set_windows_startup(enabled, exe_path)

    def _start_initial_scan_async(self):
        threading.Thread(target=self.engine.run_initial_scan, daemon=True).start()

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

    def _open_excel(self):
        path = self.config_obj.excel_file
        if os.path.exists(path):
            os.startfile(path)  # noqa: S606 - user-initiated open of their own file
        else:
            messagebox.showinfo(APP_TITLE, "Excel file has not been generated yet.")

    def _open_txt_folder(self):
        path = self.config_obj.txt_root
        if os.path.isdir(path):
            os.startfile(path)  # noqa: S606
        else:
            messagebox.showinfo(APP_TITLE, "TXT folder does not exist.")

    def _on_row_double_click(self, _event):
        selection = self.tree.selection()
        if not selection:
            return
        serial = self.tree.item(selection[0], "values")[0]
        records = self.db.get_all()
        for rec in records:
            if str(rec.serial_number) == str(serial):
                if os.path.exists(rec.full_path):
                    os.startfile(rec.full_path)  # noqa: S606
                else:
                    messagebox.showinfo(APP_TITLE, "The TXT file no longer exists on disk.")
                break

    def _on_engine_event(self, message):
        self._log_queue.put(message)

    def _on_close(self):
        self.watcher.stop()
        self.db.close()
        self.destroy()

    # -- refresh loop --------------------------------------------------------

    def _periodic_refresh(self):
        self._drain_log_queue()
        self._refresh_stats()
        self._refresh_file_list()
        self._retry_pending_excel()
        self.after(REFRESH_MS, self._periodic_refresh)

    def _retry_pending_excel(self):
        """If a previous write failed because Excel had the file open, keep retrying
        in the background so the workbook catches up as soon as it's closed -
        without requiring the user to touch another TXT file first."""
        if not self.engine.excel_pending or self._excel_retry_in_progress:
            return
        self._excel_retry_in_progress = True

        def _run():
            try:
                self.engine.regenerate_excel()
            finally:
                self._excel_retry_in_progress = False

        threading.Thread(target=_run, daemon=True).start()

    def _drain_log_queue(self):
        drained = False
        self.log_box.configure(state="normal")
        while True:
            try:
                message = self._log_queue.get_nowait()
            except queue.Empty:
                break
            timestamp = now_str().split(" ")[1]
            self.log_box.insert("end", f"{timestamp} {message}\n")
            drained = True
        self.log_box.configure(state="disabled")
        if drained:
            self.log_box.see("end")
            self.last_sync_label.configure(text=f"Last Sync: {now_str()}")

    def _refresh_stats(self):
        stats = self.db.stats()
        records = self.db.get_all(status=STATUS_ACTIVE)
        hindi_lines = sum(len(r.content.splitlines()) for r in records if r.content)
        self.stat_total.configure(text=f"Total Files: {stats['total']}")
        self.stat_active.configure(text=f"Active: {stats['active']}")
        self.stat_deleted.configure(text=f"Deleted: {stats['deleted']}")
        self.stat_lines.configure(text=f"Hindi Lines: {hindi_lines}")

    def _refresh_file_list(self):
        query = self.search_var.get().strip()
        status = self.filter_var.get()
        records = self.db.search(query, status=status) if query else self.db.get_all(status=status)

        selected_serials = {self.tree.item(i, "values")[0] for i in self.tree.selection()}
        for item in self.tree.get_children():
            self.tree.delete(item)
        for rec in records:
            item_id = self.tree.insert(
                "", "end",
                values=(rec.serial_number, rec.category, rec.file_name, rec.status, rec.modified_at),
            )
            if str(rec.serial_number) in selected_serials:
                self.tree.selection_add(item_id)


def run_app(config):
    app = App(config)
    app.mainloop()
