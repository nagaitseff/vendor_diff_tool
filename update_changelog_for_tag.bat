@echo off
if "%~1"=="" (
    echo Использование: scripts\update_changelog_for_tag.bat v0.1.0
    exit /b 1
)

git cliff --tag %1 -o CHANGELOG.md
if %errorlevel% neq 0 (
    echo Не удалось обновить CHANGELOG.md для тега %1
    exit /b %errorlevel%
)
echo CHANGELOG.md обновлен для тега %1