import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from modules.models import DiffItem


FOLDER_MAPPING = {
    "Catalogs": "Справочники",
    "Documents": "Документы",
    "InformationRegisters": "РегистрыСведений",
    "AccumulationRegisters": "РегистрыНакопления",
    "AccountingRegisters": "РегистрыБухгалтерии",
    "CalculationRegisters": "РегистрыРасчета",
    "DataProcessors": "Обработки",
    "Reports": "Отчеты",
    "ChartsOfCharacteristicTypes": "ПланыВидовХарактеристик",
    "ChartsOfAccounts": "ПланыСчетов",
    "ChartsOfCalculationTypes": "ПланыВидовРасчета",
    "BusinessProcesses": "БизнесПроцессы",
    "Tasks": "Задачи",
    "CommonModules": "ОбщиеМодули",
    "Subsystems": "Подсистемы",
    "Roles": "Роли",
    "Languages": "Языки",
    "CommonCommands": "ОбщиеКоманды",
    "CommandGroups": "ГруппыКоманд",
    "Constants": "Константы",
    "Enums": "Перечисления",
    "DocumentJournals": "ЖурналыДокументов",
    "FunctionalOptions": "ФункциональныеОпции",
    "FunctionalOptionsParameters": "ПараметрыФункциональныхОпций",
    "SettingsStorages": "ХранилищаНастроек",
    "CommonForms": "ОбщиеФормы",
    "CommonAttributes": "ОбщиеРеквизиты",
    "ExchangePlans": "ПланыОбмена",
    "FilterCriteria": "КритерииОтбора",
    "EventSubscriptions": "ПодпискиНаСобытия",
    "ScheduledJobs": "РегламентныеЗадания",
    "WebServices": "WebСервисы",
    "HTTPServices": "HTTPСервисы",
    "WSReferences": "WSСсылки",
    "StyleItems": "ЭлементыСтиля",
    "Styles": "Стили",
    "DefinedTypes": "ОпределяемыеТипы",
    "CommonPictures": "ОбщиеКартинки",
    "CommonTemplates": "ОбщиеМакеты",
    "XDTOPackages": "ПакетыXDTO",
    "IntegrationServices": "СервисыИнтеграции",
}


def get_obsidian_folder(relative_path: str) -> str:
    parts = relative_path.replace("\\", "/").split("/")
    if not parts:
        return "Объекты"
    return FOLDER_MAPPING.get(parts[0], parts[0])


def get_object_name(relative_path: str) -> str:
    return Path(relative_path).stem


def parse_configuration_xml(config_path: str) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    cfg_file = Path(config_path) / "Configuration.xml"
    if not cfg_file.exists():
        return result
    try:
        tree = ET.parse(cfg_file)
        root = tree.getroot()
        for child_objects in root.iter():
            if child_objects.tag.endswith("ChildObjects"):
                for child in child_objects:
                    tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
                    name = child.text.strip() if child.text else ""
                    if not name:
                        continue
                    folder = FOLDER_MAPPING.get(tag, tag)
                    result.setdefault(folder, []).append(name)
                break
    except Exception:
        pass
    return result


def parse_subsystem_content(config_path: str, subsystem_name: str) -> list[str]:
    sub_file = Path(config_path) / "Subsystems" / f"{subsystem_name}.xml"
    if not sub_file.exists():
        return []
    try:
        tree = ET.parse(sub_file)
        root = tree.getroot()
        contents: list[str] = []
        for content in root.iter():
            if content.tag.endswith("Content"):
                for item in content:
                    text = item.text.strip() if item.text else ""
                    if text:
                        contents.append(text)
                break
        return contents
    except Exception:
        return []


def _write_obsidian_report(
    root: Path,
    title: str,
    filename: str,
    selected: list[DiffItem],
    intro: list[str],
) -> None:
    lines = [f"# {title}", ""]
    lines.extend(intro)
    lines.append("")
    lines.append(f"- Количество: {len(selected)}")
    lines.append("")

    grouped: dict[str, list[DiffItem]] = {}
    for item in selected:
        folder = get_obsidian_folder(item.relative_path)
        grouped.setdefault(folder, []).append(item)

    for folder in sorted(grouped.keys(), key=lambda x: x.lower()):
        lines.append(f"## {folder}")
        lines.append("")
        for item in sorted(grouped[folder], key=lambda x: x.relative_path.lower()):
            name = get_object_name(item.relative_path)
            lines.append(f"- [[{folder}/{name}|{name}]]")
        lines.append("")

    (root / filename).write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_obsidian_vault(
    output_dir: str,
    obsidian_dir: str,
    config: dict[str, Any],
    items: list[DiffItem],
) -> None:
    root = Path(obsidian_dir)
    root.mkdir(parents=True, exist_ok=True)

    custom_dir = config["paths"]["custom_dir"]

    # Объектные заметки
    for item in items:
        folder = get_obsidian_folder(item.relative_path)
        name = get_object_name(item.relative_path)
        note_dir = root / folder
        note_dir.mkdir(parents=True, exist_ok=True)

        yaml_lines = [
            "---",
            f"type: {folder}",
            f"status: {item.status}",
            f"our_markers: {'true' if item.contains_our_markers else 'false'}",
            f"our_added: {'true' if item.is_our_added else 'false'}",
            f"file_ext: {item.file_ext or ''}",
            "---",
        ]

        body = [f"# {name}", ""]
        if item.vendor_path:
            body.append(f"- Путь вендора: `{item.vendor_path}`")
        if item.custom_path:
            body.append(f"- Путь доработки: `{item.custom_path}`")
        body.append(f"- Статус: {item.status}")
        if item.status == "modified":
            body.append(f"- Наши маркеры: {'да' if item.contains_our_markers else 'нет'}")
        if item.status == "added":
            body.append(f"- Наш объект: {'да' if item.is_our_added else 'нет'}")

        body.append("")
        body.append(f"[Карточка diff]({item.relative_path}.md)")

        (note_dir / f"{name}.md").write_text(
            "\n".join(yaml_lines + [""] + body) + "\n",
            encoding="utf-8",
        )

    # Отчёты
    _write_obsidian_report(
        root, "Наши добавленные объекты", "OUR_ADDED.md",
        [i for i in items if i.is_our_added],
        [
            "Сюда попадают файлы, которых нет у вендора, но они появились в нашей версии.",
            "Имя файла содержит наши маркеры — префиксы или суффиксы из конфига.",
        ],
    )
    _write_obsidian_report(
        root, "Изменённые объекты с нашими маркерами", "MODIFIED_WITH_OUR_MARKERS.md",
        [i for i in items if i.status == "modified" and i.contains_our_markers],
        [
            "Файлы отличаются от вендора, и в diff найдены наши маркеры.",
            "Изменения, скорее всего, вносили мы.",
        ],
    )
    _write_obsidian_report(
        root, "Изменённые объекты без наших маркеров", "MODIFIED_WITHOUT_OUR_MARKERS.md",
        [i for i in items if i.status == "modified" and not i.contains_our_markers],
        [
            "Файлы отличаются от вендора, но маркеры не найдены.",
            "Либо обновление вендора, либо наша доработка без пометок.",
        ],
    )
    _write_obsidian_report(
        root, "Удалённые объекты", "REMOVED.md",
        [i for i in items if i.status == "removed"],
        ["Файлы есть у вендора, но отсутствуют в доработанной версии."],
    )
    _write_obsidian_report(
        root, "Все добавленные объекты", "ADDED.md",
        [i for i in items if i.status == "added"],
        [
            "Все файлы, которые есть только в доработанной версии.",
            "Чтобы увидеть только наши объекты, откройте [[OUR_ADDED]].",
        ],
    )

    # SUMMARY
    counts = {
        "added": sum(1 for i in items if i.status == "added"),
        "modified": sum(1 for i in items if i.status == "modified"),
        "removed": sum(1 for i in items if i.status == "removed"),
        "unchanged": sum(1 for i in items if i.status == "unchanged"),
        "our_added": sum(1 for i in items if i.is_our_added),
        "modified_with": sum(1 for i in items if i.status == "modified" and i.contains_our_markers),
        "modified_without": sum(1 for i in items if i.status == "modified" and not i.contains_our_markers),
    }
    summary = [
        "# Сводка", "",
        "Общая картина различий.", "",
        f"- Всего добавлено: {counts['added']}",
        f"- Из них наши: {counts['our_added']}",
        f"- Изменено с маркерами: {counts['modified_with']}",
        f"- Изменено без маркеров: {counts['modified_without']}",
        f"- Удалено: {counts['removed']}",
        f"- Без изменений: {counts['unchanged']}",
        "", "## Отчёты", "",
        "- [[ADDED|Все добавленные]]",
        "- [[OUR_ADDED|Наши добавленные]]",
        "- [[MODIFIED_WITH_OUR_MARKERS|Изменённые с маркерами]]",
        "- [[MODIFIED_WITHOUT_OUR_MARKERS|Изменённые без маркеров]]",
        "- [[REMOVED|Удалённые]]",
        "",
    ]
    (root / "SUMMARY.md").write_text("\n".join(summary) + "\n", encoding="utf-8")

    # Configuration.md — MOC
    cfg_objects = parse_configuration_xml(custom_dir)

    config_lines = [
        "# Конфигурация", "",
        "## Анализ изменений", "",
        "- [[SUMMARY|Сводка]]",
        "- [[OUR_ADDED|Наши добавленные объекты]]",
        "- [[MODIFIED_WITH_OUR_MARKERS|Изменённые с нашими маркерами]]",
        "- [[MODIFIED_WITHOUT_OUR_MARKERS|Изменённые без наших маркеров]]",
        "- [[REMOVED|Удалённые объекты]]",
        "- [[ADDED|Все добавленные объекты]]",
        "",
    ]

    if "Подсистемы" in cfg_objects:
        config_lines.append("## Подсистемы")
        config_lines.append("")
        for sub_name in sorted(cfg_objects["Подсистемы"], key=lambda x: x.lower()):
            config_lines.append(f"- [[Подсистемы/{sub_name}|{sub_name}]]")
            sub_contents = parse_subsystem_content(custom_dir, sub_name)
            sub_note = [f"# {sub_name}", "", "## Состав"]
            for obj in sub_contents:
                if "." in obj:
                    type_prefix, obj_name = obj.split(".", 1)
                    folder = FOLDER_MAPPING.get(type_prefix, type_prefix)
                    sub_note.append(f"- [[{folder}/{obj_name}|{obj_name}]]")
                else:
                    sub_note.append(f"- {obj}")
            sub_note.append("")
            (root / "Подсистемы").mkdir(parents=True, exist_ok=True)
            (root / "Подсистемы" / f"{sub_name}.md").write_text(
                "\n".join(sub_note) + "\n", encoding="utf-8"
            )
        config_lines.append("")

    if "Роли" in cfg_objects:
        config_lines.append("## Роли")
        config_lines.append("")
        for role_name in sorted(cfg_objects["Роли"], key=lambda x: x.lower()):
            config_lines.append(f"- [[Роли/{role_name}|{role_name}]]")
        config_lines.append("")

    if "Языки" in cfg_objects:
        config_lines.append("## Языки")
        config_lines.append("")
        for lang_name in sorted(cfg_objects["Языки"], key=lambda x: x.lower()):
            config_lines.append(f"- [[Языки/{lang_name}|{lang_name}]]")
        config_lines.append("")

    other_types = [k for k in cfg_objects if k not in ("Подсистемы", "Роли", "Языки")]
    if other_types:
        config_lines.append("## Объекты конфигурации")
        config_lines.append("")
        for obj_type in sorted(other_types, key=lambda x: x.lower()):
            config_lines.append(f"- [[{obj_type}]]")
        config_lines.append("")

    (root / "Configuration.md").write_text("\n".join(config_lines) + "\n", encoding="utf-8")