# -*- coding: utf-8 -*-
"""
Анализ обучения ОС ГД с подсчётом по годам.

При запуске открывается диалог выбора файлов.
Результаты выводятся в консоль и сохраняются в Excel.

Списки курсов загружаются из courses.json.
"""

import json
import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox

import pandas as pd

# ============================================================
# ЗАГРУЗКА СПИСКОВ КУРСОВ ИЗ JSON
# ============================================================
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
COURSES_PATH = os.path.join(_SCRIPT_DIR, "courses.json")


def load_courses():
    """Загружает списки курсов из courses.json."""
    with open(COURSES_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return set(data["BP"]), set(data["IT"]), set(data["PRM"])


BP_COURSES, IT_COURSES, PRM_COURSES = load_courses()
ALL_KNOWN_COURSES = BP_COURSES | IT_COURSES


# ============================================================
# ФУНКЦИИ
# ============================================================

def select_file(title, initial_dir=None):
    """Открывает диалог выбора xlsx-файла и возвращает путь."""
    root = tk.Tk()
    root.withdraw()
    root.attributes('-topmost', True)
    file_path = filedialog.askopenfilename(
        title=title,
        initialdir=initial_dir or os.path.expanduser("~"),
        filetypes=[("Excel файлы", "*.xlsx"), ("Все файлы", "*.*")],
    )
    root.destroy()
    if not file_path:
        print(f"Файл не выбран ({title}). Выход.")
        sys.exit(0)
    return file_path


def calc_stats(df):
    """Рассчитывает показатели по срезу данных."""
    BP = df[df['Название'].isin(BP_COURSES)]
    IT = df[df['Название'].isin(IT_COURSES)]
    PRM = df[df['Название'].isin(PRM_COURSES)]

    uniques_BP = pd.unique(BP['ФИО участника'])
    uniques_IT = pd.unique(IT['ФИО участника'])
    uniques_PRM = pd.unique(PRM['ФИО участника'])

    return {
        "total_unique": len(uniques_BP) + len(uniques_IT),
        "unique_BP": len(uniques_BP),
        "unique_IT": len(uniques_IT),
        "unique_PRM": len(uniques_PRM),
        "person_courses": len(BP) + len(IT),
        "person_courses_BP": len(BP),
        "person_courses_IT": len(IT),
    }


def find_unclassified(df):
    """Возвращает список названий курсов, не входящих ни в одну категорию."""
    all_courses_in_data = set(df['Название'].dropna().unique())
    return sorted(all_courses_in_data - ALL_KNOWN_COURSES)


def print_stats(label, stats):
    """Выводит статистику в консоль."""
    print(f"\n{label}:")
    print(f"  Всего уникальных (BP+IT): {stats['total_unique']}")
    print(f"  Уникальных BP:            {stats['unique_BP']}")
    print(f"  Уникальных IT:            {stats['unique_IT']}")
    print(f"  Уникальных ПРМ:           {stats['unique_PRM']}")
    print(f"  Человеко-курсов:          {stats['person_courses']}")
    print(f"    из них BP:              {stats['person_courses_BP']}")
    print(f"    из них IT:              {stats['person_courses_IT']}")


# ============================================================
# ОСНОВНАЯ ЛОГИКА
# ============================================================

def main():
    print("=" * 60)
    print("  Анализ обучения ОС ГД — выберите файлы")
    print("=" * 60)

    # --- 1. Выбор файлов ---
    new_file = select_file("Выберите НОВЫЙ файл данных (выгрузка из ОС ГД, xlsx)")
    prev_file = select_file("Выберите ИТОГОВЫЙ (накопительный) файл — Fnl*.xlsx")

    print(f"\nНовый файл:        {new_file}")
    print(f"Итоговый файл:     {prev_file}")

    # --- 2. Чтение и объединение ---
    PZ2 = pd.read_excel(new_file)
    required_cols = ['Название', 'Статус', 'Дата начала', 'Дата завершения',
                     'ФИО участника', 'Подразделение', 'Должность', 'Предприятие сотрудника']
    missing = [c for c in required_cols if c not in PZ2.columns]
    if missing:
        print(f"\nОШИБКА: В новом файле отсутствуют столбцы: {missing}")
        input("Нажмите Enter для выхода...")
        sys.exit(1)
    PZ2 = PZ2[required_cols]

    Final_prev = pd.read_excel(prev_file)

    Final = pd.concat([Final_prev, PZ2], sort=False, axis=0, ignore_index=True)

    # --- 3. Удаление дубликатов записей ---
    before = len(Final)
    Final = Final.drop_duplicates()
    after = len(Final)
    if before != after:
        print(f"\nУдалено дубликатов записей: {before - after}")

    # Сохраняем обновлённый итоговый файл
    Final.to_excel(prev_file, index=False)
    print(f"Итоговый файл обновлён: {prev_file}")

    # --- 4. Приведение дат ---
    for col in ['Дата начала', 'Дата завершения']:
        Final[col] = pd.to_datetime(Final[col], errors='coerce')

    # --- 5. Расчёт показателей ---
    stats_all = calc_stats(Final)

    slices = {}
    for year in [2023, 2024, 2025, 2026]:
        df_year = Final[Final['Дата завершения'].dt.year == year]
        slices[f"only_{year}"] = calc_stats(df_year)

    cumulative = {}
    for year in [2022, 2023, 2024, 2025]:
        df_cum = Final[Final['Дата завершения'].dt.year <= year]
        cumulative[f"to_{year}"] = calc_stats(df_cum)

    # --- 6. Неклассифицированные курсы ---
    unclassified = find_unclassified(Final)

    # --- 7. Вывод в консоль ---
    print("\n" + "=" * 60)
    # Ручная поправка +50
    stats_all["total_unique"] += 50
    print_stats("ИТОГО ПО ВСЕМУ ПЕРИОДУ", stats_all)

    for year in [2025, 2024, 2023, 2022]:
        print_stats(f"ВСЕГО НА КОНЕЦ {year} ГОДА", cumulative[f"to_{year}"])

    for year in [2026, 2025, 2024, 2023]:
        print_stats(f"ИТОГО ТОЛЬКО ЗА {year} ГОД", slices[f"only_{year}"])

    if unclassified:
        print(f"\n{'=' * 60}")
        print(f"НЕКЛАССИФИЦИРОВАННЫЕ КУРСЫ ({len(unclassified)} шт.):")
        for name in unclassified:
            print(f"  - {name}")
    else:
        print("\nВсе курсы классифицированы.")

    # --- 8. Сохранение в Excel ---
    report_path = os.path.join(os.path.dirname(prev_file), "Отчёт_статистика.xlsx")

    rows = []
    rows.append({"Период": "Весь период", **stats_all})
    for year in [2022, 2023, 2024, 2025]:
        rows.append({"Период": f"На конец {year}", **cumulative[f"to_{year}"]})
    for year in [2023, 2024, 2025, 2026]:
        rows.append({"Период": f"Только {year}", **slices[f"only_{year}"]})

    df_report = pd.DataFrame(rows)
    df_report.columns = ['Период', 'Всего уникальных (BP+IT)',
                         'Уникальных BP', 'Уникальных IT',
                         'Уникальных ПРМ', 'Человеко-курсов',
                         'Ч-к BP', 'Ч-к IT']

    df_unclass = pd.DataFrame(unclassified, columns=['Название курса'])

    with pd.ExcelWriter(report_path, engine='openpyxl') as writer:
        df_report.to_excel(writer, sheet_name='Статистика', index=False)
        df_unclass.to_excel(writer, sheet_name='Неклассифицированные', index=False)

    print(f"\nОтчёт сохранён: {report_path}")
    print("=" * 60)
    input("\nНажмите Enter для выхода...")


if __name__ == "__main__":
    main()
