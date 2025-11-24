# core/processor.py

import os
import csv
from typing import Optional
from collections import defaultdict


SUPPORTED_TYPES = {"export", "import"}  # types we sum


# ============================================================
#  Helper functions
# ============================================================

def find_subfolders(main_folder: str):
    """Return sorted list of immediate subfolders."""
    subfolders = []
    with os.scandir(main_folder) as it:
        for entry in it:
            if entry.is_dir():
                subfolders.append(entry.path)
    return sorted(subfolders)


def list_csv_files(folder: str, prefer_updates: bool = True):
    """
    Return CSV list, ensuring that *_update.csv replaces its base file.
    Example:
        MonthlyDEC_202401.csv
        MonthlyDEC_202401_update.csv  -> this one overrides the original.
    """
    normal_files = {}
    update_files = {}

    with os.scandir(folder) as it:
        for entry in it:
            if not entry.is_file():
                continue
            name = entry.name.lower()
            if not name.endswith(".csv"):
                continue

            full_path = entry.path
            if "_update" in name:
                base = name.replace("_update", "")
                update_files[base] = full_path
            else:
                normal_files[name] = full_path

    # Build final list
    final = []

    for base_name, base_path in normal_files.items():
        if prefer_updates:
            # If an updated version exists, use that
            if base_name in update_files:
                final.append(update_files[base_name])
            else:
                final.append(base_path)
        else:
            # Always use the base file unless user disabled update preference
            final.append(base_path)

    # Include update-only files that had no base version
    if prefer_updates:
        for base_name, upd_path in update_files.items():
            if base_name not in normal_files:
                final.append(upd_path)

    return sorted(final)


def _find_hour_indices(header_row):
    """Return the indices of Hr01–Hr24 columns."""
    hour_cols = []
    for idx, name in enumerate(header_row):
        if not name:
            continue
        s = str(name).strip().lower()
        if s.startswith("hr"):
            hour_cols.append(idx)
    return hour_cols


def _locate_header_and_hours(rows):
    """Find row containing Hr01-Hr24 header."""
    for i, row in enumerate(rows):
        hour_cols = _find_hour_indices(row)
        if hour_cols:
            return i, hour_cols
    return -1, []


def _find_name_col(header_row):
    """Find column containing line/tie name."""
    keywords = ("name", "line", "tie")
    for idx, cell in enumerate(header_row):
        if not cell:
            continue
        t = str(cell).strip().lower()
        if any(k in t for k in keywords):
            return idx
    return None


# ============================================================
#   CSV Processing
# ============================================================

def process_csv_file(csv_path: str):
    """
    Processes one monthly CSV.
    Returns:
      { line_name : { 'Export': total, 'Import': total } }
    """
    results = defaultdict(lambda: defaultdict(float))

    with open(csv_path, "r", newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        rows = list(reader)

    if not rows:
        return {}

    header_index, hour_cols = _locate_header_and_hours(rows)
    if header_index < 0 or not hour_cols:
        return {}

    header = rows[header_index]
    name_col_idx = _find_name_col(header)

    data_rows = rows[header_index + 1:]

    current_line_name = ""
    flow_col_index = None

    for row in data_rows:
        if not row:
            continue

        # detect Export/Import column dynamically
        if flow_col_index is None:
            for idx, cell in enumerate(row):
                val = str(cell).strip().lower()
                if val in SUPPORTED_TYPES:
                    flow_col_index = idx
                    break

        if flow_col_index is None or flow_col_index >= len(row):
            continue

        raw_flow = str(row[flow_col_index]).strip()
        if not raw_flow:
            continue

        flow_lower = raw_flow.lower()
        if flow_lower not in SUPPORTED_TYPES:
            continue

        # line name column detection
        if name_col_idx is not None and name_col_idx < len(row):
            line_name_cell = str(row[name_col_idx]).strip()
        else:
            fallback_idx = flow_col_index + 2
            if fallback_idx < len(row):
                line_name_cell = str(row[fallback_idx]).strip()
            else:
                line_name_cell = ""

        if line_name_cell:
            current_line_name = line_name_cell

        if not current_line_name:
            continue

        # sum hours
        total = 0.0
        for h_idx in hour_cols:
            if h_idx >= len(row):
                continue
            cell = str(row[h_idx]).strip()
            if cell == "":
                continue
            try:
                total += float(cell)
            except ValueError:
                continue

        results[current_line_name][raw_flow.capitalize()] += total

    return results


def merge_results(all_results):
    """Merge per-month dicts into a full-year dict."""
    yearly = defaultdict(lambda: defaultdict(float))
    for res in all_results:
        for line, type_dict in res.items():
            for flow, val in type_dict.items():
                yearly[line][flow] += val
    return yearly


def format_results_as_text(yearly, folder_label):
    """Format readable results text."""
    out = [f"===== Results for {folder_label} ====="]
    if not yearly:
        out.append("  (No data found – check headers or CSV format.)")
        return "\n".join(out)

    for line_name in sorted(yearly):
        type_dict = yearly[line_name]
        exp = type_dict.get("Export", 0)
        imp = type_dict.get("Import", 0)
        out.append(f"Line: {line_name}")
        out.append(f"    Export total (Hr01–Hr24 full year): {exp}")
        out.append(f"    Import total (Hr01–Hr24 full year): {imp}")
    out.append("")
    return "\n".join(out)


# ============================================================
#   Subfolder Processing
# ============================================================

def process_single_subfolder(
    subfolder_path: str,
    dry_run: bool = True,
    prefer_updates: bool = True,
    output_folder: Optional[str] = None,
):
    """
    Process a single monthly folder.
    """
    folder_name = os.path.basename(subfolder_path.rstrip("/\\"))
    csv_files = list_csv_files(subfolder_path, prefer_updates=prefer_updates)

    log_lines = [f"Processing subfolder: {folder_name}",
                 f"Found {len(csv_files)} CSV files:"]

    for c in csv_files:
        log_lines.append(f"  - {os.path.basename(c)}")

    monthly_res = []
    for csv_path in csv_files:
        res = process_csv_file(csv_path)
        if not res:
            log_lines.append(
                f"  ! Warning: No Hr01–Hr24 or no Export/Import rows in: "
                f"{os.path.basename(csv_path)}"
            )
        monthly_res.append(res)

    yearly = merge_results(monthly_res)
    log_lines.append("")
    log_lines.append(format_results_as_text(yearly, folder_name))

    # Write output if not dry-run
    if not dry_run and output_folder:
        os.makedirs(output_folder, exist_ok=True)
        outpath = os.path.join(output_folder, f"{folder_name}_RESULTS.csv")
        with open(outpath, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["Line Name", "Export Total", "Import Total"])
            for line_name, td in yearly.items():
                w.writerow([line_name, td.get("Export", 0), td.get("Import", 0)])

        log_lines.append(f"Output written: {outpath}")

    if dry_run:
        log_lines.append("Dry run — no files written.")

    return "\n".join(log_lines), yearly


def process_all_subfolders(
    main_folder: str,
    dry_run: bool = True,
    prefer_updates: bool = True,
    output_folder: Optional[str] = None
):
    """Process all subfolders under a main directory."""
    subs = find_subfolders(main_folder)
    if not subs:
        return f"No subfolders inside {main_folder}"

    all_logs = [
        f"Main folder: {main_folder}",
        f"Found {len(subs)} subfolders.",
        ""
    ]

    for sub in subs:
        log, _ = process_single_subfolder(
            sub,
            dry_run=dry_run,
            prefer_updates=prefer_updates,
            output_folder=output_folder
        )
        all_logs.append(log)
        all_logs.append("-" * 60)

    if dry_run:
        all_logs.append("Dry run complete for all subfolders.")
    else:
        all_logs.append("Processing complete for all.")

    return "\n".join(all_logs)