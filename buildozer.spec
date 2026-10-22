[app]
# (str) Título de tu aplicación
title = CSV Resumen Outdoor Indoor

# (str) Nombre del paquete (sin espacios ni mayúsculas)
package.name = csvresumen

# (str) Dominio del paquete
package.domain = org.benjamin

# (list) Archivos a incluir (separados por comas)
source.include_exts = py,png,jpg,kv,atlas

# (list) Aplicación principal a ejecutar
source.dir =. 

# (list) Archivo principal de Python
source.main_file = main.py

# (list) Requisitos de tu aplicación
# Nota: 'jnius' solo funciona en Android, pero Buildozer lo maneja bien.
requirements = python3,kivy,openpyxl,jnius

# (str) Versión de la aplicación
version = 1.0

# (list) Permisos requeridos
android.permissions = READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE

# (str) Orientación soportada (portrait, landscape o all)
orientation = portrait

# (int) Versión de la API de Android objetivo
android.api = 33

# (int) SDK mínimo soportado
android.minapi = 21

[buildozer]
# Nivel de registro (0 = error, 1 = info, 2 = debug)
log_level = 2

# Modo de advertencia para root (1 = permitir compilar como root, útil en Google Colab)
warn_on_root = 1

# (list) Target architectures
android.archs = arm64-v8a