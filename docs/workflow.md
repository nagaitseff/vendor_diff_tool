# Workflow

## Зачем нужен этот документ

Здесь собран обычный рабочий порядок использования Vendor Diff Tool: от подготовки окружения до просмотра результата и локального сайта.

Документ нужен как практическая памятка, а не как формальное описание всех команд и внутренних модулей.

## Подготовка окружения

Если окружение ещё не создано:

```bat
cd /d C:\REP\vendor_diff_tool
python -m venv .venv
.venv\Scripts\activate
```

Если окружение уже существует, обычно достаточно:

```bat
cd /d C:\REP\vendor_diff_tool
.venv\Scripts\activate
```

## Установка зависимостей

Основная зависимость проекта:

```bat
python -m pip install --no-index --find-links=.\packages PyYAML==6.0.3
```

Если нужен локальный сайт:

```bat
python -m pip install --no-index --find-links=.\packages mkdocs==1.6.1 mkdocs-material==9.5.34
```

## Подготовка конфига

Если `config.yaml` ещё не создан:

```bat
python main.py init-config
```

После этого нужно открыть `config.yaml` и проверить:

- путь к каталогу вендора;
- путь к доработанному каталогу;
- путь к каталогу результата;
- маркеры собственных объектов;
- служебные файлы в `scan.exclude_files_exact` — обычно рекомендуется исключить как минимум `ConfigDumpInfo.xml`, `Help.xml`, `Configuration.xml`;
- настройки сайта в секции `site`, если нужно изменить размер diff-блоков.

Пример настройки размеров для сайта:

```yaml
site:
  code_font_size: 8pt
  diff_summary_font_size: 7pt
```

`code_font_size` используется для полного diff и обычных кодовых блоков. `diff_summary_font_size` используется для кратких цветных блоков `Что добавлено`, `Что удалено`, `Было`, `Стало`.

## Диагностика перед запуском

Перед основным запуском удобно сначала проверить проект:

```bat
python main.py doctor --config config.yaml
```

Команда `doctor`:

- проверяет наличие `config.yaml`;
- загружает и валидирует конфиг;
- проверяет каталоги `output_dir` и `site_docs`;
- проверяет наличие кэша для `resume-markdown`;
- контролирует наличие ключевых файлов проекта;
- проверяет python-импорты основных модулей;
- проверяет контракт моделей в `models.py`;
- ищет битые Markdown-ссылки в `output_dir` и `site_docs`;
- пишет отчёт в `doctor_report.json`.

Если есть ошибки уровня `ERROR`, код возврата будет 1.

## Основной запуск

Полный запуск:

```bat
python main.py run --config config.yaml
```

На практике это основной рабочий сценарий, когда нужно пересчитать результат целиком и заново получить Markdown-отчёты и сайт.

После завершения полного запуска можно отдельно пересобрать сайт:

```bat
python main.py build-site --config config.yaml
python -m mkdocs serve
```

## Как читать результат

Обычно удобнее идти в таком порядке.

Сначала открыть `SUMMARY.md`, чтобы увидеть общую картину. Затем посмотреть `OUR_ADDED.md`, потому что там собраны именно собственные добавленные объекты. После этого уже разбирать `MODIFIED_WITH_OUR_MARKERS.md` и `MODIFIED_WITHOUT_OUR_MARKERS.md`.

`REMOVED.md` лучше смотреть отдельно, потому что это отдельный смысловой класс различий.

## Как читать карточку modified-объекта

У modified-объекта карточка строится в несколько слоёв.

Сначала идёт блок `Кратко`, где видно:

- сколько строк добавлено;
- сколько строк удалено;
- сколько строк изменено;
- сколько изменённых фрагментов.

Ниже идут блоки `Что добавлено` и `Что удалено`, где изменения показываются цельными фрагментами, чтобы не терялась структура XML или BSL. Ниже расположен блок `Что изменено` с подразделами `Было` и `Стало`. В конце расположен `Полный diff`, если нужен весь контекст изменения.

Если нужно сделать краткие цветные блоки компактнее, используется параметр `site.diff_summary_font_size`. Если нужно уменьшить именно полный diff и обычные кодовые блоки, используется `site.code_font_size`.

## Подготовка локального сайта

После завершения сравнения полный сценарий выглядит так:

```bat
python main.py build-site --config config.yaml
python -m mkdocs serve
```

Команда `build-site` пересобирает каталог `site_docs`, создаёт служебные файлы и копирует Markdown-результаты из `output_dir`.

В сайт попадают:

- основные отчёты (`SUMMARY.md`, `ADDED.md`, `OUR_ADDED.md`, `MODIFIED_*`, `REMOVED.md`, `run_report.md`);
- карточки объектов;
- дополнительные Markdown-страницы, которые присутствуют в результате;
- служебный `index.md` и `stylesheets/extra.css`.

Мусорные страницы вида `Help.xml.md`, `ConfigDumpInfo.xml.md`, `Configuration.xml.md` в сайт не копируются.

Сборка статического сайта:

```bat
python -m mkdocs build
```

## Быстрый цикл

Если полное сравнение уже выполнялось и нужно быстро пересобрать представление результата, можно использовать быстрый сценарий.

### Вариант 1: повторная генерация Markdown

```bat
python main.py resume-markdown --config config.yaml
python main.py build-site-fast --config config.yaml
python -m mkdocs serve
```

Команда `resume-markdown` использует кэш:

- `output_dir/.cache/items_after_compare.json`

Она повторно генерирует Markdown и итоговые отчёты без нового полного сканирования каталогов. После этого `build-site-fast` пересобирает `site_docs`, используя уже готовый `output_dir`.

### Вариант 2: только сайт

Если менять нужно только CSS сайта или навигацию, без повторной генерации Markdown, достаточно:

```bat
python main.py build-site-fast --config config.yaml
python -m mkdocs serve
```

## Повторный запуск

Если изменились настройки, код или правила классификации, результат лучше пересобирать полностью:

```bat
cd /d C:\REP\vendor_diff_tool
.venv\Scripts\activate
python main.py doctor --config config.yaml
python main.py run --config config.yaml
python main.py build-site --config config.yaml
python -m mkdocs serve
```

Если изменения точечные и затрагивают только представление результата, можно использовать быстрый сценарий с `resume-markdown` и `build-site-fast`.

## Время выполнения

В конце запуска программа показывает длительность каждого шага.

Отдельные шаги записываются в `run_report.md`. Для оперативной диагностики обычно достаточно смотреть консольный вывод и сам `run_report.md`.

## Практический минимум

Если нужен самый короткий рабочий цикл, обычно хватает такой последовательности:

```bat
cd /d C:\REP\vendor_diff_tool
.venv\Scripts\activate
python main.py doctor --config config.yaml
python main.py run --config config.yaml
python -m mkdocs serve
```

Если нужно только обновить оформление сайта:

```bat
cd /d C:\REP\vendor_diff_tool
.venv\Scripts\activate
python main.py build-site-fast --config config.yaml
python -m mkdocs serve
```