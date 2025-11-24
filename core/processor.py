# core/processor.py

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


def choose_csv_files(folder: str, prefer_updates: bool):
    """
    Decide which CSV files to use in a folder.

    If prefer_updates is True:
        - Use 'base_update.csv' instead of 'base.csv' when both exist.
        - Otherwise just use whatever exists.

    If prefer_updates is False:
        - Ignore any '*_update.csv' files and use only the base files.
    """
    all_csv = list_csv_files(folder)

    if not prefer_updates:
        chosen = []
        for path in all_csv:
            name = os.path.basename(path)
            root, ext = os.path.splitext(name)
            if root.lower().endswith("_update"):
                continue
            chosen.append(path)
        return chosen

    # prefer_updates == True
    base_map = {}  # base_root -> chosen file path
    for path in all_csv:
        name = os.path.basename(path)
        root, ext = os.path.splitext(name)
        if root.lower().endswith("_update"):
            base_root = root[:-7]  # strip "_update"
            base_map[base_root] = path  # overwrite base if present
        else:
            base_root = root
            base_map.setdefault(base_root, path)  # only set if not replaced

    # Return files in a stable order
    chosen_paths = [base_map[k] for k in sorted(base_map.keys())]
    return chosen_paths


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


def _find_name_col(header_row):
    """
    Try to find the column index whose header looks like the line/tie name.
    We look for keywords like 'name', 'line', or 'tie' in the header text.
    Returns index or None.
    """
    if not header_row:
        return None

    keywords = ("name", "line", "tie")
    for idx, cell in enumerate(header_row):
        if not cell:
            continue
        text = str(cell).strip().lower()
        if any(k in text for k in keywords):
            return idx
    return None


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

    header_row = all_rows[header_index]
    name_col_idx = _find_name_col(header_row)  # may be None

    data_rows = all_rows[header_index + 1 :]

    current_line_name = ""
    flow_col_index = None  # we will detect this dynamically from the data rows

    for row in data_rows:
        if not row:
            continue

        # If we don't yet know which column has Export/Import, scan this row
        if flow_col_index is None:
            for idx, cell in enumerate(row):
                val = str(cell).strip().lower()
                if val in SUPPORTED_TYPES:
                    flow_col_index = idx
                    break

        if flow_col_index is None or flow_col_index >= len(row):
            # still haven't seen any Export/Import yet
            continue

        flow_type = str(row[flow_col_index]).strip()
        if not flow_type:
            continue

        flow_type_lower = flow_type.lower()
        if flow_type_lower not in SUPPORTED_TYPES:
            # Ignore Net or anything else
            continue

        # Determine which column holds the line/tie name
        line_name_cell = ""
        if name_col_idx is not None and name_col_idx < len(row):
            # Preferred: explicit Name/Line/Tie column from header
            line_name_cell = str(row[name_col_idx]).strip()
        else:
            # Fallback: two columns to the right of flow-type column
            line_name_idx = flow_col_index + 2
            if line_name_idx < len(row):
                line_name_cell = str(row[line_name_idx]).strip()

        if line_name_cell:
            current_line_name = line_name_cell

        if not current_line_name:
            # Can't group without a name
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


def write_yearly_results_csv(yearly_results, folder_label: str, output_folder: str):
    """
    Write yearly results for one subfolder to a CSV file.

    Returns: full path to the output file (or None if nothing to write).
    """
    if not yearly_results:
        return None

    os.makedirs(output_folder, exist_ok=True)

    filename = f"{folder_label}_YearlyTotals.csv"
    out_path = os.path.join(output_folder, filename)

    with open(out_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["Line Name", "Export Total", "Import Total"])
        for line_name in sorted(yearly_results.keys()):
            type_dict = yearly_results[line_name]
            export_total = type_dict.get("Export", 0.0)
            import_total = type_dict.get("Import", 0.0)
            writer.writerow([line_name, export_total, import_total])

    return out_path


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


def process_single_subfolder(
    subfolder_path: str,
    dry_run: bool = True,
    prefer_updates: bool = True,
    output_folder: str | None = None,
):
    """
    Process one monthly folder (e.g. SCPSAMonthly).

    Returns a tuple (log_text, yearly_results_dict, output_path).
    output_path is None if nothing was written (e.g. dry run, or no data).
    """
    folder_name = os.path.basename(subfolder_path.rstrip("/\\"))
    csv_files = choose_csv_files(subfolder_path, prefer_updates=prefer_updates)

    log_lines = [
        f"Processing subfolder: {folder_name}",
        f"Prefer updates: {prefer_updates}",
        f"Using {len(csv_files)} .csv files:",
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

    output_path = None
    if (not dry_run) and output_folder:
        output_path = write_yearly_results_csv(
            yearly, folder_label=folder_name, output_folder=output_folder
        )
        if output_path:
            log_lines.append(f"Saved yearly totals to: {output_path}")

    if dry_run:
        log_lines.append("Dry run: no files were written. (Computation only.)")

    return "\n".join(log_lines), yearly, output_path


def process_all_subfolders(
    main_folder: str,
    dry_run: bool = True,
    prefer_updates: bool = True,
    output_folder: str | None = None,
):
    """
    Non-GUI helper: process all subfolders and (optionally) write outputs.

    Returns (combined_log_text, list_of_output_paths)
    """
    subfolders = find_subfolders(main_folder)
    if not subfolders:
        return f"No subfolders found inside: {main_folder}", []

    all_logs = [
        f"Main folder: {main_folder}",
        f"Found {len(subfolders)} subfolders.",
        f"Prefer updates: {prefer_updates}",
        "",
    ]
    all_outputs: list[str] = []

    for sub in subfolders:
        log_text, _, out_path = process_single_subfolder(
            sub,
            dry_run=dry_run,
            prefer_updates=prefer_updates,
            output_folder=output_folder,
        )
        all_logs.append(log_text)
        all_logs.append("-" * 60)
        if out_path:
            all_outputs.append(out_path)

    if dry_run:
        all_logs.append("Dry run complete for ALL subfolders. No files written.")
    else:
        all_logs.append("Processing complete for ALL subfolders.")

    return "\n".join(all_logs), all_outputs
