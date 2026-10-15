import os
from collections import defaultdict
from pathlib import Path
import difflib
import html
import re

from modules.models import DiffItem


DIRECTIVES_MAPPING = {
    "#Область": "## Область",
    "#КонецОбласти": "## КонецОбласти",
    "#Удаление": "## Удаление",
    "#КонецУдаления": "## КонецУдаления",
    "#Вставка": "## Вставка",
    "#КонецВставки": "## КонецВставки",
    "#Если": "## Если",
    "#КонецЕсли": "## КонецЕсли",
    "#@#": "// @",
}

IDENTIFIER_RE = re.compile(r"[A-Za-zА-Яа-яЁё_][A-Za-zА-Яа-яЁё0-9_]*")

BSL_KEYWORDS = {
    "если", "тогда", "иначе", "иначеесли", "конецесли",
    "для", "каждого", "из", "по", "цикл", "конеццикла",
    "пока", "конецпроцедуры", "конецфункции",
    "процедура", "функция", "возврат", "перем",
    "попытка", "исключение", "конецпопытки",
    "прервать", "продолжить", "новый", "знач",
    "не", "и", "или", "экспорт", "вызватьисключение",
    "истина", "ложь", "неопределено", "null",
}

BSL_PREPROCESSOR = {
    "#если", "#иначе", "#иначеесли", "#конецесли",
    "#область", "#конецобласти", "#вставка", "#конецвставки",
    "#удаление", "#конецудаления",
}

BSL_TOKEN_RE = re.compile(
    r'("([^"\\]|\\.)*")'
    r"|('([^'\\]|\\.)*')"
    r"|(\|.*$)"
    r"|(&[A-Za-zА-Яа-яЁё_][A-Za-zА-Яа-яЁё0-9_]*)"
    r"|(\#[A-Za-zА-Яа-яЁё_][A-Za-zА-Яа-яЁё0-9_]*)"
    r"|(\b\d+(?:\.\d+)?\b)"
    r"|([A-Za-zА-Яа-яЁё_][A-Za-zА-Яа-яЁё0-9_]*)",
    re.IGNORECASE,
)


def replace_preprocessor_directives(line: str) -> str:
    for directive, replacement in DIRECTIVES_MAPPING.items():
        line = line.replace(directive, replacement)
    return line


def identifier_matches_markers(identifier: str, starts_with: list[str], ends_with: list[str]) -> bool:
    return any(identifier.startswith(marker) for marker in starts_with) or any(identifier.endswith(marker) for marker in ends_with)


def diff_contains_our_markers(
    diff_lines: list[str],
    starts_with: list[str],
    ends_with: list[str],
    detect_in_identifier_start: bool,
    detect_in_identifier_end: bool,
    detect_in_comment_after_slashes: bool,
    detect_inside_word: bool = False,
) -> bool:
    for raw_line in diff_lines:
        line = str(raw_line)

        # ИСПРАВЛЕНИЕ: добавлен "+" — теперь проверяем и добавленные строки
        if len(line) < 2 or line[0] not in ("-", "+", "!") or line[1] != " ":
            continue

        code_part = line[2:]

        if detect_in_comment_after_slashes and "//" in code_part:
            _, comment_part = code_part.split("//", 1)
            comment_tokens = IDENTIFIER_RE.findall(str(comment_part))

            for token in comment_tokens:
                if isinstance(token, tuple):
                    token = "".join(token)

                if identifier_matches_markers(token, starts_with, ends_with):
                    return True

                if detect_inside_word and any(marker in token for marker in starts_with + ends_with):
                    return True

        tokens = IDENTIFIER_RE.findall(code_part)

        for token in tokens:
            if isinstance(token, tuple):
                token = "".join(token)

            if detect_in_identifier_start and any(token.startswith(marker) for marker in starts_with):
                return True

            if detect_in_identifier_end and any(token.endswith(marker) for marker in ends_with):
                return True

            if detect_inside_word and any(marker in token for marker in starts_with + ends_with):
                return True

    return False


def build_diff_lines(old_file: str, new_file: str, rewrite_bsl: bool) -> list[str]:
    try:
        with open(old_file, "r", encoding="utf-8-sig") as f1, open(new_file, "r", encoding="utf-8-sig") as f2:
            old_lines = f1.read().splitlines()
            new_lines = f2.read().splitlines()

        diff = list(difflib.context_diff(old_lines, new_lines, fromfile=old_file, tofile=new_file))
        if rewrite_bsl:
            diff = [replace_preprocessor_directives(str(line)) for line in diff]
        else:
            diff = [str(line) for line in diff]
        return diff
    except Exception as e:
        return [f"<!-- Ошибка при построении diff: {e} -->"]


def build_ndiff_lines(old_file: str, new_file: str, rewrite_bsl: bool) -> list[str]:
    try:
        with open(old_file, "r", encoding="utf-8-sig") as f1, open(new_file, "r", encoding="utf-8-sig") as f2:
            old_lines = f1.read().splitlines()
            new_lines = f2.read().splitlines()

        diff = list(difflib.ndiff(old_lines, new_lines))
        if rewrite_bsl:
            diff = [replace_preprocessor_directives(str(line)) for line in diff]
        else:
            diff = [str(line) for line in diff]
        return diff
    except Exception as e:
        return [f"<!-- Ошибка при построении ndiff: {e} -->"]


def shorten_line(text: str, max_length: int = 300) -> str:
    text = text.rstrip()
    if len(text) <= max_length:
        return text
    return text[: max_length - 3] + "..."


def detect_code_language(file_ext: str | None) -> str:
    ext = (file_ext or "").lower()
    if ext == ".xml":
        return "xml"
    if ext == ".bsl":
        return "bsl"
    return "text"


def highlight_bsl_line_no_comment(escaped_line: str) -> str:
    result: list[str] = []
    last_end = 0

    for match in BSL_TOKEN_RE.finditer(escaped_line):
        start, end = match.span()
        result.append(escaped_line[last_end:start])
        token = match.group(0)
        token_lower = html.unescape(token).lower()

        if token.startswith("&"):
            result.append(f'<span class="bsl-annotation">{token}</span>')
        elif token.startswith("#") and token_lower in BSL_PREPROCESSOR:
            result.append(f'<span class="bsl-preprocessor">{token}</span>')
        elif token.startswith("|"):
            result.append(f'<span class="bsl-string">{token}</span>')
        elif token.startswith('"') or token.startswith("'"):
            result.append(f'<span class="bsl-string">{token}</span>')
        elif re.fullmatch(r"\d+(?:\.\d+)?", html.unescape(token)):
            result.append(f'<span class="bsl-number">{token}</span>')
        elif token_lower in BSL_KEYWORDS:
            result.append(f'<span class="bsl-keyword">{token}</span>')
        else:
            result.append(f'<span class="bsl-identifier">{token}</span>')

        last_end = end

    result.append(escaped_line[last_end:])
    return "".join(result)


def highlight_bsl_line(line: str) -> str:
    plain = shorten_line(str(line))
    comment_index = plain.find("//")

    if comment_index >= 0:
        code_part = plain[:comment_index]
        comment_part = plain[comment_index:]
        escaped_code = html.escape(code_part)
        escaped_comment = html.escape(comment_part)
        return highlight_bsl_line_no_comment(escaped_code) + f'<span class="bsl-comment">{escaped_comment}</span>'

    return highlight_bsl_line_no_comment(html.escape(plain))


def render_plain_line(line: str) -> str:
    return html.escape(shorten_line(str(line)))


def render_diff_line(line: str, language: str) -> str:
    content = highlight_bsl_line(line) if language == "bsl" else render_plain_line(line)
    return f'<div class="diff-line"><code>{content}</code></div>'


def render_line_block(lines: list[str], language: str, wrapper_class: str) -> str:
    rendered_lines = "\n".join(render_diff_line(line, language) for line in lines) if lines else ""
    return "\n".join([
        f'<div class="{wrapper_class} diff-block">',
        rendered_lines,
        "</div>",
    ])


def collect_ndiff_blocks(
    ndiff_lines: list[str],
    max_blocks: int = 3,
    max_lines_per_block: int = 80,
) -> tuple[list[list[str]], list[list[str]], list[tuple[list[str], list[str]]]]:
    added_blocks: list[list[str]] = []
    removed_blocks: list[list[str]] = []
    changed_pairs: list[tuple[list[str], list[str]]] = []

    i = 0
    n = len(ndiff_lines)

    while i < n:
        line = str(ndiff_lines[i])

        if line.startswith("? "):
            i += 1
            continue

        if line.startswith("- "):
            removed_chunk: list[str] = []
            while i < n and str(ndiff_lines[i]).startswith("- "):
                removed_chunk.append(str(ndiff_lines[i])[2:])
                i += 1
                while i < n and str(ndiff_lines[i]).startswith("? "):
                    i += 1

            added_chunk: list[str] = []
            j = i
            while j < n and str(ndiff_lines[j]).startswith("+ "):
                added_chunk.append(str(ndiff_lines[j])[2:])
                j += 1
                while j < n and str(ndiff_lines[j]).startswith("? "):
                    j += 1

            if added_chunk:
                changed_pairs.append((
                    removed_chunk[:max_lines_per_block],
                    added_chunk[:max_lines_per_block],
                ))
                i = j
            else:
                removed_blocks.append(removed_chunk[:max_lines_per_block])

            if len(changed_pairs) >= max_blocks and len(removed_blocks) >= max_blocks and len(added_blocks) >= max_blocks:
                pass
            continue

        if line.startswith("+ "):
            added_chunk: list[str] = []
            while i < n and str(ndiff_lines[i]).startswith("+ "):
                added_chunk.append(str(ndiff_lines[i])[2:])
                i += 1
                while i < n and str(ndiff_lines[i]).startswith("? "):
                    i += 1

            added_blocks.append(added_chunk[:max_lines_per_block])
            continue

        i += 1

    return (
        added_blocks[:max_blocks],
        removed_blocks[:max_blocks],
        changed_pairs[:max_blocks],
    )


def write_item_markdown(
    output_dir: str,
    item: DiffItem,
    diff_lines: list[str] | None = None,
    ndiff_lines: list[str] | None = None,
) -> None:
    out_path = Path(output_dir) / f"{item.relative_path}.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    code_language = detect_code_language(item.file_ext)

    lines = [
        f"# {item.relative_path}",
        "",
        f"<!-- relative_path: {item.relative_path} -->",
        "",
        f"- Статус: {item.status}",
        f"- Расширение: {item.file_ext or 'без расширения'}",
        f"- Наш объект: {'да' if item.is_our_added else 'нет'}",
        f"- Наши маркеры в diff: {'да' if item.contains_our_markers else 'нет'}",
    ]

    if item.vendor_path:
        lines.append(f"- Путь вендора: `{item.vendor_path}`")
    if item.custom_path:
        lines.append(f"- Путь доработки: `{item.custom_path}`")

    lines.append("")

    if item.status == "modified" and diff_lines is not None:
        added_blocks, removed_blocks, changed_pairs = collect_ndiff_blocks(
            ndiff_lines or [], max_blocks=3, max_lines_per_block=80
        )

        added_count = sum(len(block) for block in added_blocks)
        removed_count = sum(len(block) for block in removed_blocks)
        changed_count = sum(max(len(old_block), len(new_block)) for old_block, new_block in changed_pairs)
        changed_fragments_count = len(changed_pairs)

        lines.append("## Кратко")
        lines.append("")
        lines.append(f"- Добавлено строк: {added_count}")
        lines.append(f"- Удалено строк: {removed_count}")
        lines.append(f"- Изменено строк: {changed_count}")
        lines.append(f"- Изменённых фрагментов: {changed_fragments_count}")
        lines.append("")

        if added_blocks:
            lines.append("## Добавлено")
            lines.append("")
            for block in added_blocks:
                lines.append(render_line_block(block, code_language, "diff-added-block"))
                lines.append("")

        if removed_blocks:
            lines.append("## Удалено")
            lines.append("")
            for block in removed_blocks:
                lines.append(render_line_block(block, code_language, "diff-removed-block"))
                lines.append("")

        if changed_pairs:
            lines.append("## Изменено")
            lines.append("")
            for old_block, new_block in changed_pairs:
                if old_block:
                    lines.append("### Было")
                    lines.append("")
                    lines.append(render_line_block(old_block, code_language, "diff-changed-old-block"))
                    lines.append("")
                if new_block:
                    lines.append("### Стало")
                    lines.append("")
                    lines.append(render_line_block(new_block, code_language, "diff-changed-new-block"))
                    lines.append("")

        lines.extend([
            "## Полный diff",
            "",
            "```diff",
            "\n".join(str(line) for line in diff_lines).rstrip(),
            "```",
        ])
    elif item.status == "added":
        lines.append("Файл есть только в доработанной версии.")
    elif item.status == "removed":
        lines.append("Файл есть только у вендора.")
    elif item.status == "unchanged":
        lines.append("Файл совпадает в обеих версиях.")

    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def group_items_by_top_dir(items: list[DiffItem]) -> dict[str, list[DiffItem]]:
    grouped: dict[str, list[DiffItem]] = defaultdict(list)

    for item in items:
        top_dir = str(item.relative_path).split("/", 1)[0]
        grouped[top_dir].append(item)

    return dict(sorted(grouped.items(), key=lambda x: x[0].lower()))


def build_grouped_index(title: str, items: list[DiffItem], intro_lines: list[str] | None = None) -> list[str]:
    lines = [f"# {title}", ""]

    if intro_lines:
        lines.extend(intro_lines)
        lines.append("")

    lines.append(f"- Количество: {len(items)}")
    lines.append("")

    grouped = group_items_by_top_dir(items)

    for top_dir, group_items in grouped.items():
        lines.append(f"## {top_dir}")
        lines.append("")
        for item in sorted(group_items, key=lambda x: str(x.relative_path).lower()):
            md_relative = f"{item.relative_path}.md"
            lines.append(f"- [{item.relative_path}]({md_relative})")
        lines.append("")

    return lines


def write_our_added_report(output_dir: str, report_name: str, items: list[DiffItem]) -> None:
    root = Path(output_dir)
    selected = [item for item in items if item.is_our_added]

    lines = build_grouped_index(
        "Наши добавленные объекты",
        selected,
        intro_lines=[
            "Сюда попадают файлы, которых нет у вендора, но они появились в нашей версии. "
            "При этом имя файла содержит наши маркеры — префиксы или суффиксы, которые мы заранее задали в конфиге. "
            "Программа по этим маркерам понимает: это наш объект, а не что-то новое от вендора.",
            "",
            "Пример: если наш префикс `АВ_`, то сюда попадёт отчёт `АВ_АнализПродаж`. "
            "Если наш суффикс `_бит`, то сюда попадёт справочник `Контрагенты_бит`.",
        ],
    )

    (root / report_name).write_text("\n".join(lines), encoding="utf-8")


def write_modified_with_markers_report(output_dir: str, report_name: str, items: list[DiffItem]) -> None:
    root = Path(output_dir)
    selected = [item for item in items if item.status == "modified" and item.contains_our_markers]

    lines = build_grouped_index(
        "Изменённые объекты с нашими маркерами",
        selected,
        intro_lines=[
            "Сюда попадают файлы, которые есть и у вендора, и у нас, но содержимое различается. "
            "При этом в изменённых строках программа нашла наши маркеры — наши идентификаторы, комментарии с пометками или префиксы.",
            "",
            "Это значит, что изменения, скорее всего, вносили мы. "
            "Такие объекты легко проверять, потому что видно, где именно наша доработка.",
        ],
    )

    (root / report_name).write_text("\n".join(lines), encoding="utf-8")


def write_modified_without_markers_report(output_dir: str, report_name: str, items: list[DiffItem]) -> None:
    root = Path(output_dir)
    selected = [item for item in items if item.status == "modified" and not item.contains_our_markers]

    lines = build_grouped_index(
        "Изменённые объекты без наших маркеров",
        selected,
        intro_lines=[
            "Сюда попадают файлы, которые тоже отличаются от вендора, но в изменениях наши маркеры не найдены. "
            "Это значит, что либо изменения делал вендор в новом релизе, либо мы вносили доработку, но не оставили в ней явных пометок.",
            "",
            "Эти файлы требуют ручной проверки. "
            "Нужно открыть и посмотреть: это вендор обновил форму документа, или мы два года назад добавили проверку без префикса и без комментария.",
        ],
    )

    (root / report_name).write_text("\n".join(lines), encoding="utf-8")


def write_removed_report(output_dir: str, items: list[DiffItem]) -> None:
    root = Path(output_dir)
    selected = [item for item in items if item.status == "removed"]

    lines = build_grouped_index(
        "Удалённые объекты",
        selected,
        intro_lines=[
            "Сюда попадают файлы, которые есть у вендора, но отсутствуют в доработанной версии. "
            "Возможно, они были удалены при обновлении или перенесены в другое место.",
        ],
    )

    (root / "REMOVED.md").write_text("\n".join(lines), encoding="utf-8")


def write_added_report(output_dir: str, items: list[DiffItem]) -> None:
    root = Path(output_dir)
    selected = [item for item in items if item.status == "added"]

    lines = build_grouped_index(
        "Все добавленные объекты",
        selected,
        intro_lines=[
            "Сюда попадают все файлы, которые есть только в доработанной версии — и наши, и любые другие, добавленные вендором или в процессе обновления.",
            "",
            "Чтобы увидеть только наши объекты, откройте отчёт [Наши добавленные объекты](OUR_ADDED.md).",
        ],
    )

    (root / "ADDED.md").write_text("\n".join(lines), encoding="utf-8")


def write_summary(output_dir: str, items: list[DiffItem], publish_unchanged: bool, project_info: dict[str, Any] | None = None) -> None:
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)

    counts = {
        "modified": 0,
        "added": 0,
        "removed": 0,
        "unchanged": 0,
        "our_added": 0,
        "modified_with_our_markers": 0,
        "modified_without_our_markers": 0,
    }

    for item in items:
        counts[item.status] += 1

        if item.is_our_added:
            counts["our_added"] += 1

        if item.status == "modified":
            if item.contains_our_markers:
                counts["modified_with_our_markers"] += 1
            else:
                counts["modified_without_our_markers"] += 1

    project = project_info or {}
    summary = []
    if project.get("name"):
        summary.append(f"# {project['name']}")
    else:
        summary.append("# Сводка")
    if project.get("description"):
        summary.append("")
        summary.append(project["description"])
    summary.extend([
        "",
        "Общая картина различий между вендорской и доработанной версиями.",
        "",
        f"- Всего добавлено объектов: {counts['added']}",
        f"- Из них распознано как наши: {counts['our_added']}",
        f"- Изменено с нашими маркерами: {counts['modified_with_our_markers']}",
        f"- Изменено без наших маркеров: {counts['modified_without_our_markers']}",
        f"- Удалено относительно вендора: {counts['removed']}",
        f"- Без изменений: {counts['unchanged']}",
        "",
        "## Отчёты",
        "",
        "- [Все добавленные объекты](ADDED.md)",
        "- [Наши добавленные объекты](OUR_ADDED.md)",
        "- [Изменённые объекты с нашими маркерами](MODIFIED_WITH_OUR_MARKERS.md)",
        "- [Изменённые объекты без наших маркеров](MODIFIED_WITHOUT_OUR_MARKERS.md)",
        "- [Удалённые объекты](REMOVED.md)",
        "- [Отчёт о запуске](run_report.md)",
        "",
    ])

    if publish_unchanged:
        summary.append("- [Файлы без изменений](UNCHANGED.md)")
        summary.append("")

    (root / "SUMMARY.md").write_text("\n".join(summary), encoding="utf-8")