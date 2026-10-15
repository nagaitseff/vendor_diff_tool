from pathlib import Path
from filecmp import cmp
from modules.models import DiffItem


def matches_name_markers(name: str, starts_with: list[str], ends_with: list[str]) -> bool:
    return any(name.startswith(marker) for marker in starts_with) or any(name.endswith(marker) for marker in ends_with)


def compare_file_sets(
    vendor_files: dict[str, str],
    custom_files: dict[str, str],
    custom_name_starts_with: list[str],
    custom_name_ends_with: list[str],
    enable_our_added_classification: bool,
) -> list[DiffItem]:
    all_paths = sorted(set(vendor_files.keys()) | set(custom_files.keys()))
    result: list[DiffItem] = []

    for relative_path in all_paths:
        vendor_path = vendor_files.get(relative_path)
        custom_path = custom_files.get(relative_path)
        ext = Path(relative_path).suffix.lower()
        file_stem = Path(relative_path).stem

        is_our_added = False

        if vendor_path and custom_path:
            if cmp(vendor_path, custom_path, shallow=False):
                status = "unchanged"
            else:
                status = "modified"
        elif custom_path and not vendor_path:
            status = "added"
            if enable_our_added_classification and matches_name_markers(file_stem, custom_name_starts_with, custom_name_ends_with):
                is_our_added = True
        elif vendor_path and not custom_path:
            status = "removed"
        else:
            continue

        result.append(
            DiffItem(
                relative_path=relative_path,
                status=status,
                vendor_path=vendor_path,
                custom_path=custom_path,
                file_ext=ext,
                is_our_added=is_our_added,
            )
        )

    return result