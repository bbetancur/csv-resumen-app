# -*- coding: utf-8 -*-
"""Resumen CSV Outdoor / Indoor con Kivy (Selector directo de archivos CSV via Plyer)."""
import csv
import os
import re
import math
import statistics
from collections import defaultdict
from kivy.app import App
from kivy.utils import platform
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.spinner import Spinner
from plyer import filechooser

# Configuración de rutas en Android
if platform == 'android':
    from android.permissions import request_permissions, Permission
    try:
        request_permissions([
            Permission.READ_EXTERNAL_STORAGE, 
            Permission.WRITE_EXTERNAL_STORAGE
        ])
    except Exception:
        pass
    from jnius import autoclass
    Environment = autoclass('android.os.Environment')
    DEFAULT_FOLDER = Environment.getExternalStoragePublicDirectory(Environment.DIRECTORY_DOWNLOADS).getAbsolutePath()
else:
    DEFAULT_FOLDER = os.getcwd()

OUTDOOR_ROWS = [
    'Application throughput downlink measurement average',
    'Application throughput uplink measurement average',
    'VoIMS call disconnects (dropped)',
    'Voice call disconnects (dropped)',
]
INDOOR_ROWS = [
    'App Tput DL avg',
    'App Tput UL avg',
    'App Tput DL avg',
    'Voice call dropped',
    'Voice call dropped',
]

def norm(s):
    return (s or '').strip().casefold()

def parse_number(value):
    s = (value or '').strip().replace('\u00a0', '').replace(' ', '')
    if not s or s.casefold() in {'nc', 'n/a', 'na', '-', 'null'}:
        return None
    if ',' in s and '.' in s:
        if s.rfind(',') > s.rfind('.'):
            s = s.replace('.', '').replace(',', '.')
        else:
            s = s.replace(',', '')
    elif ',' in s:
        s = s.replace(',', '.')
    try:
        n = float(s)
        return n if math.isfinite(n) else None
    except ValueError:
        return None

def fmt(value):
    if value is None:
        return '-'
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return ('%.6f' % value).rstrip('0').rstrip('.').replace('.', ',')

def read_csv(path):
    for enc in ('utf-8-sig', 'latin-1'):
        try:
            with open(path, 'r', encoding=enc, newline='') as f:
                return list(csv.reader(f, delimiter=';'))
        except UnicodeDecodeError:
            continue
    return []

def row_value(rows, name, value_col=1):
    target = norm(name)
    for row in rows:
        if len(row) > value_col and norm(row[0]) == target:
            return parse_number(row[value_col])
    return None

def device_label(rows, fallback):
    for row in rows:
        if len(row) > 1 and norm(row[0]) == 'device label' and row[1].strip():
            return row[1].strip()
    return fallback

def process_outdoor(files):
    if not files:
        raise ValueError('No se han seleccionado archivos CSV.')
    headers = None
    avg_values = {name: defaultdict(list) for name in OUTDOOR_ROWS[:2]}
    sum_values = {name: defaultdict(float) for name in OUTDOOR_ROWS[2:]}
    sum_seen = {name: defaultdict(bool) for name in OUTDOOR_ROWS[2:]}
    for path in files:
        rows = read_csv(path)
        if not rows:
            continue
        if headers is None:
            header_row = rows[0] if rows else []
            headers = []
            for physical_col in range(2, 7):
                idx = physical_col - 1
                if len(header_row) > idx and header_row[idx].strip():
                    headers.append(header_row[idx].strip())
                else:
                    headers.append(f'Columna {physical_col}')
        for row in rows:
            if not row:
                continue
            name = row[0].strip()
            matched_avg = next((k for k in avg_values if norm(k) == norm(name)), None)
            matched_sum = next((k for k in sum_values if norm(k) == norm(name)), None)
            if matched_avg is not None:
                for j, col_index in enumerate(range(1, 4)):
                    val = parse_number(row[col_index]) if len(row) > col_index else None
                    if val is not None:
                        avg_values[matched_avg][j].append(val)
            elif matched_sum is not None:
                for j, col_index in enumerate(range(4, 6), start=3):
                    val = parse_number(row[col_index]) if len(row) > col_index else None
                    if val is not None:
                        sum_values[matched_sum][j] += val
                        sum_seen[matched_sum][j] = True
    if headers is None:
        raise ValueError('No se pudieron leer datos de los CSV.')
    result = []
    for name in OUTDOOR_ROWS:
        vals = []
        for j in range(5):
            if name in avg_values:
                nums = avg_values[name].get(j, [])
                vals.append(statistics.fmean(nums) if nums else None)
            else:
                if j < 3:
                    vals.append(None)
                else:
                    vals.append(sum_values[name].get(j, 0.0) if sum_seen[name].get(j, False) else 0.0)
        result.append([name] + vals)
    return ['KPI'] + headers, result

def process_indoor(files, mode):
    matches = []
    for path in files:
        m = re.search(r'[\._]([1-5])\.csv$', os.path.basename(path), flags=re.I)
        if m:
            matches.append((int(m.group(1)), path))
    if not matches:
        raise ValueError('No se seleccionaron archivos terminados en .1.csv al .5.csv.')

    labels_by_suffix = defaultdict(set)
    values_by_group = defaultdict(list)
    for suffix, path in matches:
        rows = read_csv(path)
        label = device_label(rows, f'Device {suffix}')
        labels_by_suffix[suffix].add(label)
        if mode == 'Indoor Normal':
            kpi = {1: 'App Tput DL avg', 2: 'App Tput UL avg', 3: 'App Tput DL avg', 4: 'Voice call dropped', 5: 'Voice call dropped'}[suffix]
        else:
            kpi = {1: 'App Tput DL avg', 2: 'App Tput DL avg', 3: 'App Tput DL avg', 4: 'Voice call dropped', 5: 'Voice call dropped'}[suffix]
        val = row_value(rows, kpi, 1)
        values_by_group[(suffix, label)].append(val)

    columns = []
    for suffix in range(1, 6):
        for label in sorted(labels_by_suffix.get(suffix, set()), key=str.casefold):
            columns.append((suffix, label))
    if not columns:
        raise ValueError('No se encontraron archivos Indoor válidos.')

    row_names = INDOOR_ROWS if mode == 'Indoor Normal' else [
        'App Tput DL avg', 'App Tput DL avg', 'App Tput DL avg',
        'Voice call dropped', 'Voice call dropped'
    ]
    rows_out = []
    for row_i, kpi_name in enumerate(row_names):
        out = [kpi_name]
        suffix = row_i + 1
        for col_suffix, label in columns:
            if col_suffix != suffix:
                out.append(None)
                continue
            vals = [v for v in values_by_group.get((suffix, label), []) if v is not None]
            if not vals:
                out.append(None)
            elif suffix <= 3:
                out.append(statistics.fmean(vals))
            else:
                out.append(sum(vals))
        rows_out.append(out)
    return ['KPI'] + [label for _, label in columns], rows_out


class ResumenAppUI(FloatLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.selected_files = []

        main_layout = BoxLayout(
            orientation='vertical',
            padding=25,
            spacing=15,
            size_hint=(0.95, 0.9),
            pos_hint={'center_x': 0.5, 'center_y': 0.5}
        )

        # 1. Título principal (font_size = 36)
        self.title_label = Label(
            text='Resumen CSV Outdoor / Indoor', 
            font_size=36, 
            size_hint_y=None, 
            height=80, 
            bold=True,
            halign='center',
            valign='middle'
        )
        self.title_label.bind(size=lambda s, w: setattr(s, 'text_size', w))
        main_layout.add_widget(self.title_label)

        # 2. Selector de Modo (font_size = 36)
        self.mode_spinner = Spinner(
            text='Outdoor', 
            values=('Outdoor', 'Indoor Normal', 'Indoor Forzado'), 
            size_hint_y=None, 
            height=80,
            font_size=36
        )
        main_layout.add_widget(self.mode_spinner)

        # 3. Botón para seleccionar archivos directamente (font_size = 36)
        self.folder_btn = Button(
            text='Seleccionar Archivos CSV', 
            size_hint_y=None, 
            height=80, 
            background_color=(0.15, 0.5, 0.75, 1),
            font_size=36,
            bold=True
        )
        self.folder_btn.bind(on_press=self.seleccionar_archivos)
        main_layout.add_widget(self.folder_btn)

        # 4. Etiqueta de archivos seleccionados (font_size = 36)
        self.path_label = Label(
            text='Ningún archivo seleccionado', 
            font_size=36, 
            size_hint_y=None, 
            height=130, 
            halign='center', 
            valign='middle',
            bold=True
        )
        self.path_label.bind(size=lambda s, w: setattr(s, 'text_size', w))
        main_layout.add_widget(self.path_label)

        # 5. Botón Procesar (font_size = 36)
        self.process_btn = Button(
            text='Procesar y Guardar Resultados', 
            size_hint_y=None, 
            height=90, 
            background_color=(0.1, 0.7, 0.3, 1),
            font_size=36,
            bold=True
        )
        self.process_btn.bind(on_press=self.ejecutar_proceso)
        main_layout.add_widget(self.process_btn)

        # 6. Estado (font_size = 36)
        self.status_label = Label(
            text='Listo. Selecciona tus archivos .csv y presiona procesar.', 
            font_size=36, 
            halign='center', 
            valign='middle'
        )
        self.status_label.bind(size=lambda s, w: setattr(s, 'text_size', w))
        main_layout.add_widget(self.status_label)

        self.add_widget(main_layout)

        # 7. Créditos en la esquina inferior derecha (font_size = 28)
        self.credits_label = Label(
            text='creado por Benjamín Betancur\nbenjamin.betancur@gmail.com',
            font_size=28,
            size_hint=(None, None),
            size=(550, 90),
            pos_hint={'right': 0.98, 'bottom': 0.02},
            halign='right',
            valign='bottom',
            color=(0.7, 0.7, 0.7, 1)
        )
        self.credits_label.bind(size=lambda s, w: setattr(s, 'text_size', w))
        self.add_widget(self.credits_label)

    def seleccionar_archivos(self, instance):
        try:
            filechooser.open_file(
                title="Seleccionar archivos CSV",
                multiple=True,
                filters=[("CSV Files", "*.csv", "*.CSV")],
                on_selection=self.on_files_selected
            )
        except Exception as e:
            self.status_label.text = f'Error al abrir selector: {e}'

    def on_files_selected(self, selection):
        if selection:
            self.selected_files = selection
            nombres = [os.path.basename(f) for f in selection]
            if len(nombres) <= 2:
                texto = "Archivos:\n" + ", ".join(nombres)
            else:
                texto = f"Archivos seleccionados: {len(nombres)} archivos"
            self.path_label.text = texto
            self.status_label.text = 'Archivos seleccionados correctamente.'

    def ejecutar_proceso(self, instance):
        files = self.selected_files
        mode_val = self.mode_spinner.text
        
        if not files:
            self.status_label.text = 'Error: No hay archivos .csv seleccionados.'
            return

        target_dir = os.path.dirname(files[0]) if files else DEFAULT_FOLDER

        try:
            if mode_val == 'Outdoor':
                headers, data = process_outdoor(files)
            else:
                mode_tipo = 'Indoor Normal' if mode_val == 'Indoor Normal' else 'Indoor Forzado'
                headers, data = process_indoor(files, mode_tipo)

            # Guardar TXT
            out_txt = os.path.join(target_dir, 'RESUMEN_CSV.txt')
            with open(out_txt, 'w', encoding='utf-8-sig', newline='') as f:
                lines = ['\t'.join(str(x) for x in headers)]
                for row in data:
                    lines.append('\t'.join(str(v) if v is not None else '-' for v in row))
                f.write('\n'.join(lines).replace('\t', ';') + '\n')

            # Guardar Excel
            out_xlsx = os.path.join(target_dir, 'RESUMEN_CSV.xlsx')
            from openpyxl import Workbook
            wb = Workbook()
            ws = wb.active
            ws.title = 'Resumen'
            ws.append(headers)
            for row in data:
                ws.append([v if v is not None else '' for v in row])
            wb.save(out_xlsx)

            self.status_label.text = f'¡Éxito! Resultados guardados en:\n{target_dir}'
        except Exception as e:
            self.status_label.text = f'Aviso: {str(e)}'


class ResumenApp(App):
    def build(self):
        return ResumenAppUI()


if __name__ == '__main__':
    ResumenApp().run()
