from pathlib import Path


def should_exclude_dir(dir_name: str, exclude_prefixes: list[str]) -> bool:
    return any(dir_name.startswith(prefix) for prefix in exclude_prefixes)


def should_exclude_file(file_name: str, exclude_prefixes: list[str], exclude_exact: list[str]) -> bool:
    if file_name in exclude_exact:
        return True
    return any(file_name.startswith(prefix) for prefix in exclude_prefixes)


def scan_files(
    base_dir: str,
    include_extensions: list[str],
    exclude_dir_prefixes: list[str],
    exclude_file_prefixes: list[str],
    exclude_files_exact: list[str],
) -> dict[str, str]:
    result: dict[str, str] = {}
    base_path = Path(base_dir)

    normalized_extensions = {ext.lower() for ext in include_extensions}

    for path in base_path.rglob("*"):
        if not path.is_file():
            continue

        relative_path = path.relative_to(base_path)
        relative_parts = relative_path.parts

        if any(should_exclude_dir(part, exclude_dir_prefixes) for part in relative_parts[:-1]):
            continue

        if should_exclude_file(path.name, exclude_file_prefixes, exclude_files_exact):
            continue

        if path.suffix.lower() not in normalized_extensions:
            continue

        result[relative_path.as_posix()] = str(path)

    return result