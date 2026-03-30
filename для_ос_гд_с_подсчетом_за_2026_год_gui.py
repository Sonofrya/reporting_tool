# -*- coding: utf-8 -*-
"""
Анализ обучения ОС ГД с подсчётом по годам — GUI-версия (customtkinter).

Возможности:
  - Интерактивное управление неклассифицированными курсами
  - Назначение курсов в BP / IT / PRM / Блеклист
  - Сохранение назначений в course_assignments.json
  - Графики (matplotlib): столбчатая, круговая, линейный тренд
  - Опциональная перезапись итогового файла
"""

import json
import os
import sys
import threading
from tkinter import filedialog

import customtkinter as ctk
import pandas as pd
import matplotlib
matplotlib.use("TkAgg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

# ============================================================
# ПУТИ К ФАЙЛАМ
# ============================================================
if getattr(sys, 'frozen', False):
    _SCRIPT_DIR = os.path.dirname(sys.executable)
    _BUNDLE_DIR = sys._MEIPASS
else:
    _SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    _BUNDLE_DIR = _SCRIPT_DIR
COURSES_PATH = os.path.join(_BUNDLE_DIR, "courses.json")
ASSIGNMENTS_PATH = os.path.join(_SCRIPT_DIR, "course_assignments.json")

# ============================================================
# ЗАГРУЗКА СПИСКОВ КУРСОВ ИЗ JSON
# ============================================================

def load_courses():
    """Загружает списки курсов из courses.json."""
    with open(COURSES_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return set(data["BP"]), set(data["IT"]), set(data["PRM"])


BP_COURSES, IT_COURSES, PRM_COURSES = load_courses()
ALL_KNOWN_COURSES = BP_COURSES | IT_COURSES | PRM_COURSES

CATEGORY_OPTIONS = ["BP", "IT", "PRM", "Блеклист"]


# ============================================================
# РАБОТА С JSON-НАЗНАЧЕНИЯМИ
# ============================================================

def load_assignments():
    """Загружает пользовательские назначения из JSON."""
    if os.path.exists(ASSIGNMENTS_PATH):
        with open(ASSIGNMENTS_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return {
            "BP": set(data.get("BP", [])),
            "IT": set(data.get("IT", [])),
            "PRM": set(data.get("PRM", [])),
            "BLACKLIST": set(data.get("BLACKLIST", [])),
        }
    return {"BP": set(), "IT": set(), "PRM": set(), "BLACKLIST": set()}


def save_assignments(assignments):
    """Сохраняет пользовательские назначения в JSON."""
    data = {
        "BP": sorted(assignments.get("BP", set())),
        "IT": sorted(assignments.get("IT", set())),
        "PRM": sorted(assignments.get("PRM", set())),
        "BLACKLIST": sorted(assignments.get("BLACKLIST", set())),
    }
    with open(ASSIGNMENTS_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_effective_sets(assignments):
    """Возвращает расширенные множества курсов с учётом пользовательских назначений."""
    bp = BP_COURSES | assignments["BP"]
    it = IT_COURSES | assignments["IT"]
    prm = PRM_COURSES | assignments["PRM"]
    blacklist = assignments["BLACKLIST"]
    all_known = bp | it | prm | blacklist
    return bp, it, prm, blacklist, all_known


# ============================================================
# ФУНКЦИИ РАСЧЁТА
# ============================================================

def calc_stats(df, bp_set, it_set, prm_set):
    """Рассчитывает показатели по срезу данных."""
    BP = df[df['Название'].isin(bp_set)]
    IT = df[df['Название'].isin(it_set)]
    PRM = df[df['Название'].isin(prm_set)]

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


def find_unclassified(df, all_known):
    """Возвращает список названий курсов, не входящих ни в одну категорию."""
    all_courses_in_data = set(df['Название'].dropna().unique())
    return sorted(all_courses_in_data - all_known)


# ============================================================
# GUI-ПРИЛОЖЕНИЕ
# ============================================================

class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Анализ обучения ОС ГД")
        self.geometry("1050x800")
        self.minsize(850, 650)

        ctk.set_appearance_mode("system")
        ctk.set_default_color_theme("blue")

        # Данные
        self.new_file_path = None
        self.prev_file_path = None
        self.final_df = None
        self.report_data = None
        self.unclassified_list = []
        self.assignments = load_assignments()
        self.course_vars = {}
        self.course_row_widgets = []
        # Данные для графиков
        self.chart_data = None  # (stats_all, slices)
        self.chart_canvas = None

        self._build_ui()

    # --------------------------------------------------------
    # Построение интерфейса
    # --------------------------------------------------------
    def _build_ui(self):
        # --- Верхняя секция: выбор файлов ---
        file_frame = ctk.CTkFrame(self)
        file_frame.pack(fill="x", padx=15, pady=(15, 5))

        row1 = ctk.CTkFrame(file_frame, fg_color="transparent")
        row1.pack(fill="x", padx=10, pady=(10, 5))
        self.btn_new = ctk.CTkButton(row1, text="Выбрать новый файл", width=220,
                                      command=self._select_new_file)
        self.btn_new.pack(side="left")
        self.lbl_new = ctk.CTkLabel(row1, text="файл не выбран", anchor="w", text_color="gray")
        self.lbl_new.pack(side="left", padx=10, fill="x", expand=True)

        row2 = ctk.CTkFrame(file_frame, fg_color="transparent")
        row2.pack(fill="x", padx=10, pady=(0, 10))
        self.btn_prev = ctk.CTkButton(row2, text="Выбрать итоговый файл", width=220,
                                       command=self._select_prev_file)
        self.btn_prev.pack(side="left")
        self.lbl_prev = ctk.CTkLabel(row2, text="файл не выбран", anchor="w", text_color="gray")
        self.lbl_prev.pack(side="left", padx=10, fill="x", expand=True)

        # --- Кнопка запуска + чекбокс перезаписи ---
        run_frame = ctk.CTkFrame(self, fg_color="transparent")
        run_frame.pack(fill="x", padx=15, pady=(5, 5))

        self.btn_run = ctk.CTkButton(
            run_frame, text="Запустить анализ", height=40,
            font=ctk.CTkFont(size=15, weight="bold"),
            command=self._run_analysis, state="disabled",
        )
        self.btn_run.pack(side="left", padx=(0, 15))

        self.overwrite_var = ctk.BooleanVar(value=True)
        self.chk_overwrite = ctk.CTkCheckBox(
            run_frame, text="Перезаписать итоговый файл",
            variable=self.overwrite_var,
            font=ctk.CTkFont(size=13),
        )
        self.chk_overwrite.pack(side="left")

        # --- Прогресс-бар ---
        progress_frame = ctk.CTkFrame(self, fg_color="transparent")
        progress_frame.pack(fill="x", padx=15, pady=(0, 5))

        self.lbl_progress = ctk.CTkLabel(
            progress_frame, text="", anchor="w",
            font=ctk.CTkFont(size=12), text_color="gray",
        )
        self.lbl_progress.pack(fill="x")

        self.progress_bar = ctk.CTkProgressBar(progress_frame)
        self.progress_bar.pack(fill="x", pady=(2, 0))
        self.progress_bar.set(0)
        progress_frame.pack_forget()
        self.progress_frame = progress_frame

        # --- Вкладки ---
        self.tabview = ctk.CTkTabview(self)
        self.tabview.pack(fill="both", expand=True, padx=15, pady=(0, 5))

        self.tab_stats = self.tabview.add("Статистика")
        self.tab_unclass = self.tabview.add("Неклассифицированные")
        self.tab_assigned = self.tabview.add("Назначения")
        self.tab_charts = self.tabview.add("Графики")

        # -- Вкладка Статистика --
        self.txt_stats = ctk.CTkTextbox(self.tab_stats, font=ctk.CTkFont(family="Consolas", size=13))
        self.txt_stats.pack(fill="both", expand=True, padx=5, pady=(5, 0))

        # Включить копирование через Ctrl+C и контекстное меню
        self._enable_copy(self.txt_stats)

        stats_btn_frame = ctk.CTkFrame(self.tab_stats, fg_color="transparent")
        stats_btn_frame.pack(fill="x", padx=5, pady=5)
        ctk.CTkButton(
            stats_btn_frame, text="Копировать всё", width=150, height=28,
            font=ctk.CTkFont(size=12), fg_color="#555555", hover_color="#777777",
            command=self._copy_stats,
        ).pack(side="left")

        # -- Вкладка Неклассифицированные --
        self._build_unclass_tab()

        # -- Вкладка Назначения --
        self._build_assigned_tab()

        # -- Вкладка Графики --
        self._build_charts_tab()

        # --- Нижняя панель ---
        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.pack(fill="x", padx=15, pady=(0, 15))

        self.btn_save = ctk.CTkButton(bottom, text="Сохранить отчёт в Excel",
                                       state="disabled", command=self._save_report)
        self.btn_save.pack(side="left")

        self.lbl_status = ctk.CTkLabel(bottom, text="", anchor="w", text_color="gray")
        self.lbl_status.pack(side="left", padx=15, fill="x", expand=True)

    def _build_unclass_tab(self):
        """Строит интерфейс вкладки Неклассифицированные."""
        top = ctk.CTkFrame(self.tab_unclass, fg_color="transparent")
        top.pack(fill="x", padx=5, pady=5)

        ctk.CTkLabel(top, text="Поиск:").pack(side="left", padx=(0, 5))
        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", lambda *_: self._filter_unclassified())
        self.search_entry = ctk.CTkEntry(top, textvariable=self.search_var, width=300,
                                          placeholder_text="Введите часть названия курса...")
        self.search_entry.pack(side="left", fill="x", expand=True)

        self.lbl_unclass_count = ctk.CTkLabel(top, text="", text_color="gray")
        self.lbl_unclass_count.pack(side="right", padx=10)

        # Кнопки выделения
        sel_frame = ctk.CTkFrame(self.tab_unclass, fg_color="transparent")
        sel_frame.pack(fill="x", padx=5, pady=(0, 3))

        ctk.CTkButton(
            sel_frame, text="Выделить все", width=120, height=28,
            font=ctk.CTkFont(size=12), fg_color="#555555", hover_color="#777777",
            command=self._select_all_unclass,
        ).pack(side="left", padx=(0, 5))

        ctk.CTkButton(
            sel_frame, text="Снять все", width=120, height=28,
            font=ctk.CTkFont(size=12), fg_color="#555555", hover_color="#777777",
            command=self._deselect_all_unclass,
        ).pack(side="left")

        self.unclass_scroll = ctk.CTkScrollableFrame(self.tab_unclass)
        self.unclass_scroll.pack(fill="both", expand=True, padx=5, pady=(0, 5))

        # Панель массового назначения
        btn_frame = ctk.CTkFrame(self.tab_unclass, fg_color="transparent")
        btn_frame.pack(fill="x", padx=5, pady=5)

        ctk.CTkLabel(btn_frame, text="Назначить выбранные в:",
                     font=ctk.CTkFont(size=13)).pack(side="left", padx=(0, 5))

        self.unclass_target_var = ctk.StringVar(value="BP")
        self.unclass_target_menu = ctk.CTkOptionMenu(
            btn_frame, variable=self.unclass_target_var,
            values=CATEGORY_OPTIONS, width=120, height=30,
        )
        self.unclass_target_menu.pack(side="left", padx=(0, 10))

        self.btn_apply = ctk.CTkButton(
            btn_frame, text="Применить",
            fg_color="#2B7A0B", hover_color="#1E5A08",
            command=self._apply_assignments, state="disabled",
        )
        self.btn_apply.pack(side="left", padx=(0, 10))

        self.btn_recalc_unclass = ctk.CTkButton(
            btn_frame, text="Пересчитать",
            fg_color="#1F6AA5", hover_color="#164d78",
            command=self._recalculate_from_unclass,
        )
        self.btn_recalc_unclass.pack(side="left", padx=(0, 10))

        self.btn_reset = ctk.CTkButton(
            btn_frame, text="Сбросить все назначения",
            fg_color="#8B0000", hover_color="#5C0000",
            command=self._reset_assignments,
        )
        self.btn_reset.pack(side="left")

    def _build_assigned_tab(self):
        """Строит интерфейс вкладки Назначения."""
        self.assigned_scroll = ctk.CTkScrollableFrame(self.tab_assigned)
        self.assigned_scroll.pack(fill="both", expand=True, padx=5, pady=(5, 0))

        # Панель действий
        assigned_btn_frame = ctk.CTkFrame(self.tab_assigned, fg_color="transparent")
        assigned_btn_frame.pack(fill="x", padx=5, pady=5)

        ctk.CTkButton(
            assigned_btn_frame, text="Выделить все", width=120, height=28,
            font=ctk.CTkFont(size=12), fg_color="#555555", hover_color="#777777",
            command=self._select_all_assigned,
        ).pack(side="left", padx=(0, 5))

        ctk.CTkButton(
            assigned_btn_frame, text="Снять все", width=120, height=28,
            font=ctk.CTkFont(size=12), fg_color="#555555", hover_color="#777777",
            command=self._deselect_all_assigned,
        ).pack(side="left", padx=(0, 15))

        ctk.CTkLabel(assigned_btn_frame, text="Перенести в:",
                     font=ctk.CTkFont(size=13)).pack(side="left", padx=(0, 5))

        self.assigned_target_var = ctk.StringVar(value="BP")
        ctk.CTkOptionMenu(
            assigned_btn_frame, variable=self.assigned_target_var,
            values=CATEGORY_OPTIONS + ["Убрать"],
            width=120, height=30,
        ).pack(side="left", padx=(0, 10))

        ctk.CTkButton(
            assigned_btn_frame, text="Применить",
            fg_color="#2B7A0B", hover_color="#1E5A08",
            width=120, height=30,
            command=self._move_assigned,
        ).pack(side="left", padx=(0, 10))

        self.btn_recalc = ctk.CTkButton(
            assigned_btn_frame, text="Пересчитать",
            fg_color="#1F6AA5", hover_color="#164d78",
            width=120, height=30,
            command=self._recalculate_from_assigned,
        )
        self.btn_recalc.pack(side="left")

        self.assigned_check_vars = {}
        self._refresh_assigned_tab()

    def _build_charts_tab(self):
        """Строит интерфейс вкладки Графики (пустой до анализа)."""
        self.charts_placeholder = ctk.CTkLabel(
            self.tab_charts,
            text="Графики появятся после запуска анализа.",
            text_color="gray", font=ctk.CTkFont(size=13),
        )
        self.charts_placeholder.pack(pady=30)

    # --------------------------------------------------------
    # Вкладка Назначения — обновление
    # --------------------------------------------------------
    def _refresh_assigned_tab(self):
        for widget in self.assigned_scroll.winfo_children():
            widget.destroy()
        self.assigned_check_vars = {}

        categories = [("BP", "#1F6AA5"), ("IT", "#6A1FA5"),
                      ("PRM", "#A5861F"), ("Блеклист", "#8B0000")]
        key_map = {"BP": "BP", "IT": "IT", "PRM": "PRM", "Блеклист": "BLACKLIST"}

        any_assignments = False
        for cat_label, color in categories:
            key = key_map[cat_label]
            courses = sorted(self.assignments.get(key, set()))
            if not courses:
                continue
            any_assignments = True

            header = ctk.CTkLabel(
                self.assigned_scroll, text=f"  {cat_label} ({len(courses)} шт.)",
                font=ctk.CTkFont(size=14, weight="bold"), text_color=color, anchor="w",
            )
            header.pack(fill="x", pady=(10, 2))

            for course in courses:
                var = ctk.BooleanVar(value=False)
                self.assigned_check_vars[(course, key)] = var

                cb = ctk.CTkCheckBox(
                    self.assigned_scroll, text=course, variable=var,
                    font=ctk.CTkFont(size=12),
                )
                cb.pack(fill="x", padx=10, pady=1, anchor="w")

        if not any_assignments:
            ctk.CTkLabel(
                self.assigned_scroll,
                text="Пользовательских назначений пока нет.\n\n"
                     "Запустите анализ, затем назначьте курсы\n"
                     "на вкладке «Неклассифицированные».",
                text_color="gray", font=ctk.CTkFont(size=13),
            ).pack(pady=30)

    def _select_all_assigned(self):
        for var in self.assigned_check_vars.values():
            var.set(True)

    def _deselect_all_assigned(self):
        for var in self.assigned_check_vars.values():
            var.set(False)

    def _move_assigned(self):
        """Перенести выбранные курсы в другую категорию или убрать."""
        cat_map = {"BP": "BP", "IT": "IT", "PRM": "PRM", "Блеклист": "BLACKLIST"}
        target = self.assigned_target_var.get()
        moved = 0

        for (course, old_key), var in self.assigned_check_vars.items():
            if not var.get():
                continue
            # Убрать из старой категории
            self.assignments[old_key].discard(course)
            # Если не «Убрать» — добавить в новую
            if target != "Убрать":
                new_key = cat_map[target]
                if new_key != old_key:
                    self.assignments[new_key].add(course)
            moved += 1

        if moved == 0:
            self.lbl_status.configure(text="Не выбрано ни одного курса.")
            return

        save_assignments(self.assignments)
        self._refresh_assigned_tab()

        if target == "Убрать":
            self.lbl_status.configure(text=f"Убрано {moved} курсов из назначений.")
        else:
            self.lbl_status.configure(text=f"Перенесено {moved} курсов → {target}.")

    def _recalculate_from_assigned(self):
        """Пересчитать статистику (вызов из вкладки Назначения)."""
        if self.final_df is not None:
            self._recalculate()
        else:
            self.lbl_status.configure(text="Сначала запустите анализ.")

    # --------------------------------------------------------
    # Отображение неклассифицированных курсов
    # --------------------------------------------------------
    def _populate_unclassified(self):
        for widget in self.unclass_scroll.winfo_children():
            widget.destroy()
        self.course_vars.clear()
        self.course_row_widgets.clear()

        if not self.unclassified_list:
            ctk.CTkLabel(
                self.unclass_scroll, text="Все курсы классифицированы!",
                text_color="gray", font=ctk.CTkFont(size=13),
            ).pack(pady=30)
            self.lbl_unclass_count.configure(text="0 курсов")
            return

        self.lbl_unclass_count.configure(text=f"{len(self.unclassified_list)} курсов")

        for course in self.unclassified_list:
            var = ctk.BooleanVar(value=False)
            self.course_vars[course] = var

            row = ctk.CTkFrame(self.unclass_scroll, fg_color="transparent")
            row.pack(fill="x", padx=5, pady=2)

            cb = ctk.CTkCheckBox(
                row, text=course, variable=var,
                font=ctk.CTkFont(size=12),
            )
            cb.pack(side="left", fill="x", expand=True)

            self.course_row_widgets.append((course, row, cb))

    def _filter_unclassified(self):
        query = self.search_var.get().lower().strip()
        visible_count = 0
        for course, row, lbl in self.course_row_widgets:
            if query == "" or query in course.lower():
                row.pack(fill="x", padx=5, pady=2)
                visible_count += 1
            else:
                row.pack_forget()
        self.lbl_unclass_count.configure(
            text=f"{visible_count} / {len(self.course_row_widgets)} курсов")

    # --------------------------------------------------------
    # Выделение / снятие чекбоксов
    # --------------------------------------------------------
    def _select_all_unclass(self):
        """Выделить все видимые чекбоксы на вкладке Неклассифицированные."""
        query = self.search_var.get().lower().strip()
        for course, var in self.course_vars.items():
            if query == "" or query in course.lower():
                var.set(True)

    def _deselect_all_unclass(self):
        """Снять все чекбоксы на вкладке Неклассифицированные."""
        for var in self.course_vars.values():
            var.set(False)

    # --------------------------------------------------------
    # Применение назначений
    # --------------------------------------------------------
    def _apply_assignments(self):
        cat_map = {"BP": "BP", "IT": "IT", "PRM": "PRM", "Блеклист": "BLACKLIST"}
        target = self.unclass_target_var.get()
        key = cat_map[target]
        new_count = 0

        for course, var in self.course_vars.items():
            if var.get():
                self.assignments[key].add(course)
                new_count += 1

        if new_count == 0:
            self.lbl_status.configure(text="Не выбрано ни одного курса.")
            return

        save_assignments(self.assignments)
        self._refresh_assigned_tab()
        self.lbl_status.configure(text=f"Назначено {new_count} курсов → {target}. Нажмите «Пересчитать».")

    def _recalculate_from_unclass(self):
        """Пересчитать статистику (вызов из вкладки Неклассифицированные)."""
        if self.final_df is not None:
            self._recalculate()
        else:
            self.lbl_status.configure(text="Сначала запустите анализ.")

    def _reset_assignments(self):
        self.assignments = {"BP": set(), "IT": set(), "PRM": set(), "BLACKLIST": set()}
        save_assignments(self.assignments)
        self._refresh_assigned_tab()
        self.lbl_status.configure(text="Все назначения сброшены. Пересчёт...")

        if self.final_df is not None:
            self._recalculate()

    def _recalculate(self):
        bp, it, prm, blacklist, all_known = get_effective_sets(self.assignments)
        Final = self.final_df

        stats_all = calc_stats(Final, bp, it, prm)

        slices = {}
        for year in [2023, 2024, 2025, 2026]:
            df_year = Final[Final['Дата завершения'].dt.year == year]
            slices[f"only_{year}"] = calc_stats(df_year, bp, it, prm)

        cumulative = {}
        for year in [2022, 2023, 2024, 2025]:
            df_cum = Final[Final['Дата завершения'].dt.year <= year]
            cumulative[f"to_{year}"] = calc_stats(df_cum, bp, it, prm)

        stats_all["total_unique"] += 50

        unclassified = find_unclassified(Final, all_known)
        self.unclassified_list = unclassified

        lines = self._format_stats(stats_all, cumulative, slices)
        self.txt_stats.delete("1.0", "end")
        self.txt_stats.insert("1.0", "\n".join(lines))

        self.search_var.set("")
        self._populate_unclassified()

        self._update_report_data(stats_all, cumulative, slices, unclassified)

        # Обновить графики
        self.chart_data = (stats_all, slices)
        self._draw_charts()

        self.lbl_status.configure(text="Пересчёт завершён.")

    # --------------------------------------------------------
    # Копирование текста
    # --------------------------------------------------------
    def _enable_copy(self, textbox):
        """Включает Ctrl+C и контекстное меню (ПКМ) для копирования в CTkTextbox."""
        import tkinter as tk

        inner = textbox._textbox  # внутренний tk.Text виджет

        def copy_selection(event=None):
            try:
                sel = inner.get("sel.first", "sel.last")
                if sel:
                    self.clipboard_clear()
                    self.clipboard_append(sel)
            except tk.TclError:
                pass
            return "break"

        def select_all(event=None):
            inner.tag_add("sel", "1.0", "end-1c")
            return "break"

        def show_context_menu(event):
            menu = tk.Menu(inner, tearoff=0)
            menu.add_command(label="Копировать", command=copy_selection)
            menu.add_command(label="Выделить всё", command=select_all)
            menu.tk_popup(event.x_root, event.y_root)

        inner.bind("<Control-c>", copy_selection)
        inner.bind("<Control-C>", copy_selection)
        inner.bind("<Control-a>", select_all)
        inner.bind("<Control-A>", select_all)
        inner.bind("<Button-3>", show_context_menu)

    def _copy_stats(self):
        """Копирует текст статистики в буфер обмена."""
        text = self.txt_stats.get("1.0", "end").strip()
        if text:
            self.clipboard_clear()
            self.clipboard_append(text)
            self.lbl_status.configure(text="Текст скопирован в буфер обмена.")

    # --------------------------------------------------------
    # Выбор файлов
    # --------------------------------------------------------
    def _select_new_file(self):
        path = filedialog.askopenfilename(
            title="Выберите НОВЫЙ файл данных (xlsx)",
            filetypes=[("Excel файлы", "*.xlsx"), ("Все файлы", "*.*")],
        )
        if path:
            self.new_file_path = path
            self.lbl_new.configure(text=os.path.basename(path), text_color="white")
            self._check_ready()

    def _select_prev_file(self):
        path = filedialog.askopenfilename(
            title="Выберите ИТОГОВЫЙ (накопительный) файл — Fnl*.xlsx",
            filetypes=[("Excel файлы", "*.xlsx"), ("Все файлы", "*.*")],
        )
        if path:
            self.prev_file_path = path
            self.lbl_prev.configure(text=os.path.basename(path), text_color="white")
            self._check_ready()

    def _check_ready(self):
        if self.new_file_path and self.prev_file_path:
            self.btn_run.configure(state="normal")

    # --------------------------------------------------------
    # Прогресс-бар
    # --------------------------------------------------------
    def _set_progress(self, value, text=""):
        self.after(0, lambda: self._update_progress_ui(value, text))

    def _update_progress_ui(self, value, text):
        self.progress_bar.set(value)
        if text:
            self.lbl_progress.configure(text=text)

    # --------------------------------------------------------
    # Анализ
    # --------------------------------------------------------
    def _run_analysis(self):
        self.btn_run.configure(state="disabled", text="Обработка...")
        self.btn_save.configure(state="disabled")
        self.btn_apply.configure(state="disabled")
        self.txt_stats.delete("1.0", "end")

        self.progress_frame.pack(fill="x", padx=15, pady=(0, 5),
                                  before=self.tabview)
        self.progress_bar.set(0)
        self.lbl_progress.configure(text="Подготовка...")
        self.lbl_status.configure(text="")

        threading.Thread(target=self._analysis_worker, daemon=True).start()

    def _analysis_worker(self):
        try:
            result = self._do_analysis()
            self.after(0, lambda: self._on_analysis_done(result))
        except Exception as e:
            err_msg = str(e)
            self.after(0, lambda: self._on_analysis_error(err_msg))

    def _do_analysis(self):
        # Шаг 1: Чтение нового файла
        self._set_progress(0.05, "Чтение нового файла...")
        PZ2 = pd.read_excel(self.new_file_path)
        required_cols = [
            'Название', 'Статус', 'Дата начала', 'Дата завершения',
            'ФИО участника', 'Подразделение', 'Должность', 'Предприятие сотрудника',
        ]
        missing = [c for c in required_cols if c not in PZ2.columns]
        if missing:
            raise ValueError(f"В новом файле отсутствуют столбцы: {missing}")
        PZ2 = PZ2[required_cols]
        self._set_progress(0.20, "Новый файл загружен.")

        # Шаг 2: Чтение итогового файла
        self._set_progress(0.25, "Чтение итогового файла...")
        Final_prev = pd.read_excel(self.prev_file_path)
        self._set_progress(0.40, "Итоговый файл загружен.")

        # Шаг 3: Объединение и дедупликация
        self._set_progress(0.45, "Объединение данных и удаление дубликатов...")
        Final = pd.concat([Final_prev, PZ2], sort=False, axis=0, ignore_index=True)

        before = len(Final)
        Final = Final.drop_duplicates()
        after = len(Final)
        dup_msg = ""
        if before != after:
            dup_msg = f"Удалено дубликатов записей: {before - after}\n"
        self._set_progress(0.55, "Дубликаты удалены.")

        # Шаг 4: Сохранение итогового файла (если включён чекбокс)
        save_msg = ""
        if self.overwrite_var.get():
            self._set_progress(0.58, "Сохранение итогового файла...")
            Final.to_excel(self.prev_file_path, index=False)
            save_msg = f"Итоговый файл обновлён: {os.path.basename(self.prev_file_path)}"
            self._set_progress(0.70, "Итоговый файл сохранён.")
        else:
            save_msg = "Итоговый файл НЕ перезаписан (галочка снята)."
            self._set_progress(0.70, save_msg)

        # Шаг 5: Расчёт статистики
        self._set_progress(0.72, "Приведение дат и расчёт статистики...")
        for col in ['Дата начала', 'Дата завершения']:
            Final[col] = pd.to_datetime(Final[col], errors='coerce')

        bp, it, prm, blacklist, all_known = get_effective_sets(self.assignments)

        stats_all = calc_stats(Final, bp, it, prm)

        slices = {}
        for year in [2023, 2024, 2025, 2026]:
            df_year = Final[Final['Дата завершения'].dt.year == year]
            slices[f"only_{year}"] = calc_stats(df_year, bp, it, prm)

        cumulative = {}
        for year in [2022, 2023, 2024, 2025]:
            df_cum = Final[Final['Дата завершения'].dt.year <= year]
            cumulative[f"to_{year}"] = calc_stats(df_cum, bp, it, prm)

        stats_all["total_unique"] += 50
        self._set_progress(0.90, "Статистика рассчитана.")

        # Шаг 6: Поиск неклассифицированных
        self._set_progress(0.92, "Поиск неклассифицированных курсов...")
        unclassified = find_unclassified(Final, all_known)

        lines = []
        if dup_msg:
            lines.append(dup_msg)
        lines.append(save_msg)
        lines.append("")
        lines.extend(self._format_stats(stats_all, cumulative, slices))

        self._set_progress(1.0, "Готово!")
        return Final, "\n".join(lines), unclassified, stats_all, cumulative, slices

    def _format_stats(self, stats_all, cumulative, slices):
        lines = []

        def fmt(label, s):
            lines.append(f"{label}:")
            lines.append(f"  Всего уникальных (BP+IT): {s['total_unique']}")
            lines.append(f"  Уникальных BP:            {s['unique_BP']}")
            lines.append(f"  Уникальных IT:            {s['unique_IT']}")
            lines.append(f"  Уникальных ПРМ:           {s['unique_PRM']}")
            lines.append(f"  Человеко-курсов:          {s['person_courses']}")
            lines.append(f"    из них BP:              {s['person_courses_BP']}")
            lines.append(f"    из них IT:              {s['person_courses_IT']}")
            lines.append("")

        fmt("ИТОГО ПО ВСЕМУ ПЕРИОДУ", stats_all)
        for year in [2025, 2024, 2023, 2022]:
            fmt(f"ВСЕГО НА КОНЕЦ {year} ГОДА", cumulative[f"to_{year}"])
        for year in [2026, 2025, 2024, 2023]:
            fmt(f"ИТОГО ТОЛЬКО ЗА {year} ГОД", slices[f"only_{year}"])

        return lines

    def _update_report_data(self, stats_all, cumulative, slices, unclassified):
        rows = []
        rows.append({"Период": "Весь период", **stats_all})
        for year in [2022, 2023, 2024, 2025]:
            rows.append({"Период": f"На конец {year}", **cumulative[f"to_{year}"]})
        for year in [2023, 2024, 2025, 2026]:
            rows.append({"Период": f"Только {year}", **slices[f"only_{year}"]})

        df_report = pd.DataFrame(rows)
        df_report.columns = [
            'Период', 'Всего уникальных (BP+IT)',
            'Уникальных BP', 'Уникальных IT',
            'Уникальных ПРМ', 'Человеко-курсов',
            'Ч-к BP', 'Ч-к IT',
        ]
        df_unclass = pd.DataFrame(unclassified, columns=['Название курса'])
        self.report_data = (df_report, df_unclass)

    def _on_analysis_done(self, result):
        Final, stats_text, unclassified, stats_all, cumulative, slices = result
        self.final_df = Final
        self.unclassified_list = unclassified

        self._update_report_data(stats_all, cumulative, slices, unclassified)

        self.txt_stats.insert("1.0", stats_text)

        self.search_var.set("")
        self._populate_unclassified()
        self._refresh_assigned_tab()

        # Графики
        self.chart_data = (stats_all, slices)
        self._draw_charts()

        self.btn_run.configure(state="normal", text="Запустить анализ")
        self.btn_save.configure(state="normal")
        self.btn_apply.configure(state="normal")
        self.lbl_status.configure(text="Анализ завершён.")
        self.after(1500, self.progress_frame.pack_forget)

    def _on_analysis_error(self, err_msg):
        self.txt_stats.insert("1.0", f"ОШИБКА: {err_msg}")
        self.btn_run.configure(state="normal", text="Запустить анализ")
        self.lbl_status.configure(text="Ошибка при обработке.")
        self.lbl_progress.configure(text="Ошибка!")
        self.progress_bar.set(0)
        self.after(3000, self.progress_frame.pack_forget)

    # --------------------------------------------------------
    # Графики (matplotlib)
    # --------------------------------------------------------
    def _draw_charts(self):
        """Рисует графики на вкладке Графики."""
        if not self.chart_data:
            return

        stats_all, slices = self.chart_data

        # Удалить предыдущий canvas
        if self.chart_canvas:
            self.chart_canvas.get_tk_widget().destroy()
            self.chart_canvas = None

        # Убрать placeholder
        if self.charts_placeholder:
            self.charts_placeholder.destroy()
            self.charts_placeholder = None

        # Определяем цвет фона по теме
        is_dark = ctk.get_appearance_mode() == "Dark"
        bg_color = "#2B2B2B" if is_dark else "#EBEBEB"
        text_color = "white" if is_dark else "black"
        grid_color = "#444444" if is_dark else "#CCCCCC"

        fig = Figure(figsize=(10, 7), dpi=90, facecolor=bg_color)

        years = [2023, 2024, 2025, 2026]
        bp_vals = [slices[f"only_{y}"]["unique_BP"] for y in years]
        it_vals = [slices[f"only_{y}"]["unique_IT"] for y in years]
        pc_vals = [slices[f"only_{y}"]["person_courses"] for y in years]

        # --- 1. Столбчатая: BP vs IT по годам ---
        ax1 = fig.add_subplot(2, 2, 1)
        ax1.set_facecolor(bg_color)
        x = range(len(years))
        w = 0.35
        bars_bp = ax1.bar([i - w/2 for i in x], bp_vals, w, label="BP", color="#1F6AA5")
        bars_it = ax1.bar([i + w/2 for i in x], it_vals, w, label="IT", color="#6A1FA5")
        ax1.set_xticks(list(x))
        ax1.set_xticklabels([str(y) for y in years], color=text_color)
        ax1.set_title("Уникальные по годам", color=text_color, fontsize=12, fontweight="bold")
        ax1.legend(facecolor=bg_color, edgecolor=grid_color, labelcolor=text_color)
        ax1.tick_params(colors=text_color)
        ax1.yaxis.grid(True, color=grid_color, linestyle="--", alpha=0.5)
        # Подписи значений над столбцами
        for bar in bars_bp:
            ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.5,
                     str(int(bar.get_height())), ha="center", va="bottom",
                     color=text_color, fontsize=8)
        for bar in bars_it:
            ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.5,
                     str(int(bar.get_height())), ha="center", va="bottom",
                     color=text_color, fontsize=8)

        # --- 2. Круговая: BP vs IT за весь период ---
        ax2 = fig.add_subplot(2, 2, 2)
        ax2.set_facecolor(bg_color)
        bp_total = stats_all["unique_BP"]
        it_total = stats_all["unique_IT"]
        if bp_total + it_total > 0:
            sizes = [bp_total, it_total]
            labels = [f"BP\n{bp_total}", f"IT\n{it_total}"]
            colors = ["#1F6AA5", "#6A1FA5"]
            wedges, texts, autotexts = ax2.pie(
                sizes, labels=labels, colors=colors, autopct="%1.0f%%",
                startangle=90, textprops={"color": text_color, "fontsize": 10},
            )
            for at in autotexts:
                at.set_color("white")
                at.set_fontweight("bold")
        ax2.set_title("BP vs IT (весь период)", color=text_color, fontsize=12, fontweight="bold")

        # --- 3. Линейный тренд: человеко-курсы ---
        ax3 = fig.add_subplot(2, 1, 2)
        ax3.set_facecolor(bg_color)
        ax3.plot(years, pc_vals, marker="o", linewidth=2, color="#2B7A0B",
                 markersize=8, markerfacecolor="#4CAF50")
        for i, v in enumerate(pc_vals):
            ax3.annotate(str(v), (years[i], v), textcoords="offset points",
                         xytext=(0, 12), ha="center", color=text_color, fontsize=10)
        ax3.set_xticks(years)
        ax3.set_xticklabels([str(y) for y in years], color=text_color)
        ax3.set_title("Человеко-курсы по годам", color=text_color, fontsize=12, fontweight="bold")
        ax3.tick_params(colors=text_color)
        ax3.yaxis.grid(True, color=grid_color, linestyle="--", alpha=0.5)

        fig.tight_layout(pad=2.0)

        # Встраиваем в tkinter
        self.chart_canvas = FigureCanvasTkAgg(fig, master=self.tab_charts)
        self.chart_canvas.draw()
        self.chart_canvas.get_tk_widget().pack(fill="both", expand=True, padx=5, pady=5)

    # --------------------------------------------------------
    # Сохранение отчёта
    # --------------------------------------------------------
    def _save_report(self):
        if not self.report_data:
            return

        df_report, df_unclass = self.report_data

        save_path = filedialog.asksaveasfilename(
            title="Сохранить отчёт",
            defaultextension=".xlsx",
            initialfile="Отчёт_статистика.xlsx",
            filetypes=[("Excel файлы", "*.xlsx")],
        )
        if not save_path:
            return

        with pd.ExcelWriter(save_path, engine='openpyxl') as writer:
            df_report.to_excel(writer, sheet_name='Статистика', index=False)
            df_unclass.to_excel(writer, sheet_name='Неклассифицированные', index=False)

        self.lbl_status.configure(text=f"Отчёт сохранён: {os.path.basename(save_path)}")


# ============================================================
# ЗАПУСК
# ============================================================

if __name__ == "__main__":
    app = App()
    app.mainloop()
