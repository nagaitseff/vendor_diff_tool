from pathlib import Path
import os
import re

from modules.models import DiffItem


XML_REF_RE = re.compile(
    r"(CatalogRef|DocumentRef|EnumRef|ChartOfCharacteristicTypesRef|ChartOfAccountsRef|ChartOfCalculationTypesRef)\.([A-Za-zА-Яа-яЁё0-9_]+)"
)

RELATIVE_PATH_COMMENT_RE = re.compile(r"<!--\s*relative_path:\s*(.*?)\s*-->")

TYPE_TO_FOLDER = {
    "CatalogRef": "Catalogs",
    "DocumentRef": "Documents",
    "EnumRef": "Enums",
    "ChartOfCharacteristicTypesRef": "ChartsOfCharacteristicTypes",
    "ChartOfAccountsRef": "ChartsOfAccounts",
    "ChartOfCalculationTypesRef": "ChartsOfCalculationTypes",
}


def object_ref_fallback_path(objects_dir: str, ref_type: str, ref_name: str) -> Path:
    return Path(objects_dir) / ref_type / ref_name / "index.md"


def object_ref_real_object_path(ref_type: str, ref_name: str) -> Path | None:
    folder = TYPE_TO_FOLDER.get(ref_type)
    if not folder:
        return None
    return Path(folder) / f"{ref_name}.xml.md"


def resolve_best_target(output_dir: Path, objects_dir: str, ref_type: str, ref_name: str) -> Path:
    real_object = object_ref_real_object_path(ref_type, ref_name)
    if real_object is not None and (output_dir / real_object).exists():
        return real_object
    return object_ref_fallback_path(objects_dir, ref_type, ref_name)


def make_relative_link(from_md: Path, to_md: Path) -> str:
    return os.path.relpath(to_md, start=from_md.parent).replace("\\", "/")


def ensure_fallback_object_page(output_dir: Path, objects_dir: str, ref_type: str, ref_name: str) -> None:
    out_path = output_dir / object_ref_fallback_path(objects_dir, ref_type, ref_name)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if not out_path.exists():
        out_path.write_text(
            "\n".join([
                f"# {ref_name}",
                "",
                f"Тип объекта: {ref_type}",
                "Источник: автоматически создано из XML-ссылки",
                "",
            ]) + "\n",
            encoding="utf-8",
        )


def extract_relative_path_from_md(md_file: Path) -> str | None:
    text = md_file.read_text(encoding="utf-8")
    match = RELATIVE_PATH_COMMENT_RE.search(text)
    if not match:
        return None
    return match.group(1).strip()


def append_related_files_block(md_file: Path, related_targets: list[tuple[str, str]]) -> bool:
    text = md_file.read_text(encoding="utf-8")

    marker = "\n## Связанные файлы\n"
    if marker in text:
        text = text.split(marker, 1)[0].rstrip() + "\n"

    lines = [
        "",
        "## Связанные файлы",
        "",
    ]

    if related_targets:
        for label, relative_link in related_targets:
            lines.append(f"- [{label}]({relative_link})")
    else:
        lines.append("Связанные файлы не обнаружены.")

    lines.append("")

    new_text = text.rstrip() + "\n" + "\n".join(lines)
    md_file.write_text(new_text, encoding="utf-8")
    return True


def link_xml_references_in_file(md_file: Path, output_dir: Path, objects_dir: str) -> int:
    text = md_file.read_text(encoding="utf-8")
    found_refs = set(XML_REF_RE.findall(text))

    replacements = 0
    related_targets: list[tuple[str, str]] = []
    seen_related: set[str] = set()

    for ref_type, ref_name in sorted(found_refs):
        ensure_fallback_object_page(output_dir, objects_dir, ref_type, ref_name)

        target_path = resolve_best_target(output_dir, objects_dir, ref_type, ref_name)
        relative_link = make_relative_link(md_file, output_dir / target_path)

        plain_text = f"{ref_type}.{ref_name}"
        markdown_link = f"[{plain_text}]({relative_link})"

        if markdown_link not in text:
            new_text = text.replace(plain_text, markdown_link)
            if new_text != text:
                replacements += 1
                text = new_text

        related_key = f"{plain_text}|{relative_link}"
        if related_key not in seen_related:
            seen_related.add(related_key)
            related_targets.append((plain_text, relative_link))

    if text != md_file.read_text(encoding="utf-8"):
        md_file.write_text(text, encoding="utf-8")

    append_related_files_block(md_file, related_targets)
    return replacements + len(related_targets)


def link_xml_objects(output_dir: str, items: list[DiffItem], objects_dir: str) -> int:
    root = Path(output_dir)
    generated_pages = 0

    for item in items:
        if item.status == "unchanged":
            continue

        md_file = root / f"{item.relative_path}.md"
        if md_file.exists():
            generated_pages += link_xml_references_in_file(md_file, root, objects_dir)

    return generated_pages