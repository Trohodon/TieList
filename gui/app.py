# gui/app.py

import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from core import processor  # uses core/processor.py


class TieDataApp(tk.Tk):
    """
    Main GUI window for the Tie List processing tool.
    """

    def __init__(self):
        super().__init__()

        self.title("Tie List Processor")
        self.geometry("900x600")

        self.main_folder_var = tk.StringVar()
        self.dry_run_var = tk.BooleanVar(value=True)

        self._build_gui()

    # ---------- GUI layout ----------

    def _build_gui(self):
        # Top frame: folder selection + dry run
        top_frame = ttk.Frame(self)
        top_frame.pack(fill="x", padx=10, pady=10)

        ttk.Label(top_frame, text="Main folder (e.g. DataForTieList):").grid(
            row=0, column=0, sticky="w"
        )

        entry = ttk.Entry(top_frame, textvariable=self.main_folder_var, width=70)
        entry.grid(row=1, column=0, padx=(0, 5), sticky="we")

        browse_btn = ttk.Button(top_frame, text="Browse...", command=self.browse_folder)
        browse_btn.grid(row=1, column=1, sticky="e")

        dry_check = ttk.Checkbutton(
            top_frame,
            text="Dry run (no output files, just compute & log)",
            variable=self.dry_run_var,
        )
        dry_check.grid(row=2, column=0, columnspan=2, pady=(5, 0), sticky="w")

        # Buttons frame
        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill="x", padx=10, pady=(0, 10))

        ttk.Button(
            btn_frame, text="Run TEST (single subfolder)", command=self.run_single_folder
        ).pack(side="left", padx=(0, 5))

        ttk.Button(
            btn_frame, text="Run ALL subfolders", command=self.run_all_folders
        ).pack(side="left", padx=(0, 5))

        ttk.Button(btn_frame, text="Clear Log", command=self.clear_log).pack(
            side="right"
        )

        # Log text box with scrollbars
        log_frame = ttk.Frame(self)
        log_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        self.log_text = tk.Text(log_frame, wrap="none")
        self.log_text.pack(side="left", fill="both", expand=True)

        y_scroll = ttk.Scrollbar(
            log_frame, orient="vertical", command=self.log_text.yview
        )
        y_scroll.pack(side="right", fill="y")
        self.log_text.configure(yscrollcommand=y_scroll.set)

        x_scroll = ttk.Scrollbar(
            self, orient="horizontal", command=self.log_text.xview
        )
        x_scroll.pack(fill="x", padx=10, pady=(0, 10))
        self.log_text.configure(xscrollcommand=x_scroll.set)

    # ---------- Helper methods ----------

    def browse_folder(self):
        folder = filedialog.askdirectory(title="Select main data folder")
        if folder:
            self.main_folder_var.set(folder)

    def clear_log(self):
        self.log_text.delete("1.0", tk.END)

    def append_log(self, text: str):
        self.log_text.insert(tk.END, text + "\n")
        self.log_text.see(tk.END)

    def _get_main_folder_checked(self):
        folder = self.main_folder_var.get().strip()
        if not folder:
            messagebox.showwarning("Missing folder", "Please select a main folder.")
            return None
        if not os.path.isdir(folder):
            messagebox.showerror("Invalid folder", f"Folder not found:\n{folder}")
            return None
        return folder

    # ---------- Actions ----------

    def run_single_folder(self):
        """
        Test mode: user picks ONE secondary folder under the main folder.
        """
        main_folder = self._get_main_folder_checked()
        if not main_folder:
            return

        # Find all subfolders under the main folder.
        subfolders = processor.find_subfolders(main_folder)
        if not subfolders:
            messagebox.showerror(
                "No subfolders",
                "No secondary folders were found under the main folder.",
            )
            return

        # Let user choose the specific test folder.
        test_folder = filedialog.askdirectory(
            title="Select ONE secondary folder to test", initialdir=main_folder
        )
        if not test_folder:
            return

        dry = self.dry_run_var.get()
        self.append_log(
            f"=== TEST RUN on single subfolder ===\nDry run = {dry}\nFolder = {test_folder}\n"
        )

        log_text, _ = processor.process_single_subfolder(test_folder, dry_run=dry)
        self.append_log(log_text)
        self.append_log("\n")

    def run_all_folders(self):
        """
        Full run: process every secondary folder under the main folder.
        """
        main_folder = self._get_main_folder_checked()
        if not main_folder:
            return

        dry = self.dry_run_var.get()
        self.append_log(f"=== RUN ALL SUBFOLDERS ===\nDry run = {dry}\n")

        log_text = processor.process_all_subfolders(main_folder, dry_run=dry)
        self.append_log(log_text)
        self.append_log("\n")
