@echo off
git cliff -o CHANGELOG.md
if %errorlevel% neq 0 (
    echo Не удалось обновить CHANGELOG.md
    exit /b %errorlevel%
)
echo CHANGELOG.md обновлен