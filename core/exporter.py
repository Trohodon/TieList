# core/exporter.py

import os
import csv


def get_output_root(main_folder: str, override) -> str:
    """
    Decide where to put summary CSVs.

    If override is a non-empty string, use that as the root.
    Otherwise, create/use a 'Results' folder inside main_folder.
    """

    # --- SAFETY FIX: normalize override ----
    if override is None:
        override = ""
    else:
        override = str(override).strip()

    # If user picked an override folder
    if override != "":
        root = override
    else:
        # default folder inside main folder
        root = os.path.join(main_folder, "Results")

    os.makedirs(root, exist_ok=True)
    return root


def write_subfolder_summary(output_root: str,
                            folder_name: str,
                            yearly_results: dict) -> str:
    """
    Write a CSV summary for a single subfolder.

    Columns:
        Folder, LineName, ExportTotal, ImportTotal

    Returns the full path to the file.
    """
    filename = f"{folder_name}_summary.csv"
    path = os.path.join(output_root, filename)

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Folder", "LineName", "ExportTotal", "ImportTotal"])

        for line_name in sorted(yearly_results.keys()):
            type_dict = yearly_results[line_name]
            export_total = type_dict.get("Export", 0.0)
            import_total = type_dict.get("Import", 0.0)
            writer.writerow([folder_name, line_name, export_total, import_total])

    return path


def write_all_summaries(output_root: str,
                        all_yearly: dict[str, dict]) -> list[str]:
    """
    Write summaries for all subfolders.

    all_yearly: {folder_name: yearly_results_dict}

    Returns a list of file paths created.
    """
    paths = []
    for folder_name, yearly_results in all_yearly.items():
        path = write_subfolder_summary(output_root, folder_name, yearly_results)
        paths.append(path)
    return paths
