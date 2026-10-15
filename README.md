# Vendor Diff Tool

Инструмент для сравнения доработанной выгрузки 1С с чистым релизом вендора.

Текущая версия: `0.1.0`

## Что делает программа

Утилита сравнивает два каталога: чистую выгрузку вендора и доработанную версию. На выходе она формирует Markdown-результат, по которому можно быстро понять, какие объекты добавлены, какие изменены, какие удалены и где в diff обнаружены наши маркеры.

Результат можно читать как обычные Markdown-файлы, открывать в Obsidian и публиковать как локальный сайт через MkDocs.

## Что получается на выходе

После запуска формируются основные файлы:

- `SUMMARY.md` — сводка по результату
- `ADDED.md` — все объекты, присутствующие только в доработанной версии
- `OUR_ADDED.md` — только наши добавленные объекты
- `MODIFIED_WITH_OUR_MARKERS.md` — изменённые объекты, в diff которых найдены наши маркеры
- `MODIFIED_WITHOUT_OUR_MARKERS.md` — изменённые объекты без наших маркеров
- `REMOVED.md` — объекты, которые есть у вендора, но отсутствуют в доработанной версии
- `run_report.md` — технический отчёт по запуску

Кроме индексных файлов формируются карточки по каждому объекту и дополнительные ссылки по XML-связям.

## Как понимать категории

### Added

Все файлы, которые есть только в доработанной версии.

### Our Added

Подмножество added. Сюда попадают только те добавленные объекты, которые распознаны как наши по маркерам имени.

### Modified With Our Markers

Файлы отличаются от вендора, и в diff обнаружены наши маркеры.

### Modified Without Our Markers

Файлы отличаются от вендора, но по текущим правилам в diff не найдены наши маркеры.

### Removed

Файлы есть у вендора, но отсутствуют в доработанной версии.

## Требования

Для работы нужны:

- Python 3.14 x64
- `venv`
- `pip`
- `PyYAML`

Для локального сайта дополнительно нужны:

- `mkdocs`
- `mkdocs-material`

Если работа идёт за прокси, пакеты можно заранее скачать вручную и положить в каталог `packages`.

## Подготовка окружения

```bat
cd /d C:\REP\vendor_diff_tool
python -m venv .venv
.venv\Scripts\activate
```

После активации окружения можно установить зависимости из локального каталога `packages`.

Пример установки основной зависимости:

```bat
python -m pip install --no-index --find-links=.\packages PyYAML==6.0.3
```

Пример установки MkDocs:

```bat
python -m pip install --no-index --find-links=.\packages mkdocs==1.6.1 mkdocs-material==9.5.34
```

## Первый запуск

Если рабочего конфига ещё нет:

```bat
python main.py init-config
```

Команда копирует шаблон `config.example.yaml` из каталога `modules/` и создаёт рабочий `config.yaml` рядом с `main.py`.

После этого откройте `config.yaml` и проверьте пути, фильтры и маркеры.

Проверка версии:

```bat
python main.py version
```

Полная диагностика проекта:

```bat
python main.py doctor --config config.yaml
```

`doctor` проверит:

- наличие и валидность `config.yaml`;
- пути проекта;
- импорты Python-модулей;
- наличие кэша для `resume-markdown`;
- наличие `site_docs`;
- внутренние Markdown-ссылки в `output_dir` и `site_docs`.

Результат выводится в консоль и дополнительно записывается в `doctor_report.json`.

Основной запуск:

```bat
python main.py run --config config.yaml
```

## Многопоточность

Сравнение файлов и генерация Markdown выполняются параллельно. Количество потоков настраивается в `config.yaml`:

```yaml
performance:
  # Количество параллельных потоков.
  # null = авто (число ядер CPU * 2, но не более 16).
  # Укажите число, если хотите ограничить нагрузку.
  max_workers: null
```

При запуске в консоли отображается прогресс:
Сравнение файлов: 137493 объектов, потоков: 16
Сравнено 5000/137493
Сравнено 10000/137493
...
Генерация Markdown: 5000 файлов, потоков: 16
Сгенерировано 1000/5000
Сгенерировано 2000/5000


## Подготовка сайта

После основного запуска можно собрать содержимое для локального сайта.

Полный режим:

```bat
python main.py build-site --config config.yaml
```

Команда пересобирает каталог `site_docs`, создаёт `index.md`, подключает `stylesheets/extra.css` и копирует Markdown-результаты из `output_dir`, кроме служебных мусорных файлов:

- `Help.xml.md`
- `ConfigDumpInfo.xml.md`
- `Configuration.xml.md`

Быстрый режим:

```bat
python main.py build-site-fast --config config.yaml
```

Команда пересобирает только `site_docs`, используя уже готовый `output_dir`. Это удобно для повторных проверок CSS, навигации и оформления.

Запуск локального сайта выполняется через активированное окружение:

```bat
.venv\Scripts\activate
python -m mkdocs serve
```

Сборка статического сайта:

```bat
python -m mkdocs build
```

## Resume-markdown

Для `resume-markdown` используется кэш:

- `output_dir/.cache/items_after_compare.json`

Если кэш отсутствует, сначала нужно выполнить хотя бы один полный `run`.

Команда продолжения:

```bat
python main.py resume-markdown --config config.yaml
```

Этот режим пересобирает Markdown-отчёты без повторного полного сравнения файлов.

## Как читать modified-файлы

Для изменённых объектов в карточке есть три уровня детализации.

Сначала идёт краткая сводка:

- сколько строк добавлено;
- сколько удалено;
- сколько изменено;
- сколько изменённых фрагментов.

Затем идут блоки `Что добавлено` и `Что удалено`, где изменения показываются цельными фрагментами кода. Ниже идёт блок `Что изменено` с разделением на `Было` и `Стало`. После этого можно открыть `Полный diff`, если нужен весь контекст.

Такой формат удобнее обычного списка строк, потому что сохраняет структуру XML- или BSL-фрагмента.

## Формат времени

Время выполнения шагов показывается так:

- до 60 секунд — в секундах;
- больше минуты — в минутах и секундах;
- больше часа — в часах, минутах и секундах.

Этот формат используется и в консоли, и в `run_report.md`.

## Конфигурация

Основные настройки лежат в `config.yaml`, шаблон — в `modules/config.example.yaml`.

### project

Общая информация о проекте:

- `name`
- `version`
- `description`

### paths

Пути к каталогам:

- `vendor_dir`
- `custom_dir`
- `output_dir`

### scan

Настройки сканирования:

- `include_extensions`
- `exclude_dirs_prefixes`
- `exclude_files_prefixes`
- `exclude_files_exact`

По умолчанию в `exclude_files_exact` рекомендуется указать служебные файлы выгрузки конфигурации:

- `ConfigDumpInfo.xml`
- `Help.xml`
- `Configuration.xml`

Они не несут полезной нагрузки для анализа diff и засоряют структуру каталога.

### classification

Настройки распознавания собственных объектов и собственных изменений.

#### custom_name_markers

Списки:

- `starts_with`
- `ends_with`

#### content_detection

Логика анализа diff:

- `enabled`
- `detect_in_identifier_start`
- `detect_in_identifier_end`
- `detect_in_comment_after_slashes`
- `detect_inside_word`

### compare

- `mode`
- `publish_unchanged`

### markdown

- `rewrite_bsl_directives`
- `create_summary_files`

### reports

Настройки генерации отчётов и их имён.

### site

Настройки презентации в локальном сайте:

- `code_font_size` — размер шрифта для полного diff и обычных кодовых блоков;
- `diff_summary_font_size` — размер шрифта для кратких цветных блоков `Что добавлено`, `Что удалено`, `Было`, `Стало`.

Пример:

```yaml
site:
  code_font_size: 8pt
  diff_summary_font_size: 7pt
```

### obsidian

Настройки карточек объектов и XML-связей.

### performance

Настройки многопоточности:

```yaml
performance:
  max_workers: null
```

- `null` — авто (число ядер CPU * 2, но не более 32);
- число — фиксированное количество потоков.

## Порядок работы

Перед любыми командами сначала перейди в каталог проекта и активируй окружение:

```bat
cd /d C:\REP\vendor_diff_tool
.venv\Scripts\activate
```

Обычный рабочий сценарий:

1. Проверить `config.yaml`.
2. Выполнить `python main.py doctor --config config.yaml`.
3. Выполнить `python main.py run --config config.yaml`.
4. Открыть `SUMMARY.md`.
5. Посмотреть `OUR_ADDED.md`.
6. Затем перейти к `MODIFIED_WITH_OUR_MARKERS.md`.
7. Потом к `MODIFIED_WITHOUT_OUR_MARKERS.md`.
8. Отдельно посмотреть `REMOVED.md`.
9. Собрать статический сайт и скопировать на веб-сервер:

```bat
python -m mkdocs build
xcopy /E /I /Y C:\REP\vendor_diff_tool\site\* C:\inetpub\wwwroot\vendor_diff\
```

После этого сайт доступен по адресу сервера без запуска консольных команд.

## Быстрый цикл

Перед любыми командами сначала перейди в каталог проекта и активируй окружение:

```bat
cd /d C:\REP\vendor_diff_tool
.venv\Scripts\activate
```

Если код diff и конфиг уже отлажены, а правки касаются только оформления сайта или Markdown-представления:

```bat
python main.py resume-markdown --config config.yaml
python main.py build-site-fast --config config.yaml
python -m mkdocs build
xcopy /E /I /Y C:\REP\vendor_diff_tool\site\* C:\inetpub\wwwroot\vendor_diff\
```

Если правки касаются только CSS сайта:

```bat
python main.py build-site-fast --config config.yaml
python -m mkdocs build
xcopy /E /I /Y C:\REP\vendor_diff_tool\site\* C:\inetpub\wwwroot\vendor_diff\
```

Если сайт уже собран и нужно только обновить файлы на сервере:

```bat
xcopy /E /I /Y C:\REP\vendor_diff_tool\site\* C:\inetpub\wwwroot\vendor_diff\
```

## Changelog

Для истории изменений используется `git-cliff`.

Основные файлы:

- `cliff.toml`
- `CHANGELOG.md`

Обновление changelog:

```bat
git cliff -o CHANGELOG.md
```