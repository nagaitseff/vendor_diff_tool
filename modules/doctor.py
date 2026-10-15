from dataclasses import dataclass
from pathlib import Path
import importlib
import json
import re
import traceback

from modules.config import load_config, validate_config


@dataclass
class DoctorCheckResult:
    status: str
    title: str
    details: str


def ok(title: str, details: str) -> DoctorCheckResult:
    return DoctorCheckResult("OK", title, details)


def warn(title: str, details: str) -> DoctorCheckResult:
    return DoctorCheckResult("WARN", title, details)


def error(title: str, details: str) -> DoctorCheckResult:
    return DoctorCheckResult("ERROR", title, details)


def get_project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def check_config_file(config_path: str) -> DoctorCheckResult:
    path = Path(config_path)
    if path.exists():
        return ok("config.yaml", f"Файл конфигурации найден: {path}")
    return error(
        "config.yaml",
        f"Файл конфигурации не найден: {path}\n"
        f"Выполните: python main.py init-config"
    )


def check_config_values(config_path: str) -> DoctorCheckResult:
    try:
        config = load_config(config_path)
    except Exception as exc:
        return error("Загрузка конфигурации", f"Не удалось загрузить конфиг: {exc}")

    try:
        validate_config(config)
    except Exception as exc:
        return error("Проверка конфигурации", f"Конфиг загружен, но не прошёл проверку: {exc}")

    vendor_dir = config["paths"]["vendor_dir"]
    custom_dir = config["paths"]["custom_dir"]
    output_dir = config["paths"]["output_dir"]

    return ok(
        "Пути конфигурации",
        "\n".join([
            f"vendor_dir: {vendor_dir}",
            f"custom_dir: {custom_dir}",
            f"output_dir: {output_dir}",
        ])
    )


def check_required_project_files() -> list[DoctorCheckResult]:
    root = get_project_root()

    required_files = [
        root / "main.py",
        root / "mkdocs.yml",
        root / "modules" / "config.example.yaml",
        root / "modules" / "cli.py",
        root / "modules" / "models.py",
        root / "modules" / "reporting.py",
        root / "modules" / "markdown_renderer.py",
        root / "modules" / "doctor.py",
        root / "modules" / "site_builder.py",
        root / "modules" / "scanner.py",
        root / "modules" / "comparator.py",
        root / "modules" / "xml_linker.py",
        root / "README.md",
    ]

    results: list[DoctorCheckResult] = []

    for file_path in required_files:
        if file_path.exists():
            results.append(ok("Файл проекта", f"Найден: {file_path}"))
        else:
            results.append(error("Файл проекта", f"Отсутствует: {file_path}"))

    return results


def check_python_imports() -> list[DoctorCheckResult]:
    modules = [
        "modules.models",
        "modules.reporting",
        "modules.markdown_renderer",
        "modules.xml_linker",
        "modules.site_builder",
        "modules.cli",
        "modules.doctor",
        "modules.scanner",
        "modules.comparator",
        "modules.config",
    ]

    results: list[DoctorCheckResult] = []

    for module_name in modules:
        try:
            importlib.import_module(module_name)
            results.append(ok("Импорт модуля", module_name))
        except Exception as exc:
            short = "".join(traceback.format_exception_only(type(exc), exc)).strip()
            results.append(error("Импорт модуля", f"{module_name}\n{short}"))

    return results


def check_output_dirs(config_path: str) -> list[DoctorCheckResult]:
    results: list[DoctorCheckResult] = []

    try:
        config = load_config(config_path)
    except Exception as exc:
        return [error("Каталоги результата", f"Невозможно проверить каталоги: {exc}")]

    output_dir = Path(config["paths"]["output_dir"])
    cache_file = output_dir / ".cache" / "items_after_compare.json"
    site_docs_dir = Path("site_docs")

    if output_dir.exists():
        results.append(ok("Каталог результата", f"Существует: {output_dir}"))
    else:
        results.append(warn("Каталог результата", f"Ещё не создан: {output_dir}"))

    if cache_file.exists():
        results.append(ok("Кэш resume-markdown", f"Найден: {cache_file}"))
    else:
        results.append(warn(
            "Кэш resume-markdown",
            "Кэш не найден. Команда resume-markdown пока не сможет стартовать.\n"
            "Сначала выполните хотя бы один успешный run до конца шага 3."
        ))

    if site_docs_dir.exists():
        results.append(ok("Каталог site_docs", f"Существует: {site_docs_dir}"))
    else:
        results.append(warn(
            "Каталог site_docs",
            "Пока не создан. Для локального сайта выполните: python main.py build-site --config config.yaml"
        ))

    return results


def check_models_contract() -> list[DoctorCheckResult]:
    results: list[DoctorCheckResult] = []

    try:
        from modules.models import DiffItem, StepTiming, RunReport
    except Exception as exc:
        return [error("Контракт models.py", f"Не удалось импортировать модели: {exc}")]

    missing = []

    for cls_name, attrs in {
        "DiffItem": ["relative_path", "status", "vendor_path", "custom_path", "file_ext"],
        "StepTiming": ["step_name", "duration_seconds"],
        "RunReport": ["config", "items", "generated_object_cards", "total_vendor_files", "total_custom_files"],
    }.items():
        cls = {"DiffItem": DiffItem, "StepTiming": StepTiming, "RunReport": RunReport}[cls_name]
        annotations = getattr(cls, "__annotations__", {})
        for attr in attrs:
            if attr not in annotations:
                missing.append(f"{cls_name}.{attr}")

    if missing:
        results.append(error(
            "Контракт models.py",
            "Не хватает ожидаемых полей:\n" + "\n".join(missing)
        ))
    else:
        results.append(ok("Контракт models.py", "Все ожидаемые модели и поля на месте"))

    return results


MARKDOWN_LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+\.md)\)")


def _collect_markdown_links(md_file: Path) -> set[str]:
    text = md_file.read_text(encoding="utf-8")
    links = set()

    for match in MARKDOWN_LINK_RE.finditer(text):
        target = match.group(1)
        if not target:
            continue
        if "://" in target:
            continue
        links.add(target)

    return links


def check_markdown_links_in_dir(root: Path, title_prefix: str) -> list[DoctorCheckResult]:
    results: list[DoctorCheckResult] = []

    if not root.exists():
        results.append(warn(f"Проверка ссылок ({title_prefix})", f"Каталог не найден: {root}"))
        return results

    root = root.resolve()
    all_md_files = {p.resolve().relative_to(root).as_posix(): p.resolve() for p in root.rglob("*.md")}
    broken: list[str] = []

    for rel, path in all_md_files.items():
        try:
            links = _collect_markdown_links(path)
        except Exception as exc:
            broken.append(f"{rel}: ошибка чтения ({exc})")
            continue

        for link in links:
            target_path = (path.parent / link).resolve()

            try:
                rel_target = target_path.relative_to(root).as_posix()
            except ValueError:
                broken.append(f"{rel}: ссылка выходит за пределы каталога: {link}")
                continue

            if rel_target not in all_md_files:
                broken.append(f"{rel}: не найден файл по ссылке {link}")

    if broken:
        results.append(error(
            f"Проверка ссылок ({title_prefix})",
            "Обнаружены битые Markdown-ссылки:\n" + "\n".join(broken)
        ))
    else:
        results.append(ok(f"Проверка ссылок ({title_prefix})", "Битых Markdown-ссылок не найдено"))

    return results


def run_doctor(config_path: str) -> tuple[list[DoctorCheckResult], int]:
    results: list[DoctorCheckResult] = []

    results.append(check_config_file(config_path))

    config_exists = Path(config_path).exists()
    if config_exists:
        results.append(check_config_values(config_path))
        results.extend(check_output_dirs(config_path))

    results.extend(check_required_project_files())
    results.extend(check_python_imports())
    results.extend(check_models_contract())

    try:
        config = load_config(config_path) if config_exists else None
    except Exception:
        config = None

    if config and "paths" in config:
        output_dir = Path(config["paths"]["output_dir"])
        results.extend(check_markdown_links_in_dir(output_dir, "output_dir"))

    site_docs_dir = Path("site_docs")
    results.extend(check_markdown_links_in_dir(site_docs_dir, "site_docs"))

    has_error = any(item.status == "ERROR" for item in results)
    exit_code = 1 if has_error else 0

    report_path = Path(config_path).with_name("doctor_report.json")
    payload = [
        {
            "status": item.status,
            "title": item.title,
            "details": item.details,
        }
        for item in results
    ]
    try:
        report_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception:
        pass

    return results, exit_code


def format_doctor_results(results: list[DoctorCheckResult]) -> str:
    lines: list[str] = ["Проверка проекта:", ""]

    for item in results:
        lines.append(f"[{item.status}] {item.title}")
        for detail_line in item.details.splitlines():
            lines.append(f"  {detail_line}")
        lines.append("")

    errors = sum(1 for item in results if item.status == "ERROR")
    warnings = sum(1 for item in results if item.status == "WARN")
    oks = sum(1 for item in results if item.status == "OK")

    lines.append(f"Итого: OK={oks}, WARN={warnings}, ERROR={errors}")
    return "\n".join(lines)