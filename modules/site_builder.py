import shutil
from pathlib import Path


TRASH_MD_NAMES = {
    "Help.xml.md",
    "ConfigDumpInfo.xml.md",
    "Configuration.xml.md",
}

CORE_REPORTS = [
    "SUMMARY.md",
    "ADDED.md",
    "OUR_ADDED.md",
    "MODIFIED_WITH_OUR_MARKERS.md",
    "MODIFIED_WITHOUT_OUR_MARKERS.md",
    "REMOVED.md",
    "run_report.md",
]


def build_extra_css(code_font_size: str, diff_summary_font_size: str) -> str:
    return f"""\
.md-typeset .diff-block {{
  margin: 0 0 1rem 0;
  border-radius: 8px;
  overflow: hidden;
  font-family: var(--md-code-font-family, monospace);
  font-size: {diff_summary_font_size};
  line-height: 1.25;
}}

.md-typeset .diff-block .diff-line {{
  padding: 0.2rem 1rem;
  white-space: pre-wrap;
  word-break: break-word;
  overflow-wrap: anywhere;
}}

.md-typeset .diff-block .diff-line code {{
  display: block;
  background: transparent;
  padding: 0;
  margin: 0;
  font-size: inherit;
  line-height: inherit;
  color: inherit;
  box-shadow: none;
}}

.md-typeset .diff-added-block,
.md-typeset .diff-removed-block,
.md-typeset .diff-changed-old-block,
.md-typeset .diff-changed-new-block {{
  margin: 0 0 1rem 0;
  border-radius: 8px;
  overflow: hidden;
  font-size: {diff_summary_font_size};
  line-height: 1.25;
}}

.md-typeset .diff-added-block {{
  border-left: 4px solid #2e7d32;
  background: rgba(46, 125, 50, 0.10);
}}

.md-typeset .diff-removed-block {{
  border-left: 4px solid #c62828;
  background: rgba(198, 40, 40, 0.10);
}}

.md-typeset .diff-changed-old-block {{
  border-left: 4px solid #7e57c2;
  background: rgba(126, 87, 194, 0.20);
}}

.md-typeset .diff-changed-new-block {{
  border-left: 4px solid #5e35b1;
  background: rgba(94, 53, 177, 0.20);
}}

.md-typeset .diff-added-block .diff-line {{
  color: #12351d;
}}

.md-typeset .diff-removed-block .diff-line {{
  color: #4a1414;
}}

.md-typeset .diff-changed-old-block .diff-line,
.md-typeset .diff-changed-new-block .diff-line {{
  color: #24163a;
}}

.md-typeset pre,
.md-typeset pre code {{
  white-space: pre-wrap;
  word-break: break-word;
  overflow-wrap: anywhere;
  line-height: 1.15;
  font-size: {code_font_size};
}}

.md-typeset .language-diff {{
  font-size: {code_font_size};
}}

.md-typeset .bsl-code-block {{
  margin: 0;
  padding: 0.85rem 1rem;
  white-space: pre-wrap;
  word-break: break-word;
  overflow-wrap: anywhere;
  line-height: 1.15;
  font-size: {code_font_size};
  background: transparent;
}}

.md-typeset .bsl-code-block .bsl-keyword,
.md-typeset .diff-block .bsl-keyword {{
  color: #0b57d0;
  font-weight: 700;
}}

.md-typeset .bsl-code-block .bsl-number,
.md-typeset .diff-block .bsl-number {{
  color: #b26a00;
}}

.md-typeset .bsl-code-block .bsl-string,
.md-typeset .diff-block .bsl-string {{
  color: #2e7d32;
}}

.md-typeset .bsl-code-block .bsl-comment,
.md-typeset .diff-block .bsl-comment {{
  color: #6b7280;
  font-style: italic;
}}

.md-typeset .bsl-code-block .bsl-preprocessor,
.md-typeset .diff-block .bsl-preprocessor {{
  color: #7b1fa2;
  font-weight: 700;
}}

.md-typeset .bsl-code-block .bsl-annotation,
.md-typeset .diff-block .bsl-annotation {{
  color: #8e24aa;
}}

.md-typeset .bsl-code-block .bsl-identifier,
.md-typeset .diff-block .bsl-identifier {{
  color: inherit;
}}

.md-typeset h2 {{
  margin-top: 1.8rem;
}}

.md-typeset h3 {{
  margin-top: 1.2rem;
}}

.md-typeset ul li {{
  margin-bottom: 0.2rem;
}}

[data-md-color-scheme="slate"] .md-typeset .diff-added-block {{
  background: rgba(76, 175, 80, 0.16);
}}

[data-md-color-scheme="slate"] .md-typeset .diff-removed-block {{
  background: rgba(244, 67, 54, 0.16);
}}

[data-md-color-scheme="slate"] .md-typeset .diff-changed-old-block {{
  background: rgba(149, 117, 205, 0.24);
}}

[data-md-color-scheme="slate"] .md-typeset .diff-changed-new-block {{
  background: rgba(126, 87, 194, 0.24);
}}

[data-md-color-scheme="slate"] .md-typeset .diff-added-block .diff-line {{
  color: #ecfff1;
}}

[data-md-color-scheme="slate"] .md-typeset .diff-removed-block .diff-line {{
  color: #ffecec;
}}

[data-md-color-scheme="slate"] .md-typeset .diff-changed-old-block .diff-line,
[data-md-color-scheme="slate"] .md-typeset .diff-changed-new-block .diff-line {{
  color: #f6f0ff;
}}

[data-md-color-scheme="slate"] .md-typeset .bsl-code-block .bsl-comment,
[data-md-color-scheme="slate"] .md-typeset .diff-block .bsl-comment {{
  color: #c0c4cc;
}}
"""


def _prepare_site_root(
    site_docs_dir: str,
    code_font_size: str,
    diff_summary_font_size: str,
) -> Path:
    target_root = Path(site_docs_dir)

    if target_root.exists():
        shutil.rmtree(target_root)
    target_root.mkdir(parents=True, exist_ok=True)

    index_md = target_root / "index.md"
    index_md.write_text(
        "\n".join(
            [
                "# Vendor Diff Tool",
                "",
                "Результаты сравнения вендорской и доработанной версий.",
                "",
                "## Разделы",
                "",
                "- [Сводка](SUMMARY.md)",
                "- [Все добавленные объекты](ADDED.md)",
                "- [Наши добавленные объекты](OUR_ADDED.md)",
                "- [Изменённые объекты с нашими маркерами](MODIFIED_WITH_OUR_MARKERS.md)",
                "- [Изменённые объекты без наших маркеров](MODIFIED_WITHOUT_OUR_MARKERS.md)",
                "- [Удалённые объекты](REMOVED.md)",
                "- [Отчёт о запуске](run_report.md)",
                "",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    css_dir = target_root / "stylesheets"
    css_dir.mkdir(parents=True, exist_ok=True)
    (css_dir / "extra.css").write_text(
        build_extra_css(code_font_size, diff_summary_font_size),
        encoding="utf-8",
    )

    return target_root


def _copy_output_tree(source_root: Path, target_root: Path) -> None:
    for path in source_root.rglob("*"):
        rel = path.relative_to(source_root)
        dst = target_root / rel

        if path.is_dir():
            dst.mkdir(parents=True, exist_ok=True)
            continue

        if path.suffix.lower() == ".md" and path.name in TRASH_MD_NAMES:
            continue

        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dst)


def build_site_docs(
    output_dir: str,
    site_docs_dir: str = "site_docs",
    code_font_size: str = "10pt",
    diff_summary_font_size: str = "8pt",
) -> None:
    source_root = Path(output_dir)
    if not source_root.exists():
        raise FileNotFoundError(
            f"Каталог результата не найден: {source_root}\n"
            f"Сначала выполните: python main.py run --config config.yaml"
        )

    target_root = _prepare_site_root(
        site_docs_dir,
        code_font_size,
        diff_summary_font_size,
    )
    _copy_output_tree(source_root, target_root)


def build_site_docs_fast(
    output_dir: str,
    site_docs_dir: str = "site_docs",
    code_font_size: str = "10pt",
    diff_summary_font_size: str = "8pt",
) -> None:
    source_root = Path(output_dir)
    if not source_root.exists():
        raise FileNotFoundError(
            f"Каталог результата не найден: {source_root}\n"
            f"Сначала выполните хотя бы один успешный run или resume-markdown."
        )

    target_root = _prepare_site_root(
        site_docs_dir,
        code_font_size,
        diff_summary_font_size,
    )
    _copy_output_tree(source_root, target_root)