import json
from pathlib import Path

from modules.models import RunReport, DiffItem, StepTiming


def format_duration(seconds: float) -> str:
    seconds = max(0.0, float(seconds))

    if seconds < 60:
        return f"{seconds:.1f} сек."

    minutes = int(seconds // 60)
    remain_seconds = int(seconds % 60)

    if minutes < 60:
        if remain_seconds == 0:
            return f"{minutes} мин."
        return f"{minutes} мин. {remain_seconds} сек."

    hours = minutes // 60
    remain_minutes = minutes % 60

    if remain_minutes == 0:
        return f"{hours} ч."

    return f"{hours} ч. {remain_minutes} мин."


def build_report(
    config: dict,
    items: list[DiffItem],
    generated_object_cards: int,
    total_vendor_files: int,
    total_custom_files: int,
    step_timings: list[StepTiming],
    total_duration_seconds: float,
) -> RunReport:
    return RunReport(
        config=config,
        items=items,
        generated_object_cards=generated_object_cards,
        total_vendor_files=total_vendor_files,
        total_custom_files=total_custom_files,
        step_timings=step_timings,
        total_duration_seconds=total_duration_seconds,
    )


def build_run_report_markdown(report: RunReport) -> str:
    counts = {
        "modified": 0,
        "added": 0,
        "removed": 0,
        "unchanged": 0,
        "our_added": 0,
        "modified_with_our_markers": 0,
        "modified_without_our_markers": 0,
    }

    for item in report.items:
        counts[item.status] += 1

        if item.is_our_added:
            counts["our_added"] += 1

        if item.status == "modified":
            if item.contains_our_markers:
                counts["modified_with_our_markers"] += 1
            else:
                counts["modified_without_our_markers"] += 1

    lines = [
        "# Отчёт о запуске",
        "",
        "## Входные данные",
        "",
        f"- Каталог вендора: `{report.config['paths']['vendor_dir']}`",
        f"- Каталог доработки: `{report.config['paths']['custom_dir']}`",
        f"- Каталог результата: `{report.config['paths']['output_dir']}`",
        "",
        "## Статистика файлов",
        "",
        f"- Всего файлов у вендора: {report.total_vendor_files}",
        f"- Всего файлов в доработке: {report.total_custom_files}",
        f"- Изменено: {counts['modified']}",
        f"- Добавлено: {counts['added']}",
        f"- Удалено: {counts['removed']}",
        f"- Без изменений: {counts['unchanged']}",
        "",
        "## Классификация",
        "",
        f"- Наши добавленные объекты: {counts['our_added']}",
        f"- Изменённые с нашими маркерами: {counts['modified_with_our_markers']}",
        f"- Изменённые без наших маркеров: {counts['modified_without_our_markers']}",
        f"- Создано карточек XML-объектов: {report.generated_object_cards}",
        "",
        "## Время выполнения",
        "",
    ]

    for step in report.step_timings:
        lines.append(f"- {step.step_name}: {format_duration(step.duration_seconds)}")

    lines.extend([
        f"- Общее время: {format_duration(report.total_duration_seconds)}",
        "",
    ])

    return "\n".join(lines) + "\n"


def write_reports(output_dir: str, report: RunReport) -> None:
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)

    (root / "run_report.md").write_text(
        build_run_report_markdown(report),
        encoding="utf-8",
    )

    (root / "run_report.json").write_text(
        json.dumps(report.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )