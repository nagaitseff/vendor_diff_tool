from pathlib import Path
from typing import Any
import importlib.resources as resources

import yaml


DEFAULT_CONFIG: dict[str, Any] = {
    "project": {
        "name": "Vendor Diff Tool",
        "version": "0.1.0",
        "description": "Сравнение выгрузки вендора и доработанной версии",
    },
    "paths": {
        "vendor_dir": "",
        "custom_dir": "",
        "output_dir": "vendor_diff_output",
    },
    "scan": {
        "include_extensions": [".xml", ".bsl"],
        "exclude_dirs_prefixes": [],
        "exclude_files_prefixes": [],
        "exclude_files_exact": [],
    },
    "classification": {
        "enable_our_added_classification": True,
        "custom_name_markers": {
            "starts_with": [],
            "ends_with": [],
        },
        "content_detection": {
            "enabled": True,
            "detect_in_identifier_start": True,
            "detect_in_identifier_end": True,
            "detect_in_comment_after_slashes": True,
            "detect_inside_word": False,
        },
    },
    "compare": {
        "mode": "bytes",
        "publish_unchanged": False,
    },
    "markdown": {
        "rewrite_bsl_directives": True,
    },
    "reports": {
        "verbose_console": True,
        "write_our_added_report": True,
        "our_added_report_name": "OUR_ADDED.md",
        "write_modified_with_markers_report": True,
        "modified_with_markers_report_name": "MODIFIED_WITH_OUR_MARKERS.md",
        "write_modified_without_markers_report": True,
        "modified_without_markers_report_name": "MODIFIED_WITHOUT_OUR_MARKERS.md",
    },
    "site": {
        "code_font_size": "10pt",
        "diff_summary_font_size": "8pt",
    },
    "performance": {
        "max_workers": None,
        "max_diff_file_size_mb": 5,
        "future_timeout_seconds": 300,
    },
    "obsidian": {
        "enabled": False,
        "vault_dir": "vendor_diff_output_obsidian",
    },
}


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)

    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value

    return result


def load_config(path: str) -> dict[str, Any]:
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Файл конфигурации не найден: {config_path}")

    raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    return _deep_merge(DEFAULT_CONFIG, raw)


def validate_config(config: dict[str, Any]) -> None:
    vendor_dir = config["paths"]["vendor_dir"]
    custom_dir = config["paths"]["custom_dir"]
    output_dir = config["paths"]["output_dir"]

    if not vendor_dir:
        raise ValueError("Не заполнен paths.vendor_dir в config.yaml")
    if not custom_dir:
        raise ValueError("Не заполнен paths.custom_dir в config.yaml")
    if not output_dir:
        raise ValueError("Не заполнен paths.output_dir в config.yaml")

    if not Path(vendor_dir).exists():
        raise FileNotFoundError(f"Каталог вендора не найден: {vendor_dir}")
    if not Path(custom_dir).exists():
        raise FileNotFoundError(f"Каталог доработанной версии не найден: {custom_dir}")

    site_cfg = config.get("site", {})

    code_font_size = str(site_cfg.get("code_font_size", "10pt")).strip()
    if not code_font_size:
        raise ValueError("site.code_font_size не должен быть пустым")

    diff_summary_font_size = str(site_cfg.get("diff_summary_font_size", "8pt")).strip()
    if not diff_summary_font_size:
        raise ValueError("site.diff_summary_font_size не должен быть пустым")


def write_example_config(target_path: str) -> None:
    """Копирует config.example.yaml из пакета в указанный путь."""
    try:
        example_content = resources.files("modules").joinpath("config.example.yaml").read_text(encoding="utf-8")
    except AttributeError:
        import pkgutil
        example_content = pkgutil.get_data("modules", "config.example.yaml").decode("utf-8")

    Path(target_path).write_text(example_content, encoding="utf-8")