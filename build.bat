@echo off
chcp 65001 >nul
echo ======================================
echo  Сборка .exe для анализа обучения ОС ГД
echo ======================================
echo.
echo Убедитесь, что установлены:
echo   pip install pyinstaller pandas openpyxl
echo.

pyinstaller --onefile --console --name "Анализ_обучения_ОСГД" "для_ос_гд_с_подсчетом_за_2026_год.py"

echo.
echo Готово! Файл .exe находится в папке dist\
pause
