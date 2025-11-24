# processor.py

import os
import csv
from collections import defaultdict

SUPPORTED_TYPES = {"export", "import"}  # what we actually sum


def find_subfolders(main_folder: str):
    """Return a list of full paths to immediate subfolders."""
    subfolders = []
    with os.scandir(main_folder) as it:
        for entry in it:
            if entry.is_dir():
                subfolders.append(entry.path)
    return sorted(subfolders)


def list_csv_files(folder: str):
    """Return full paths to all .csv files in a folder (ignore .xlsx, etc)."""
    files = []
    with os.scandir(folder) as it:
        for entry in it:
            if entry.is_file() and entry.name.lower().endswith(".csv"):
                files.append(entry.path)
    return sorted(files)


def _find_hour_indices(header_row):
    """
    Given a CSV header row, return list of column indices that are Hr01..Hr24.
    Matching is case-insensitive and just checks for 'hr' at the start.
    """
    hour_indices = []
    for idx, name in enumerate(header_row):
        if name is None:
            continue
        name_str = str(name).strip().lower()
        if name_str.startswith("hr"):
            hour_indices.append(idx)
    return hour_indices


def _locate_header_and_hours(rows):
    """
    Scan down through the rows until we find a row that contains Hr01..Hr24.
    Returns (header_index, hour_cols). If not found, returns (-1, []).
    """
    for i, row in enumerate(rows):
        hour_cols = _find_hour_indices(row)
        if hour_cols:
            return i, hour_cols
    return -1, []


def process_csv_file(csv_path: str):
    """
    Process a single monthly CSV.

    Returns:
        results: dict[line_name][flow_type] = total_sum_for_this_file
        where flow_type is 'Export' or 'Import'.
    """
    results = defaultdict(lambda: defaultdict(float))

    with open(csv_path, "r", newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        all_rows = list(reader)

    if not all_rows:
        return {}

    header_index, hour_cols = _locate_header_and_hours(all_rows)
    if header_index == -1 or not hour_cols:
        # Couldn't find a Hr01..Hr24 header row
        return {}

    # Data starts on the row after the header
    data_rows = all_rows[header_index + 1 :]

    # We assume:
    # Col 0: Export / Import / Net
    # Col 1: Date
    # Col 2: Line name (may be blank except for first row of a block)
    current_line_name = ""

    for row in data_rows:
        if not row:
            continue

        # Make sure row is long enough for at least the first 3 columns
        # (Python will just give "" if index is out of range via safe checks below.)
        flow_type = str(row[0]).strip() if len(row) > 0 else ""
        if not flow_type:
            continue

        flow_type_lower = flow_type.lower()
        if flow_type_lower not in SUPPORTED_TYPES:
            # Ignore Net or anything else for now
            continue

        # Column 2 is line name / corridor description
        line_name_cell = ""
        if len(row) > 2:
            line_name_cell = str(row[2]).strip()

        if line_name_cell:
            current_line_name = line_name_cell

        if not current_line_name:
            # If we still don't have a name, skip – can't group it
            continue

        # Sum Hr01..Hr24
        total_for_row = 0.0
        for idx in hour_cols:
            if idx >= len(row):
                continue
            cell = str(row[idx]).strip()
            if cell == "":
                continue
            try:
                total_for_row += float(cell)
            except ValueError:
                # Non-numeric; ignore
                continue

        results[current_line_name][flow_type.capitalize()] += total_for_row

    return results


def merge_results(list_of_results):
    """
    Merge a list of results dicts into one yearly dict.

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
    lines.append("")  # trailing blank line
    return "\n".join(lines)


def process_single_subfolder(subfolder_path: str, dry_run: bool = True):
    """
    Process one monthly folder (e.g. SCPSAMonthly).

    Returns a tuple (log_text, yearly_results_dict).
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
        if not res:
            log_lines.append(
                f"   ! No Hr01–Hr24 header or no Export/Import rows found in: "
                f"{os.path.basename(csv_path)}"
            )
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

    Returns log_text covering everything.
    """
    subfolders = find_subfolders(main_folder)
    if not subfolders:
        return f"No subfolders found inside: {main_folder}"

    all_logs = [f"Main folder: {main_folder}", f"Found {len(subfolders)} subfolders.", ""]
    for sub in subfolders:
        log_text, _ = process_single_subfolder(sub, dry_run=dry_run)
        all_logs.append(log_text)
        all_logs.append("-" * 60)

    if dry_run:
        all_logs.append("Dry run complete for ALL subfolders. No files written.")
    else:
        all_logs.append("Processing complete for ALL subfolders.")

    return "\n".join(all_logs)
