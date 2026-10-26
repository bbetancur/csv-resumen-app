# -*- coding: utf-8 -*-
"""Resumen CSV Outdoor / Indoor con Kivy (Explorador de Archivos y Permisos Android 11+)."""
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
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout

# Configuración avanzada de permisos para Android 11+ (Scoped Storage)
if platform == 'android':
    from android.permissions import request_permissions, Permission
    try:
        request_permissions([
            Permission.READ_EXTERNAL_STORAGE, 
            Permission.WRITE_EXTERNAL_STORAGE,
            "android.permission.MANAGE_EXTERNAL_STORAGE"
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

def obtener_archivos_csv(target_path):
    """Obtiene lista de archivos .csv si target_path es carpeta o lista de archivos si se seleccionó individualmente."""
    csv_list = []
    if not target_path or not os.path.exists(target_path):
        return csv_list
    
    if os.path.isfile(target_path):
        if target_path.lower().endswith('.csv'):
            folder = os.path.dirname(target_path)
            return obtener_archivos_csv(folder)
        return []

    for root, dirs, files in os.walk(target_path):
        for f in files:
            if f.lower().endswith('.csv'):
                csv_list.append(os.path.join(root, f))
    return sorted(csv_list, key=lambda p: os.path.basename(p).lower())

def process_outdoor(folder):
    files = obtener_archivos_csv(folder)
    if not files:
        raise ValueError('No se encontraron archivos CSV en la ubicación.')
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

def process_indoor(folder, mode):
    files = obtener_archivos_csv(folder)
    matches = []
    for path in files:
        # Expresión regular mejorada para detectar patrones .1.csv, _1.csv, .1.CSV, etc.
        m = re.search(r'[\._]([1-5])\.csv$', os.path.basename(path), flags=re.I)
        if m:
            matches.append((int(m.group(1)), path))
    if not matches:
        raise ValueError('No se encontraron archivos terminados en .1.csv al .5.csv.')

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


class FolderChooserPopup(Popup):
    def __init__(self, current_path, callback, **kwargs):
        super().__init__(**kwargs)
        self.title = "Seleccionar Carpeta o Archivo"
        self.size_hint = (0.95, 0.95)
        self.current_path = current_path if os.path.exists(current_path) else '/storage/emulated/0/'
        if os.path.isfile(self.current_path):
            self.current_path = os.path.dirname(self.current_path)
        self.callback = callback

        layout = BoxLayout(orientation='vertical', spacing=10, padding=10)
        
        self.path_label = Label(text=self.current_path, font_size=24, size_hint_y=None, height=70)
        layout.add_widget(self.path_label)

        self.scroll = ScrollView()
        self.grid = GridLayout(cols=1, spacing=5, size_hint_y=None)
        self.grid.bind(minimum_height=self.grid.setter('height'))
        self.scroll.add_widget(self.grid)
        layout.add_widget(self.scroll)

        btn_layout = BoxLayout(size_hint_y=None, height=80, spacing=10)
        select_btn = Button(text="Elegir Esta Carpeta", font_size=28, background_color=(0.1, 0.7, 0.3, 1))
        select_btn.bind(on_press=self.select_current)
        btn_layout.add_widget(select_btn)

        cancel_btn = Button(text="Cancelar", font_size=28, background_color=(0.8, 0.2, 0.2, 1))
        cancel_btn.bind(on_press=lambda x: self.dismiss())
        btn_layout.add_widget(cancel_btn)
        
        layout.add_widget(btn_layout)
        self.add_widget(layout)
        self.load_directories()

    def load_directories(self):
        self.grid.clear_widgets()
        parent_dir = os.path.dirname(self.current_path)
        if parent_dir and parent_dir != self.current_path:
            btn_up = Button(text=".. [Subir de carpeta]", font_size=24, size_hint_y=None, height=65, background_color=(0.3, 0.3, 0.3, 1))
            btn_up.bind(on_press=lambda x: self.change_dir(parent_dir))
            self.grid.add_widget(btn_up)

        try:
            items = sorted(os.listdir(self.current_path))
            for item in items:
                full_path = os.path.join(self.current_path, item)
                if os.path.isdir(full_path):
                    btn = Button(text=f"[Carpeta] > {item}", font_size=24, size_hint_y=None, height=65, background_color=(0.2, 0.4, 0.6, 1))
                    btn.bind(on_press=lambda x, p=full_path: self.change_dir(p))
                    self.grid.add_widget(btn)
                elif item.lower().endswith('.csv'):
                    btn = Button(text=f"[Archivo CSV] {item}", font_size=24, size_hint_y=None, height=65, background_color=(0.1, 0.6, 0.4, 1))
                    btn.bind(on_press=lambda x, p=self.current_path: self.select_specific(p))
                    self.grid.add_widget(btn)
        except Exception as e:
            err_btn = Button(text=f"Error al leer carpeta: {e}", font_size=20, size_hint_y=None, height=65)
            self.grid.add_widget(err_btn)

    def change_dir(self, path):
        if os.path.exists(path):
            self.current_path = path
            self.path_label.text = path
            self.load_directories()

    def select_current(self, instance):
        self.callback(self.current_path)
        self.dismiss()

    def select_specific(self, path):
        self.callback(path)
        self.dismiss()


class ResumenAppUI(FloatLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.selected_folder = DEFAULT_FOLDER

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

        # 3. Botón para seleccionar carpeta (font_size = 36)
        self.folder_btn = Button(
            text='Seleccionar Carpeta con CSVs', 
            size_hint_y=None, 
            height=80, 
            background_color=(0.15, 0.5, 0.75, 1),
            font_size=36,
            bold=True
        )
        self.folder_btn.bind(on_press=self.abrir_explorador)
        main_layout.add_widget(self.folder_btn)

        # 4. Etiqueta de ruta (font_size = 36)
        self.path_label = Label(
            text=f'Carpeta:\n{self.selected_folder}', 
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
            text='Listo. Selecciona tu carpeta con archivos .csv y presiona procesar.', 
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

    def abrir_explorador(self, instance):
        popup = FolderChooserPopup(self.selected_folder, self.on_folder_chosen)
        popup.open()

    def on_folder_chosen(self, folder_path):
        self.selected_folder = folder_path
        self.path_label.text = f'Carpeta:\n{self.selected_folder}'
        self.status_label.text = 'Ubicación seleccionada correctamente.'

    def ejecutar_proceso(self, instance):
        folder = self.selected_folder
        mode_val = self.mode_spinner.text
        
        if not folder or not os.path.exists(folder):
            self.status_label.text = 'Error: La ubicación seleccionada no es válida.'
            return

        target_dir = folder if os.path.isdir(folder) else os.path.dirname(folder)

        try:
            if mode_val == 'Outdoor':
                headers, data = process_outdoor(target_dir)
            else:
                mode_tipo = 'Indoor Normal' if mode_val == 'Indoor Normal' else 'Indoor Forzado'
                headers, data = process_indoor(target_dir, mode_tipo)

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

            self.status_label.text = f'¡Éxito! Archivos guardados en:\n{target_dir}'
        except Exception as e:
            self.status_label.text = f'Aviso: {str(e)}'


class ResumenApp(App):
    def build(self):
        return ResumenAppUI()


if __name__ == '__main__':
    ResumenApp().run()
