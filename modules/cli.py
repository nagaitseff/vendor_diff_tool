import argparse
import json
import os
import shutil
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Callable

from modules import __version__
from modules.config import load_config, validate_config, write_example_config
from modules.doctor import format_doctor_results, run_doctor
from modules.markdown_renderer import (
    build_diff_lines,
    build_ndiff_lines,
    diff_contains_our_markers,
    write_added_report,
    write_item_markdown,
    write_modified_with_markers_report,
    write_modified_without_markers_report,
    write_our_added_report,
    write_removed_report,
    write_summary,
)
from modules.models import DiffItem
from modules.scanner import scan_files
from modules.site_builder import build_site_docs, build_site_docs_fast
from modules.obsidian_builder import build_obsidian_vault


CACHE_DIR_NAME = ".cache"
ITEMS_AFTER_COMPARE_NAME = "items_after_compare.json"
RUN_REPORT_NAME = "run_report.md"


def ensure_dir(path: str | Path) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def cache_dir(output_dir: str) -> Path:
    return ensure_dir(Path(output_dir) / CACHE_DIR_NAME)


def items_after_compare_path(output_dir: str) -> Path:
    return cache_dir(output_dir) / ITEMS_AFTER_COMPARE_NAME


def save_items_after_compare(output_dir: str, items: list[DiffItem]) -> None:
    payload = [item.__dict__ for item in items]
    items_after_compare_path(output_dir).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_items_after_compare(output_dir: str) -> list[DiffItem]:
    path = items_after_compare_path(output_dir)
    if not path.exists():
        raise FileNotFoundError(
            f"Не найден файл состояния: {path}\n"
            f"Сначала выполните полный запуск: python main.py run --config config.yaml"
        )

    raw = json.loads(path.read_text(encoding="utf-8"))
    return [DiffItem(**item) for item in raw]


def write_run_report(
    output_dir: str,
    config_path: str,
    vendor_dir: str,
    custom_dir: str,
    counts: dict[str, int],
    durations: dict[str, float],
    mode: str,
    project_info: dict[str, Any] | None = None,
) -> None:
    project = project_info or {}
    report = [
        "# Отчёт о запуске",
        "",
    ]
    if project.get("name"):
        report.append(f"- Проект: {project['name']}")
    if project.get("version"):
        report.append(f"- Версия: {project['version']}")
    if project.get("description"):
        report.append(f"- Описание: {project['description']}")
    report.extend([
        f"- Конфиг: `{config_path}`",
        f"- Каталог вендора: `{vendor_dir}`",
        f"- Каталог доработки: `{custom_dir}`",
        f"- Режим сравнения: `{mode}`",
        "",
        "## Результат",
        "",
        f"- Добавлено: {counts.get('added', 0)}",
        f"- Изменено: {counts.get('modified', 0)}",
        f"- Удалено: {counts.get('removed', 0)}",
        f"- Без изменений: {counts.get('unchanged', 0)}",
        "",
        "## Время",
        "",
    ])
    for step_name, duration in durations.items():
        report.append(f"- {step_name}: {format_duration(duration)}")
    report.append("")
    Path(output_dir, RUN_REPORT_NAME).write_text("\n".join(report), encoding="utf-8")

def run_timed_step(title: str, func: Callable[[], Any], verbose: bool = True):
    if verbose:
        print(title)
    started = time.perf_counter()
    result = func()
    duration = time.perf_counter() - started
    if verbose:
        print(f"Готово: {format_duration(duration)}")
    return result, duration


def compare_files_bytes(path1: str, path2: str) -> bool:
    """Быстрое побайтовое сравнение. Если отличаются — проверяем, не BOM ли виноват."""
    with open(path1, "rb") as f1, open(path2, "rb") as f2:
        b1 = f1.read()
        b2 = f2.read()
        if b1 == b2:
            return True

    # Fallback: отличие может быть только в BOM. Сравниваем как текст без BOM.
    try:
        with open(path1, "r", encoding="utf-8-sig") as f1, open(path2, "r", encoding="utf-8-sig") as f2:
            return f1.read() == f2.read()
    except (UnicodeDecodeError, IOError):
        return False


def classify_our_added(relative_path: str, custom_name_markers: dict[str, Any]) -> bool:
    starts_with = custom_name_markers.get("starts_with", [])
    ends_with = custom_name_markers.get("ends_with", [])
    stem = Path(relative_path).stem

    return any(stem.startswith(marker) for marker in starts_with) or any(
        stem.endswith(marker) for marker in ends_with
    )


def _get_max_workers(config: dict[str, Any]) -> int:
    """Определяет количество потоков из конфига или авто."""
    perf = config.get("performance", {})
    max_workers = perf.get("max_workers", None)

    if max_workers is None:
        # Ограничиваем 16: Python GIL + диск IO = больше потоков не лучше
        max_workers = min(16, (os.cpu_count() or 2) * 2)
    elif max_workers <= 0:
        max_workers = 1

    return max_workers


def build_items(config: dict[str, Any]) -> list[DiffItem]:
    vendor_dir = config["paths"]["vendor_dir"]
    custom_dir = config["paths"]["custom_dir"]

    include_extensions = config["scan"].get("include_extensions", [])
    exclude_dir_prefixes = config["scan"].get("exclude_dirs_prefixes", [])
    exclude_file_prefixes = config["scan"].get("exclude_files_prefixes", [])
    exclude_files_exact = config["scan"].get("exclude_files_exact", [])

    vendor_files = scan_files(
        base_dir=vendor_dir,
        include_extensions=include_extensions,
        exclude_dir_prefixes=exclude_dir_prefixes,
        exclude_file_prefixes=exclude_file_prefixes,
        exclude_files_exact=exclude_files_exact,
    )
    custom_files = scan_files(
        base_dir=custom_dir,
        include_extensions=include_extensions,
        exclude_dir_prefixes=exclude_dir_prefixes,
        exclude_file_prefixes=exclude_file_prefixes,
        exclude_files_exact=exclude_files_exact,
    )

    vendor_map = vendor_files
    custom_map = custom_files

    all_paths = sorted(set(vendor_map.keys()) | set(custom_map.keys()), key=lambda s: s.lower())

    compare_mode = config["compare"].get("mode", "bytes")
    markers = config["classification"].get("custom_name_markers", {})
    enable_our_added = config["classification"].get("enable_our_added_classification", True)

    # === МНОГОПОТОЧНОЕ СРАВНЕНИЕ ===
    max_workers = _get_max_workers(config)
    total = len(all_paths)
    print(f"Сравнение файлов: {total} объектов, потоков: {max_workers}")

    def compare_one(relative_path: str):
        vendor_path = vendor_map.get(relative_path)
        custom_path = custom_map.get(relative_path)

        if vendor_path and custom_path:
            if compare_mode == "bytes":
                same = compare_files_bytes(vendor_path, custom_path)
            else:
                same = compare_files_bytes(vendor_path, custom_path)
            status = "unchanged" if same else "modified"
        elif custom_path and not vendor_path:
            status = "added"
        elif vendor_path and not custom_path:
            status = "removed"
        else:
            return None

        file_ext = Path(relative_path).suffix.lower()

        return DiffItem(
            relative_path=relative_path.replace("\\", "/"),
            vendor_path=vendor_path,
            custom_path=custom_path,
            status=status,
            file_ext=file_ext,
            is_our_added=enable_our_added
            and status == "added"
            and classify_our_added(relative_path, markers),
            contains_our_markers=False,
        )

    items: list[DiffItem] = []
    processed = 0

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(compare_one, rp): rp for rp in all_paths}
        for future in as_completed(futures):
            result = future.result()
            processed += 1
            if result:
                items.append(result)
            if processed % 5000 == 0:
                print(f"  Сравнено {processed}/{total}")

    items.sort(key=lambda x: x.relative_path.lower())
    print(f"Сравнение завершено: {len(items)} объектов")

    return items


def generate_markdown_and_reports(
    config: dict[str, Any],
    config_path: str,
    items: list[DiffItem],
    verbose: bool = True,
) -> None:
    output_dir = config["paths"]["output_dir"]
    rewrite_bsl = config["markdown"].get("rewrite_bsl_directives", True)
    publish_unchanged = config["compare"].get("publish_unchanged", False)

    report_cfg = config.get("reports", {})
    write_our_added_report_flag = report_cfg.get("write_our_added_report", True)
    write_modified_with_markers_report_flag = report_cfg.get("write_modified_with_markers_report", True)
    write_modified_without_markers_report_flag = report_cfg.get("write_modified_without_markers_report", True)

    our_added_report_name = report_cfg.get("our_added_report_name", "OUR_ADDED.md")
    modified_with_markers_report_name = report_cfg.get(
        "modified_with_markers_report_name",
        "MODIFIED_WITH_OUR_MARKERS.md",
    )
    modified_without_markers_report_name = report_cfg.get(
        "modified_without_markers_report_name",
        "MODIFIED_WITHOUT_OUR_MARKERS.md",
    )

    content_detection = config["classification"].get("content_detection", {})
    detect_enabled = content_detection.get("enabled", True)
    detect_in_identifier_start = content_detection.get("detect_in_identifier_start", True)
    detect_in_identifier_end = content_detection.get("detect_in_identifier_end", True)
    detect_in_comment_after_slashes = content_detection.get(
        "detect_in_comment_after_slashes",
        True,
    )
    detect_inside_word = content_detection.get("detect_inside_word", False)

    custom_name_markers = config["classification"].get("custom_name_markers", {})
    starts_with = custom_name_markers.get("starts_with", [])
    ends_with = custom_name_markers.get("ends_with", [])

    durations: dict[str, float] = {}

    # Пропускать diff для файлов больше этого размера (байт)
    perf_cfg = config.get("performance", {})
    MAX_DIFF_FILE_SIZE = perf_cfg.get("max_diff_file_size_mb", 5) * 1024 * 1024
    FUTURE_TIMEOUT = perf_cfg.get("future_timeout_seconds", 300)

    max_workers = _get_max_workers(config)
    total_md = len([i for i in items if i.status != "unchanged" or publish_unchanged])
    print(f"Генерация Markdown: {total_md} файлов, потоков: {max_workers}")

    def process_one_item(item: DiffItem):
        try:
            diff_lines = None
            ndiff_lines = None

            if item.status == "modified" and item.vendor_path and item.custom_path:
                v_size = os.path.getsize(item.vendor_path)
                c_size = os.path.getsize(item.custom_path)

                if v_size > MAX_DIFF_FILE_SIZE or c_size > MAX_DIFF_FILE_SIZE:
                    diff_lines = [f"<!-- Файл слишком большой для полного diff (> 5 MB) -->"]
                    ndiff_lines = []
                    item.contains_our_markers = False
                else:
                    diff_lines = build_diff_lines(item.vendor_path, item.custom_path, rewrite_bsl)
                    ndiff_lines = build_ndiff_lines(item.vendor_path, item.custom_path, rewrite_bsl)

                    if detect_enabled:
                        item.contains_our_markers = diff_contains_our_markers(
                            diff_lines=diff_lines,
                            starts_with=starts_with,
                            ends_with=ends_with,
                            detect_in_identifier_start=detect_in_identifier_start,
                            detect_in_identifier_end=detect_in_identifier_end,
                            detect_in_comment_after_slashes=detect_in_comment_after_slashes,
                            detect_inside_word=detect_inside_word,
                        )

            if item.status == "unchanged" and not publish_unchanged:
                return None

            write_item_markdown(
                output_dir=output_dir,
                item=item,
                diff_lines=diff_lines,
                ndiff_lines=ndiff_lines,
            )
            return item.relative_path

        except Exception as e:
            print(f"  ОШИБКА в {item.relative_path}: {e}")
            return None

    processed = 0
    errors = 0
    skipped_big = 0

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(process_one_item, item): item
            for item in items
            if item.status != "unchanged" or publish_unchanged
        }

        for future in as_completed(futures):
            item = futures[future]
            try:
                result = future.result(timeout=FUTURE_TIMEOUT)
                processed += 1
                if result is None and item.status == "modified":
                    v_size = os.path.getsize(item.vendor_path) if item.vendor_path and os.path.exists(item.vendor_path) else 0
                    c_size = os.path.getsize(item.custom_path) if item.custom_path and os.path.exists(item.custom_path) else 0
                    if v_size > MAX_DIFF_FILE_SIZE or c_size > MAX_DIFF_FILE_SIZE:
                        skipped_big += 1

                if processed % 1000 == 0:
                    print(f"  Сгенерировано {processed}/{total_md} (ошибок: {errors}, пропущено больших: {skipped_big})")

            except Exception as e:
                processed += 1
                errors += 1
                print(f"  ОШИБКА/ТАЙМАУТ {item.relative_path}: {e}")

    print(f"Markdown готов: {processed} файлов (ошибок: {errors}, пропущено больших: {skipped_big})")

    def generate_reports() -> None:
        write_summary(output_dir, items, publish_unchanged, project_info=config.get("project"))
        write_added_report(output_dir, items)
        write_removed_report(output_dir, items)

        if write_our_added_report_flag:
            write_our_added_report(output_dir, our_added_report_name, items)

        if write_modified_with_markers_report_flag:
            write_modified_with_markers_report(
                output_dir,
                modified_with_markers_report_name,
                items,
            )

        if write_modified_without_markers_report_flag:
            write_modified_without_markers_report(
                output_dir,
                modified_without_markers_report_name,
                items,
            )

    _, duration = run_timed_step(
        "Построение сводных отчётов...",
        generate_reports,
        verbose,
    )
    durations["Сводные отчёты"] = duration

    counts = {
        "added": sum(1 for i in items if i.status == "added"),
        "modified": sum(1 for i in items if i.status == "modified"),
        "removed": sum(1 for i in items if i.status == "removed"),
        "unchanged": sum(1 for i in items if i.status == "unchanged"),
    }

    write_run_report(
        output_dir=output_dir,
        config_path=config_path,
        vendor_dir=config["paths"]["vendor_dir"],
        custom_dir=config["paths"]["custom_dir"],
        counts=counts,
        durations=durations,
        mode=config["compare"].get("mode", "bytes"),
    )

    save_items_after_compare(output_dir, items)


def run(config_path: str) -> None:
    config = load_config(config_path)
    validate_config(config)

    output_dir = config["paths"]["output_dir"]
    verbose = config.get("reports", {}).get("verbose_console", True)

    if Path(output_dir).exists():
        shutil.rmtree(output_dir)
    ensure_dir(output_dir)

    items, _ = run_timed_step(
        "Шаг 1. Сканирование и сравнение файлов...",
        lambda: build_items(config),
        verbose,
    )

    save_items_after_compare(output_dir, items)

    _, _ = run_timed_step(
        "Шаг 2. Генерация Markdown и отчётов...",
        lambda: generate_markdown_and_reports(config, config_path, items, verbose),
        verbose,
    )

    code_font_size = config.get("site", {}).get("code_font_size", "10pt")
    diff_summary_font_size = config.get("site", {}).get("diff_summary_font_size", "8pt")

    _, _ = run_timed_step(
        "Шаг 3. Сборка документационного сайта...",
        lambda: build_site_docs(
            output_dir,
            "site_docs",
            code_font_size,
            diff_summary_font_size,
        ),
        verbose,
    )

    if verbose:
        print("Готово.")


def resume_markdown(config_path: str) -> None:
    config = load_config(config_path)
    validate_config(config)

    output_dir = config["paths"]["output_dir"]
    verbose = config.get("reports", {}).get("verbose_console", True)

    print("Продолжение с этапа генерации Markdown...")
    items = load_items_after_compare(output_dir)
    generate_markdown_and_reports(config, config_path, items, verbose)


def build_site(config_path: str) -> None:
    config = load_config(config_path)
    validate_config(config)

    output_dir = config["paths"]["output_dir"]
    verbose = config.get("reports", {}).get("verbose_console", True)
    code_font_size = config.get("site", {}).get("code_font_size", "10pt")
    diff_summary_font_size = config.get("site", {}).get("diff_summary_font_size", "8pt")

    _, _ = run_timed_step(
        "Сборка документационного сайта...",
        lambda: build_site_docs(
            output_dir,
            "site_docs",
            code_font_size,
            diff_summary_font_size,
        ),
        verbose,
    )


def build_site_fast(config_path: str) -> None:
    config = load_config(config_path)
    validate_config(config)

    output_dir = config["paths"]["output_dir"]
    verbose = config.get("reports", {}).get("verbose_console", True)
    code_font_size = config.get("site", {}).get("code_font_size", "10pt")
    diff_summary_font_size = config.get("site", {}).get("diff_summary_font_size", "8pt")

    _, _ = run_timed_step(
        "Быстрая сборка сайта...",
        lambda: build_site_docs_fast(
            output_dir,
            "site_docs",
            code_font_size,
            diff_summary_font_size,
        ),
        verbose,
    )


def clean(config_path: str) -> None:
    config = load_config(config_path)
    validate_config(config)

    output_dir = Path(config["paths"]["output_dir"])
    site_docs_dir = Path("site_docs")

    if output_dir.exists():
        shutil.rmtree(output_dir)

    if site_docs_dir.exists():
        shutil.rmtree(site_docs_dir)

    print("Каталоги output_dir и site_docs очищены.")


def init_config(path: str) -> None:
    target = Path(path)
    if target.exists():
        raise FileExistsError(f"Файл уже существует: {target}")

    write_example_config(str(target))
    print(f"Создан шаблон конфигурации: {target}")


def version() -> None:
    print(__version__)


def doctor(config_path: str) -> None:
    results, exit_code = run_doctor(config_path)
    print(format_doctor_results(results))
    raise SystemExit(exit_code)


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Vendor Diff Tool — сравнение выгрузки вендора и доработанной версии."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_config_parser = subparsers.add_parser(
        "init-config",
        help="Создать шаблон config.yaml",
    )
    init_config_parser.add_argument(
        "path",
        nargs="?",
        default="config.yaml",
        help="Путь к создаваемому config.yaml",
    )

    subparsers.add_parser("version", help="Показать версию")

    run_parser = subparsers.add_parser(
        "run",
        help="Полный запуск: сканирование, markdown, отчёты, сайт",
    )
    run_parser.add_argument("--config", required=True, help="Путь к config.yaml")

    resume_parser = subparsers.add_parser(
        "resume-markdown",
        help="Продолжить с генерации markdown и отчётов",
    )
    resume_parser.add_argument("--config", required=True, help="Путь к config.yaml")

    doctor_parser = subparsers.add_parser(
        "doctor",
        help="Проверить конфиг, импорты, выходные каталоги и Markdown-ссылки",
    )
    doctor_parser.add_argument("--config", required=True, help="Путь к config.yaml")

    build_site_parser = subparsers.add_parser(
        "build-site",
        help="Пересобрать site_docs из готового output_dir",
    )
    build_site_parser.add_argument("--config", required=True, help="Путь к config.yaml")

    fast_site_parser = subparsers.add_parser(
        "build-site-fast",
        help="Быстро пересобрать site_docs из готового output_dir",
    )
    fast_site_parser.add_argument("--config", required=True, help="Путь к config.yaml")

    clean_parser = subparsers.add_parser(
        "clean",
        help="Очистить output_dir и site_docs",
    )
    clean_parser.add_argument("--config", required=True, help="Путь к config.yaml")
    
    obsidian_parser = subparsers.add_parser(
        "build-obsidian",
        help="Сформировать Obsidian-волт из готового анализа",
    )
    obsidian_parser.add_argument("--config", required=True, help="Путь к config.yaml")

    return parser

def format_duration(seconds: float) -> str:
    if seconds < 60:
        return f"{seconds:.1f} сек."
    m = int(seconds // 60)
    s = int(seconds % 60)
    if m < 60:
        return f"{m} мин. {s} сек."
    h = m // 60
    m = m % 60
    return f"{h} ч. {m} мин. {s} сек."

def build_obsidian(config_path: str) -> None:
    config = load_config(config_path)
    validate_config(config)

    output_dir = config["paths"]["output_dir"]
    obsidian_dir = Path(output_dir).parent / "vendor_diff_output_obsidian"

    print("Формирование Obsidian-волта...")
    items = load_items_after_compare(output_dir)
    build_obsidian_vault(output_dir, str(obsidian_dir), config, items)
    print(f"Готово: {obsidian_dir}")

def main() -> None:
    parser = create_parser()
    args = parser.parse_args()

    if args.command == "init-config":
        init_config(args.path)
    elif args.command == "version":
        version()
    elif args.command == "run":
        run(args.config)
    elif args.command == "resume-markdown":
        resume_markdown(args.config)
    elif args.command == "doctor":
        doctor(args.config)
    elif args.command == "build-site":
        build_site(args.config)
    elif args.command == "build-site-fast":
        build_site_fast(args.config)
    elif args.command == "clean":
        clean(args.config)
    elif args.command == "build-obsidian":
        build_obsidian(args.config)
    else:
        parser.error(f"Неизвестная команда: {args.command}")