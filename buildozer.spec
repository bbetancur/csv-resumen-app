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
source.dir = .

# (list) Archivo principal de Python
source.main_file = main.py

# (list) Requisitos de tu aplicación
requirements = python310,kivy,openpyxl,pyjnius

# (str) Rama de python-for-android a utilizar (añade esta línea al final)
p4a.branch = release-2024.01.21

# (bool) Indicate if you accept the Android SDK license
android.accept_sdk_license = True

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

# Modo de advertencia para root (1 = permitir compilar como root)
warn_on_root = 1

# (list) Target architectures
android.archs = arm64-v8a

# (int) Android NDK version to use
android.ndk = 23b

android.api = 33
android.minapi = 21
