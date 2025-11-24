# app.py

import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from core import processor  # core/processor.py


class TieDataApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Tie List Processor v2.0")
        self.geometry("1200x700")

        self.main_folder_var = tk.StringVar()
        self.output_folder_var = tk.StringVar()
        self.dry_run_var = tk.BooleanVar(value=True)
        self.prefer_updates_var = tk.BooleanVar(value=True)
        self.mode_var = tk.StringVar(value="single")  # 'single' or 'all'

        self.status_var = tk.StringVar(value="Ready")

        self._build_gui()

    # ---------- GUI layout ----------

    def _build_gui(self):
        style = ttk.Style(self)
        style.configure("Run.TButton", font=("TkDefaultFont", 11, "bold"), padding=8)

        # Top: folder selection
        top_frame = ttk.Frame(self)
        top_frame.pack(fill="x", padx=10, pady=(10, 5))

        ttk.Label(top_frame, text="Main folder (e.g. DataForTieList):").grid(
            row=0, column=0, columnspan=3, sticky="w"
        )

        main_entry = ttk.Entry(top_frame, textvariable=self.main_folder_var, width=80)
        main_entry.grid(row=1, column=0, padx=(0, 5), sticky="we")

        ttk.Button(top_frame, text="Browse...", command=self.browse_main_folder).grid(
            row=1, column=1, sticky="e"
        )

        ttk.Button(
            top_frame, text="Refresh tree", command=self.refresh_tree
        ).grid(row=1, column=2, padx=(5, 0), sticky="e")

        ttk.Label(top_frame, text="Output folder (for CSV results):").grid(
            row=2, column=0, columnspan=3, sticky="w", pady=(8, 0)
        )

        out_entry = ttk.Entry(top_frame, textvariable=self.output_folder_var, width=80)
        out_entry.grid(row=3, column=0, padx=(0, 5), sticky="we")

        ttk.Button(
            top_frame, text="Browse...", command=self.browse_output_folder
        ).grid(row=3, column=1, sticky="e")

        ttk.Label(
            top_frame,
            text="(If empty, results will go into a 'TieListResults' folder under the main folder when Dry run is OFF.)",
            foreground="gray",
        ).grid(row=4, column=0, columnspan=3, sticky="w", pady=(2, 0))

        top_frame.columnconfigure(0, weight=1)

        # Options (dry run, prefer updates, mode)
        opt_frame = ttk.Frame(self)
        opt_frame.pack(fill="x", padx=10, pady=(5, 5))

        ttk.Checkbutton(
            opt_frame,
            text="Dry run (no output files, just compute & log)",
            variable=self.dry_run_var,
            command=self.on_options_changed,
        ).grid(row=0, column=0, sticky="w")

        ttk.Checkbutton(
            opt_frame,
            text="Prefer '*_update.csv' files over base",
            variable=self.prefer_updates_var,
            command=self.on_options_changed,
        ).grid(row=0, column=1, padx=(15, 0), sticky="w")

        mode_frame = ttk.Frame(opt_frame)
        mode_frame.grid(row=0, column=2, padx=(30, 0), sticky="e")

        ttk.Label(mode_frame, text="Mode:").pack(side="left")
        ttk.Radiobutton(
            mode_frame,
            text="Test single subfolder",
            variable=self.mode_var,
            value="single",
        ).pack(side="left", padx=(5, 0))
        ttk.Radiobutton(
            mode_frame,
            text="All subfolders",
            variable=self.mode_var,
            value="all",
        ).pack(side="left", padx=(5, 0))

        # Run / log buttons + progress bar
        btn_frame = ttk.Frame(self)
        btn_frame.pack(fill="x", padx=10, pady=(0, 5))

        run_btn = ttk.Button(
            btn_frame,
            text="Run Processing",
            style="Run.TButton",
            command=self.run_processing,
        )
        run_btn.pack(side="left")

        self.progress = ttk.Progressbar(
            btn_frame, orient="horizontal", mode="determinate", length=300
        )
        self.progress.pack(side="left", padx=(15, 0), fill="x", expand=True)

        ttk.Button(btn_frame, text="Save Log...", command=self.save_log).pack(
            side="right"
        )
        ttk.Button(btn_frame, text="Clear Log", command=self.clear_log).pack(
            side="right", padx=(0, 5)
        )

        # Middle area: folder tree (left) + log (right)
        middle = ttk.Frame(self)
        middle.pack(fill="both", expand=True, padx=10, pady=(5, 10))

        # Folder tree
        tree_frame = ttk.Frame(middle)
        tree_frame.pack(side="left", fill="y", padx=(0, 5), pady=0)

        ttk.Label(tree_frame, text="Folder contents (using current settings)").pack(
            anchor="w"
        )

        self.folder_tree = ttk.Treeview(tree_frame, show="tree", height=25)
        self.folder_tree.pack(side="left", fill="y", expand=False)

        tree_scroll = ttk.Scrollbar(
            tree_frame, orient="vertical", command=self.folder_tree.yview
        )
        tree_scroll.pack(side="right", fill="y")
        self.folder_tree.configure(yscrollcommand=tree_scroll.set)

        # Log text
        log_frame = ttk.Frame(middle)
        log_frame.pack(side="right", fill="both", expand=True)

        ttk.Label(log_frame, text="Run log / results").pack(anchor="w")

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
        x_scroll.pack(fill="x", padx=10, pady=(0, 5))
        self.log_text.configure(xscrollcommand=x_scroll.set)

        # Color tags for log
        self.log_text.tag_config(
            "header", foreground="blue", font=("TkDefaultFont", 10, "bold")
        )
        self.log_text.tag_config("warning", foreground="red")
        self.log_text.tag_config("line", foreground="darkgreen")
        self.log_text.tag_config("status", foreground="purple")

        # Status bar
        status_frame = ttk.Frame(self)
        status_frame.pack(fill="x", padx=10, pady=(0, 5))
        ttk.Label(status_frame, textvariable=self.status_var, anchor="w").pack(
            fill="x"
        )

    # ---------- Helper methods ----------

    def browse_main_folder(self):
        folder = filedialog.askdirectory(title="Select DataForTieList folder")
        if folder:
            self.main_folder_var.set(folder)
            self.refresh_tree()
            # default output folder suggestion
            tie_res = os.path.join(folder, "TieListResults")
            self.output_folder_var.set(tie_res)

    def browse_output_folder(self):
        folder = filedialog.askdirectory(title="Select output folder")
        if folder:
            self.output_folder_var.set(folder)

    def _get_main_folder_if_exists(self):
        folder = self.main_folder_var.get().strip()
        if not folder or not os.path.isdir(folder):
            return None
        return folder

    def _get_main_folder_checked(self):
        folder = self._get_main_folder_if_exists()
        if folder is None:
            messagebox.showwarning("Missing folder", "Please select a valid main folder.")
        return folder

    def _resolve_output_folder(self, main_folder: str, dry: bool):
        """
        Decide where CSV results should be written.
        Returns None when dry run is ON or when folder can't be created.
        """
        if dry:
            return None

        folder = self.output_folder_var.get().strip()
        if not folder:
            folder = os.path.join(main_folder, "TieListResults")

        try:
            os.makedirs(folder, exist_ok=True)
        except Exception as e:
            messagebox.showerror(
                "Output folder error",
                f"Could not create or access output folder:\n{folder}\n\n{e}",
            )
            return None

        return folder

    def clear_log(self):
        self.log_text.delete("1.0", tk.END)

    def append_log(self, text: str):
        # Color-coded insertion line by line
        for line in text.splitlines():
            tag = None
            if line.startswith("====="):
                tag = "header"
            elif line.startswith("   !") or "No Hr01–Hr24" in line:
                tag = "warning"
            elif line.startswith("Line:"):
                tag = "line"
            elif line.startswith("Dry run") or "complete" in line:
                tag = "status"

            if tag:
                self.log_text.insert(tk.END, line + "\n", tag)
            else:
                self.log_text.insert(tk.END, line + "\n")
        self.log_text.see(tk.END)

    def save_log(self):
        content = self.log_text.get("1.0", tk.END).strip()
        if not content:
            messagebox.showinfo("Save Log", "Log is empty, nothing to save.")
            return

        path = filedialog.asksaveasfilename(
            title="Save log as",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
        )
        if not path:
            return

        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            messagebox.showinfo("Save Log", f"Log saved to:\n{path}")
        except Exception as e:
            messagebox.showerror("Save Log", f"Failed to save log:\n{e}")

    def refresh_tree(self):
        folder = self._get_main_folder_if_exists()

        # Clear tree either way
        for item in self.folder_tree.get_children():
            self.folder_tree.delete(item)

        if not folder:
            return

        root_label = os.path.basename(folder.rstrip("/\\")) or folder
        root_id = self.folder_tree.insert("", "end", text=root_label, open=True)

        prefer_updates = self.prefer_updates_var.get()
        subfolders = processor.find_subfolders(folder)
        for sub in subfolders:
            sub_name = os.path.basename(sub.rstrip("/\\"))
            sub_id = self.folder_tree.insert(root_id, "end", text=sub_name, open=False)

            csv_files = processor.choose_csv_files(sub, prefer_updates=prefer_updates)
            for p in csv_files:
                self.folder_tree.insert(
                    sub_id, "end", text=os.path.basename(p), open=False
                )

    def on_options_changed(self):
        # updating the tree is the only visual change needed
        self.refresh_tree()

    # ---------- Actions ----------

    def run_processing(self):
        main_folder = self._get_main_folder_checked()
        if not main_folder:
            return

        dry = self.dry_run_var.get()
        prefer_updates = self.prefer_updates_var.get()
        mode = self.mode_var.get()
        output_folder = self._resolve_output_folder(main_folder, dry)

        self.clear_progress()
        self.status_var.set("Running...")
        self.update_idletasks()

        if mode == "single":
            self.run_single_folder(main_folder, dry, prefer_updates, output_folder)
        else:
            self.run_all_folders(main_folder, dry, prefer_updates, output_folder)

        if dry:
            self.status_var.set("Done (dry run).")
        else:
            self.status_var.set("Done (results written if data was found).")

    def clear_progress(self):
        self.progress["value"] = 0
        self.progress["maximum"] = 1

    def run_single_folder(
        self, main_folder: str, dry: bool, prefer_updates: bool, output_folder: str | None
    ):
        # Let the user pick ONE subfolder
        subfolders = processor.find_subfolders(main_folder)
        if not subfolders:
            messagebox.showerror(
                "No subfolders", "No secondary folders were found under the main one."
