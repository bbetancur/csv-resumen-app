# -*- coding: utf-8 -*-
"""Resumen CSV Outdoor / Indoor. Requiere Python 3.10+; openpyxl para exportar Excel."""
import csv
import os
import re
import math
import statistics
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from collections import defaultdict

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
    """Convierte números con decimal punto o coma; ignora NC y celdas vacías."""
    s = (value or '').strip().replace('\u00a0', '').replace(' ', '')
    if not s or s.casefold() in {'nc', 'n/a', 'na', '-', 'null'}:
        return None
    # Si hay coma y punto, el último separador se interpreta como decimal.
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
    # utf-8-sig cubre archivos con BOM; latin-1 permite abrir exportaciones antiguas.
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


def csv_files(folder):
    return sorted((os.path.join(folder, f) for f in os.listdir(folder)
                   if f.lower().endswith('.csv')), key=lambda p: os.path.basename(p).lower())


def process_outdoor(folder):
    files = csv_files(folder)
    if not files:
        raise ValueError('La carpeta no contiene archivos CSV.')
    # Columnas físicas 2 a 6: se excluye la primera columna de parámetros.
    headers = None
    avg_values = {name: defaultdict(list) for name in OUTDOOR_ROWS[:2]}
    sum_values = {name: defaultdict(float) for name in OUTDOOR_ROWS[2:]}
    sum_seen = {name: defaultdict(bool) for name in OUTDOOR_ROWS[2:]}
    for path in files:
        rows = read_csv(path)
        if not rows:
            continue
        if headers is None:
            # Outdoor: conservar literalmente los encabezados originales del CSV.
            # La primera fila contiene 'Parameter' en la columna 1 y los nombres
            # originales de las columnas físicas 2, 3, 4, 5 y 6 a continuación.
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
            # Comparación sin distinguir mayúsculas/minúsculas ni espacios externos.
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
                # Las filas de desconexiones se suman únicamente en columnas físicas 5 y 6.
                if j < 3:
                    vals.append(None)
                else:
                    vals.append(sum_values[name].get(j, 0.0) if sum_seen[name].get(j, False) else 0.0)
        result.append([name] + vals)
    return ['KPI'] + headers, result


def process_indoor(folder, mode):
    files = csv_files(folder)
    matches = []
    for path in files:
        m = re.search(r'\.([1-5])\.csv$', os.path.basename(path), flags=re.I)
        if m:
            matches.append((int(m.group(1)), path))
    if not matches:
        raise ValueError('No se encontraron archivos terminados en .1.csv, .2.csv, .3.csv, .4.csv o .5.csv.')

    # Cada sufijo genera una columna por Device Label. Si hay varios archivos
    # del mismo sufijo/etiqueta, se agregan sus valores según la regla indicada.
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


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('Resumen CSV - Outdoor / Indoor')
        self.geometry('900x510')
        self.minsize(680, 390)
        self.folder = ''
        self.headers = []
        self.data = []
        self.mode = tk.StringVar(value='Outdoor')
        self.indoor_mode = tk.StringVar(value='Indoor Normal')
        self._build_ui()

    def _build_ui(self):
        top = ttk.Frame(self, padding=10)
        top.pack(fill='x')
        ttk.Label(top, text='Tipo de análisis:').pack(side='left')
        ttk.Radiobutton(top, text='Outdoor', variable=self.mode, value='Outdoor', command=self._mode_changed).pack(side='left', padx=(8, 4))
        ttk.Radiobutton(top, text='Indoor', variable=self.mode, value='Indoor', command=self._mode_changed).pack(side='left', padx=4)
        self.indoor_frame = ttk.Frame(top)
        self.indoor_frame.pack(side='left', padx=12)
        ttk.Radiobutton(self.indoor_frame, text='Indoor Normal', variable=self.indoor_mode, value='Indoor Normal').pack(side='left')
        ttk.Radiobutton(self.indoor_frame, text='Indoor Forzado', variable=self.indoor_mode, value='Indoor Forzado').pack(side='left', padx=(8, 0))
        ttk.Button(top, text='Seleccionar carpeta…', command=self.choose_folder).pack(side='right')
        self.folder_label = ttk.Label(self, text='Carpeta: no seleccionada', padding=(10, 0, 10, 8))
        self.folder_label.pack(fill='x')
        actions = ttk.Frame(self, padding=(10, 0, 10, 8))
        actions.pack(fill='x')
        ttk.Button(actions, text='Procesar', command=self.run).pack(side='left')
        ttk.Button(actions, text='Copiar tabla', command=self.copy_table).pack(side='left', padx=6)
        ttk.Button(actions, text='Exportar Excel', command=self.export_excel).pack(side='left')
        ttk.Button(actions, text='Guardar TXT', command=self.save_txt).pack(side='left', padx=6)
        ttk.Button(actions, text='Información', command=lambda: messagebox.showinfo('Información', 'Creado por Benjamín Betancur')).pack(side='right')
        table_frame = ttk.Frame(self, padding=(10, 0, 10, 10))
        table_frame.pack(fill='both', expand=True)
        self.tree = ttk.Treeview(table_frame, show='headings')
        yscroll = ttk.Scrollbar(table_frame, orient='vertical', command=self.tree.yview)
        xscroll = ttk.Scrollbar(table_frame, orient='horizontal', command=self.tree.xview)
        self.tree.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        self.tree.grid(row=0, column=0, sticky='nsew')
        yscroll.grid(row=0, column=1, sticky='ns')
        xscroll.grid(row=1, column=0, sticky='ew')
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)
        self.status = ttk.Label(self, text='Selecciona una carpeta y presiona Procesar.', padding=(10, 0, 10, 8))
        self.status.pack(fill='x')
        self._mode_changed()

    def _mode_changed(self):
        state = 'normal' if self.mode.get() == 'Indoor' else 'disabled'
        for child in self.indoor_frame.winfo_children():
            child.configure(state=state)

    def choose_folder(self):
        folder = filedialog.askdirectory(title='Seleccionar carpeta con archivos CSV')
        if folder:
            self.folder = folder
            self.folder_label.configure(text='Carpeta: ' + folder)

    def run(self):
        if not self.folder:
            messagebox.showwarning('Falta carpeta', 'Primero selecciona una carpeta con archivos CSV.')
            return
        try:
            if self.mode.get() == 'Outdoor':
                self.headers, self.data = process_outdoor(self.folder)
            else:
                self.headers, self.data = process_indoor(self.folder, self.indoor_mode.get())
            self._show_table()
            self.status.configure(text=f'Resumen generado: {len(self.data)} filas de KPI.')
            self._write_txt(os.path.join(self.folder, 'RESUMEN_CSV.txt'))
        except Exception as exc:
            messagebox.showerror('Error al procesar', str(exc))

    def _format_value(self, value, row_name=None):
        # En Outdoor, mostrar los dos KPI de throughput con exactamente 2 decimales.
        if (self.mode.get() == 'Outdoor' and row_name in OUTDOOR_ROWS[:2]
                and isinstance(value, (int, float)) and value is not None):
            return f'{value:.2f}'.replace('.', ',')
        return fmt(value) if isinstance(value, (int, float)) or value is None else str(value)

    def _show_table(self):
        self.tree.delete(*self.tree.get_children())
        cols = [f'c{i}' for i in range(len(self.headers))]
        self.tree['columns'] = cols
        for i, (col, heading) in enumerate(zip(cols, self.headers)):
            self.tree.heading(col, text=heading)
            self.tree.column(col, width=260 if i == 0 else 150, minwidth=100, stretch=True, anchor='w' if i == 0 else 'center')
        for row in self.data:
            row_name = row[0] if row else None
            self.tree.insert('', 'end', values=[self._format_value(v, row_name) for v in row])

    def _tsv(self):
        lines = ['\t'.join(str(x) for x in self.headers)]
        for row in self.data:
            row_name = row[0] if row else None
            lines.append('\t'.join(self._format_value(v, row_name) for v in row))
        return '\n'.join(lines)

    def copy_table(self):
        if not self.data:
            messagebox.showinfo('Sin datos', 'Primero procesa una carpeta.')
            return
        self.clipboard_clear()
        self.clipboard_append(self._tsv())
        self.update()
        self.status.configure(text='Tabla copiada. Puedes pegarla en Excel.')

    def _write_txt(self, path):
        with open(path, 'w', encoding='utf-8-sig', newline='') as f:
            f.write(self._tsv().replace('\t', ';') + '\n')

    def save_txt(self):
        if not self.data:
            messagebox.showinfo('Sin datos', 'Primero procesa una carpeta.')
            return
        path = filedialog.asksaveasfilename(title='Guardar resumen TXT', defaultextension='.txt', initialfile='RESUMEN_CSV.txt', filetypes=[('Archivo de texto', '*.txt')])
        if path:
            try:
                self._write_txt(path)
                messagebox.showinfo('Guardado', f'Resumen guardado en:\n{path}')
            except Exception as exc:
                messagebox.showerror('Error', str(exc))

    def export_excel(self):
        if not self.data:
            messagebox.showinfo('Sin datos', 'Primero procesa una carpeta.')
            return
        path = filedialog.asksaveasfilename(title='Exportar resumen a Excel', defaultextension='.xlsx', initialfile='RESUMEN_CSV.xlsx', filetypes=[('Excel', '*.xlsx')])
        if not path:
            return
        try:
            from openpyxl import Workbook
            from openpyxl.styles import Font, PatternFill, Alignment
            wb = Workbook()
            ws = wb.active
            ws.title = 'Resumen'
            ws.append(self.headers)
            for row in self.data:
                ws.append([v if v is not None else '' for v in row])
            # Excel: formato de dos decimales sólo para los dos KPI de throughput Outdoor.
            if self.mode.get() == 'Outdoor':
                for excel_row, data_row in enumerate(self.data, start=2):
                    if data_row and data_row[0] in OUTDOOR_ROWS[:2]:
                        for excel_col in range(2, len(self.headers) + 1):
                            cell = ws.cell(row=excel_row, column=excel_col)
                            if isinstance(cell.value, (int, float)):
                                cell.number_format = '0.00'
            for cell in ws[1]:
                cell.font = Font(bold=True, color='FFFFFF')
                cell.fill = PatternFill('solid', fgColor='365F91')
                cell.alignment = Alignment(horizontal='center')
            ws.freeze_panes = 'B2'
            ws.auto_filter.ref = ws.dimensions
            for col in ws.columns:
                letter = col[0].column_letter
                ws.column_dimensions[letter].width = min(max(max(len(str(c.value or '')) for c in col) + 2, 14), 42)
            wb.save(path)
            messagebox.showinfo('Exportación completada', f'Excel guardado en:\n{path}')
        except ImportError:
            messagebox.showerror('Falta una librería', 'Para exportar Excel instala openpyxl con:\npython -m pip install openpyxl')
        except Exception as exc:
            messagebox.showerror('Error al exportar', str(exc))


if __name__ == '__main__':
    App().mainloop()
