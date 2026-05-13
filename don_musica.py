#!/usr/bin/env python3
"""
DON - Módulo de Música y SD
Se importa desde el script principal de Don
"""

import os
import json
import subprocess
import threading
import time
import random

# ─── CONFIGURACIÓN ───────────────────────────────────────
RUTA_SD        = "/sdcard"                  # Ruta base en Android
EXTENSIONES    = ('.mp3', '.flac', '.wav', '.ogg', '.m4a', '.aac')
ARCHIVO_BIBLIO = os.path.expanduser("~/.don_musica.json")
PROCESO_MUSIC  = None                       # Proceso reproductor activo

# ─── BIBLIOTECA ──────────────────────────────────────────

def escanear_sd():
    """Escanea la SD y construye la biblioteca de música"""
    canciones = []
    
    if not os.path.exists(RUTA_SD):
        return []

    print("🔍 Escaneando SD...")
    for raiz, dirs, archivos in os.walk(RUTA_SD):
        # Ignorar carpetas del sistema
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        for archivo in archivos:
            if archivo.lower().endswith(EXTENSIONES):
                ruta = os.path.join(raiz, archivo)
                nombre = os.path.splitext(archivo)[0]
                # Intentar limpiar el nombre
                nombre_limpio = nombre.replace('_', ' ').replace('-', ' ').strip()
                canciones.append({
                    "nombre": nombre_limpio,
                    "archivo": nombre,
                    "ruta": ruta,
                    "carpeta": os.path.basename(raiz)
                })

    print(f"✅ Encontré {len(canciones)} canciones")
    return canciones


def guardar_biblioteca(canciones):
    """Guarda la biblioteca en disco"""
    with open(ARCHIVO_BIBLIO, 'w', encoding='utf-8') as f:
        json.dump(canciones, f, ensure_ascii=False, indent=2)


def cargar_biblioteca():
    """Carga la biblioteca guardada"""
    if not os.path.exists(ARCHIVO_BIBLIO):
        return []
    try:
        with open(ARCHIVO_BIBLIO, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return []


def sincronizar_sd(hablar_fn):
    """
    Detecta si hay música nueva en la SD y sincroniza.
    hablar_fn: función para que Don hable (del script principal)
    """
    biblioteca_vieja = cargar_biblioteca()
    canciones_nuevas = escanear_sd()

    if not canciones_nuevas:
        return biblioteca_vieja

    if len(canciones_nuevas) != len(biblioteca_vieja):
        guardar_biblioteca(canciones_nuevas)
        diff = len(canciones_nuevas) - len(biblioteca_vieja)
        if diff > 0:
            hablar_fn(f"Encontré {len(canciones_nuevas)} canciones en tu tarjeta. Ya las tengo cargadas.")
        return canciones_nuevas

    return biblioteca_vieja


# ─── REPRODUCCIÓN ────────────────────────────────────────

def buscar_cancion(consulta, biblioteca):
    """Busca una canción por nombre aproximado"""
    consulta = consulta.lower()
    resultados = []

    for c in biblioteca:
        nombre = c['nombre'].lower()
        carpeta = c['carpeta'].lower()
        # Coincidencia directa
        if consulta in nombre or consulta in carpeta:
            resultados.append(c)

    return resultados


def reproducir(ruta, hablar_fn):
    """Reproduce un archivo de audio con mpv o termux-media-player"""
    global PROCESO_MUSIC
    detener()  # Para cualquier reproducción anterior

    # Intentar con termux-media-player primero (más nativo)
    try:
        PROCESO_MUSIC = subprocess.Popen(
            ['termux-media-player', 'play', ruta],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        return True
    except FileNotFoundError:
        pass

    # Fallback: mpv
    try:
        PROCESO_MUSIC = subprocess.Popen(
            ['mpv', '--no-video', '--really-quiet', ruta],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        return True
    except FileNotFoundError:
        hablar_fn("No tengo reproductor de audio instalado. Instalá mpv desde Termux.")
        return False


def detener():
    """Detiene la reproducción"""
    global PROCESO_MUSIC
    if PROCESO_MUSIC:
        try:
            PROCESO_MUSIC.terminate()
        except:
            pass
        PROCESO_MUSIC = None
    # También detener termux-media-player si está corriendo
    os.system("termux-media-player stop 2>/dev/null")


def pausar():
    os.system("termux-media-player pause 2>/dev/null")


def reanudar():
    os.system("termux-media-player play 2>/dev/null")


# ─── RADIO FM ────────────────────────────────────────────

def abrir_radio(frecuencia=None, hablar_fn=None):
    """
    Intenta abrir la radio FM del dispositivo.
    Usa intent de Android vía am (activity manager).
    """
    # Método 1: Intent genérico de radio FM
    intent_radio = (
        "am start -a android.intent.action.MAIN "
        "-n com.android.fmradio/.FmMainActivity "
        "2>/dev/null"
    )

    resultado = os.system(intent_radio)

    if resultado != 0:
        # Método 2: Intent abierto (cualquier app de radio instalada)
        os.system(
            "am start -a android.intent.action.VIEW "
            "-t audio/x-mpegurl 2>/dev/null"
        )

    if hablar_fn:
        if frecuencia:
            hablar_fn(f"Abriendo radio en {frecuencia} FM.")
        else:
            hablar_fn("Abriendo la radio.")


def cerrar_radio():
    os.system("am force-stop com.android.fmradio 2>/dev/null")


# ─── INTÉRPRETE DE COMANDOS ──────────────────────────────

def manejar_comando_musica(texto, hablar_fn):
    """
    Interpreta comandos de voz relacionados a música y radio.
    Devuelve True si manejó el comando, False si no era de música.
    """
    t = texto.lower()
    biblioteca = cargar_biblioteca()

    # ── RADIO ──
    if any(p in t for p in ['radio', 'fm']):
        # Extraer frecuencia si la dicen
        import re
        freq = re.search(r'(\d{2,3}[\.,]\d)', t)
        frecuencia = freq.group(1).replace(',', '.') if freq else None
        abrir_radio(frecuencia, hablar_fn)
        return True

    # ── DETENER ──
    if any(p in t for p in ['pará', 'para la música', 'silencio', 'stop', 'detené']):
        detener()
        hablar_fn("Música detenida.")
        return True

    # ── PAUSAR ──
    if any(p in t for p in ['pausá', 'pausa', 'un momento']):
        pausar()
        hablar_fn("Pausado.")
        return True

    # ── REANUDAR ──
    if any(p in t for p in ['seguí', 'continuá', 'reanudá']):
        reanudar()
        hablar_fn("Continuando.")
        return True

    # ── ALEATORIO ──
    if any(p in t for p in ['algo', 'cualquier', 'aleatoria', 'sorprendeme', 'lo que sea']):
        if not biblioteca:
            hablar_fn("No encontré música en tu tarjeta.")
            return True
        cancion = random.choice(biblioteca)
        hablar_fn(f"Poniendo {cancion['nombre']}.")
        reproducir(cancion['ruta'], hablar_fn)
        return True

    # ── BUSCAR CANCIÓN ──
    if any(p in t for p in ['poné', 'pone', 'tocá', 'toca', 'escuchar', 'música']):
        if not biblioteca:
            hablar_fn("No tengo música cargada. Insertá tu tarjeta SD.")
            return True

        # Extraer qué quiere escuchar
        for palabra in ['poné', 'pone', 'tocá', 'toca', 'quiero escuchar', 'música de', 'ponerme']:
            t = t.replace(palabra, '').strip()

        if not t:
            # Sin especificar → aleatorio
            cancion = random.choice(biblioteca)
            hablar_fn(f"Poniendo {cancion['nombre']}.")
            reproducir(cancion['ruta'], hablar_fn)
            return True

        resultados = buscar_cancion(t, biblioteca)
        if resultados:
            cancion = resultados[0]
            hablar_fn(f"Poniendo {cancion['nombre']}.")
            reproducir(cancion['ruta'], hablar_fn)
        else:
            hablar_fn(f"No encontré {t} en tu música.")
        return True

    # ── SINCRONIZAR ──
    if any(p in t for p in ['sincronizá', 'actualizá la música', 'cargar música', 'escanear']):
        hablar_fn("Escaneando tu tarjeta, dame un momento.")
        canciones = escanear_sd()
        guardar_biblioteca(canciones)
        hablar_fn(f"Listo, cargué {len(canciones)} canciones.")
        return True

    return False  # No era un comando de música


# ─── MONITOREO SD ────────────────────────────────────────

def monitorear_sd(hablar_fn):
    """
    Corre en segundo plano y detecta cuando se inserta la SD.
    Llama a sincronizar automáticamente.
    """
    ultima_cantidad = len(cargar_biblioteca())

    while True:
        time.sleep(30)  # Chequea cada 30 segundos
        try:
            if os.path.exists(RUTA_SD):
                canciones = escanear_sd()
                if len(canciones) > ultima_cantidad + 5:  # Si hay 5+ canciones nuevas
                    guardar_biblioteca(canciones)
                    nuevas = len(canciones) - ultima_cantidad
                    hablar_fn(f"Detecté {nuevas} canciones nuevas en tu tarjeta. Ya las cargué.")
                    ultima_cantidad = len(canciones)
        except:
            pass


def iniciar_monitoreo_sd(hablar_fn):
    """Inicia el monitoreo de SD en un hilo separado"""
    hilo = threading.Thread(target=monitorear_sd, args=(hablar_fn,), daemon=True)
    hilo.start()