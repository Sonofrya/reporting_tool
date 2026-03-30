@echo off
chcp 65001 >nul
echo ======================================
echo  Сборка .exe для анализа обучения ОС ГД
echo ======================================
echo.
echo Убедитесь, что установлены:
echo   pip install pyinstaller pandas openpyxl customtkinter matplotlib
echo.

pyinstaller --onefile --windowed --name "Анализ_обучения_ОСГД" --add-data "courses.json;." "для_ос_гд_с_подсчетом_за_2026_год_gui.py"

echo.
echo Готово! Файл .exe находится в папке dist\
pause
