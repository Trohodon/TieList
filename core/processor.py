# core/processor.py

import os
import csv
from collections import defaultdict

# Only these row types are summed. "Net" is ignored.
SUPPORTED_TYPES = {"export", "import"}


def find_subfolders(main_folder: str):
    """
    Return a sorted list of full paths to immediate subfolders
    under main_folder.
    """
    subfolders = []
    with os.scandir(main_folder) as it:
        for entry in it:
            if entry.is_dir():
                subfolders.append(entry.path)
    return sorted(subfolders)


def list_csv_files(folder: str):
    """
    Return full paths to all .csv files in a folder.
    Ignores .xlsx and anything else.
    """
    files = []
    with os.scandir(folder) as it:
        for entry in it:
            if entry.is_file() and entry.name.lower().endswith(".csv"):
                files.append(entry.path)
    return sorted(files)


def _find_hour_indices(header_row):
    """
    Given a CSV header row, return a list of column indices that look like
    Hr01..Hr24 (match 'hr' at the start, case-insensitive).
    """
    hour_indices = []
    for idx, name in enumerate(header_row):
        if name is None:
            continue
        name_str = str(name).strip().lower()
        if name_str.startswith("hr"):
            hour_indices.append(idx)
    return hour_indices


def process_csv_file(csv_path: str):
    """
    Process a single monthly CSV file.

    Returns:
        results: dict[line_name][flow_type] = total_sum_for_this_file
        where flow_type is 'Export' or 'Import'.

    Assumes:
        Col 0: Export / Import / Net
        Col 1: Date
        Col 2: Line / corridor name (may only appear on the first row of a block)
        HrXX columns somewhere to the right (Hr01..Hr24).
    """
    results = defaultdict(lambda: defaultdict(float))

    with open(csv_path, "r", newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        try:
            header = next(reader)
        except StopIteration:
            return {}  # Empty file, nothing to do.

        hour_cols = _find_hour_indices(header)
        if not hour_cols:
            # No Hr01–Hr24 detected
            return {}

        current_line_name = ""

        for row in reader:
            if not row:
                continue

            flow_type = str(row[0]).strip()
            if not flow_type:
                continue

            flow_type_lower = flow_type.lower()
            if flow_type_lower not in SUPPORTED_TYPES:
                # Skip Net or anything that isn't Export/Import
                continue

            # Column 2 is the corridor / line name.
            line_name_cell = ""
            if len(row) > 2:
                line_name_cell = str(row[2]).strip()

            if line_name_cell:
                current_line_name = line_name_cell

            if not current_line_name:
                # If we still don't know which line this belongs to, skip it.
                continue

            # Sum Hr01..Hr24 columns
            total_for_row = 0.0
            for idx in hour_cols:
                if idx >= len(row):
                    continue
                cell = row[idx].strip()
                if cell == "":
                    continue
                try:
                    total_for_row += float(cell)
                except ValueError:
                    # Non-numeric cell; ignore
                    continue

            results[current_line_name][flow_type.capitalize()] += total_for_row

    return results


def merge_results(list_of_results):
    """
    Merge multiple monthly result dicts into one yearly dict.

    Input:  [dict[line][type] = value, ...]
    Output: dict[line][type] = yearly_total
    """
    yearly = defaultdict(lambda: defaultdict(float))
    for res in list_of_results:
        for line_name, type_dict in res.items():
            for flow_type, value in type_dict.items():
                yearly[line_name][flow_type] += value
    return yearly


def format_results_as_text(yearly_results, folder_label: str):
    """
    Create a human-readable text block for the GUI log window.
    folder_label is usually the subfolder name (e.g. 'SCPSAMonthly').
    """
    lines = []
    lines.append(f"===== Results for {folder_label} =====")
    if not yearly_results:
        lines.append("  (No data found – check CSV format or Hr01–Hr24 headers.)")
        return "\n".join(lines)

    for line_name in sorted(yearly_results.keys()):
        type_dict = yearly_results[line_name]
        export_total = type_dict.get("Export", 0.0)
        import_total = type_dict.get("Import", 0.0)
        lines.append(f"Line: {line_name}")
        lines.append(f"    Export total (Hr01–Hr24, full year): {export_total}")
        lines.append(f"    Import total (Hr01–Hr24, full year): {import_total}")
    lines.append("")  # blank line at the end
    return "\n".join(lines)


def process_single_subfolder(subfolder_path: str, dry_run: bool = True):
    """
    Process one secondary folder (e.g. SCPSAMonthly).

    Returns:
        (log_text, yearly_results_dict)
    """
    folder_name = os.path.basename(subfolder_path.rstrip("/\\"))
    csv_files = list_csv_files(subfolder_path)

    log_lines = [
        f"Processing subfolder: {folder_name}",
        f"Found {len(csv_files)} .csv files:",
    ]
    for p in csv_files:
        log_lines.append(f"   - {os.path.basename(p)}")

    monthly_results = []
    for csv_path in csv_files:
        res = process_csv_file(csv_path)
        monthly_results.append(res)

    yearly = merge_results(monthly_results)
    log_lines.append("")
    log_lines.append(format_results_as_text(yearly, folder_name))

    if dry_run:
        log_lines.append("Dry run: no files were written. (Computation only.)")

    return "\n".join(log_lines), yearly


def process_all_subfolders(main_folder: str, dry_run: bool = True):
    """
    Process all immediate subfolders under main_folder.

    Returns:
        log_text covering everything.
    """
    subfolders = find_subfolders(main_folder)
    if not subfolders:
        return f"No subfolders found inside: {main_folder}"

    all_logs = [
        f"Main folder: {main_folder}",
        f"Found {len(subfolders)} subfolders.",
        "",
    ]
    for sub in subfolders:
        log_text, _ = process_single_subfolder(sub, dry_run=dry_run)
        all_logs.append(log_text)
        all_logs.append("-" * 60)

    if dry_run:
        all_logs.append("Dry run complete for ALL subfolders. No files written.")
    else:
        all_logs.append("Processing complete for ALL subfolders.")

    return "\n".join(all_logs)
