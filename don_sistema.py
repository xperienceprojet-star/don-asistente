#!/usr/bin/env python3
"""
DON - Módulo de Batería y Chip
Monitorea batería y detecta chip/SIM automáticamente
"""

import os
import json
import time
import threading
import subprocess

# ─── BATERÍA ─────────────────────────────────────────────

ARCHIVO_ESTADO   = os.path.expanduser("~/.don_estado.json")
ULTIMO_AVISO_BAT = None   # Para no repetir avisos

def leer_bateria():
    """Lee el nivel y estado de carga de la batería vía Termux API"""
    try:
        resultado = subprocess.run(
            ['termux-battery-status'],
            capture_output=True, text=True, timeout=5
        )
        datos = json.loads(resultado.stdout)
        return {
            "nivel":    datos.get("percentage", 100),
            "cargando": datos.get("status", "") == "CHARGING",
            "estado":   datos.get("status", "UNKNOWN")
        }
    except Exception as e:
        print(f"[batería] Error: {e}")
        return {"nivel": 100, "cargando": False, "estado": "UNKNOWN"}


def actualizar_pantalla_bateria(nivel, cargando):
    """
    Escribe el nivel de batería en el archivo de estado
    para que la pantalla web lo muestre
    """
    try:
        # Leer estado actual
        estado = {}
        if os.path.exists(ARCHIVO_ESTADO):
            with open(ARCHIVO_ESTADO) as f:
                estado = json.load(f)

        estado["bateria"]  = nivel
        estado["cargando"] = cargando

        # Color de alerta para la pantalla
        if nivel <= 15:
            estado["alerta_bateria"] = "critica"
        elif nivel <= 30:
            estado["alerta_bateria"] = "baja"
        else:
            estado["alerta_bateria"] = "normal"

        with open(ARCHIVO_ESTADO, 'w') as f:
            json.dump(estado, f)
    except:
        pass


def monitorear_bateria(hablar_fn):
    """
    Corre en segundo plano.
    Avisa por voz cuando la batería está baja.
    """
    global ULTIMO_AVISO_BAT

    while True:
        try:
            bat = leer_bateria()
            nivel    = bat["nivel"]
            cargando = bat["cargando"]

            actualizar_pantalla_bateria(nivel, cargando)

            if not cargando:
                if nivel <= 5 and ULTIMO_AVISO_BAT != "critica":
                    hablar_fn("Atención, batería al cinco por ciento. Conectá el cargador urgente.")
                    ULTIMO_AVISO_BAT = "critica"
                    time.sleep(60)

                elif nivel <= 15 and ULTIMO_AVISO_BAT not in ("critica", "muy_baja"):
                    hablar_fn("La batería está al quince por ciento. Te recomiendo conectar el cargador.")
                    ULTIMO_AVISO_BAT = "muy_baja"
                    time.sleep(300)  # Espera 5 min antes del próximo aviso

                elif nivel <= 30 and ULTIMO_AVISO_BAT not in ("critica", "muy_baja", "baja"):
                    hablar_fn("La batería está al treinta por ciento.")
                    ULTIMO_AVISO_BAT = "baja"

            else:
                # Si está cargando, resetear los avisos
                if nivel >= 35:
                    ULTIMO_AVISO_BAT = None

        except Exception as e:
            print(f"[batería] Error en monitoreo: {e}")

        time.sleep(120)  # Chequea cada 2 minutos


def iniciar_monitoreo_bateria(hablar_fn):
    """Inicia el monitoreo de batería en hilo separado"""
    hilo = threading.Thread(
        target=monitorear_bateria,
        args=(hablar_fn,),
        daemon=True
    )
    hilo.start()
    print("🔋 Monitor de batería iniciado")


# ─── CHIP / SIM ───────────────────────────────────────────

def detectar_chip():
    """
    Detecta si hay un chip SIM insertado y obtiene info básica
    """
    try:
        resultado = subprocess.run(
            ['termux-telephony-deviceinfo'],
            capture_output=True, text=True, timeout=5
        )
        datos = json.loads(resultado.stdout)
        numero   = datos.get("phone_number", "")
        operador = datos.get("network_operator_name", "")
        tipo     = datos.get("phone_type", "")

        tiene_chip = bool(operador or tipo)

        return {
            "tiene_chip": tiene_chip,
            "numero":     numero if numero not in ("", "null", None) else None,
            "operador":   operador or None,
        }
    except Exception as e:
        print(f"[chip] Error: {e}")
        return {"tiene_chip": False, "numero": None, "operador": None}


def verificar_chip_al_inicio(hablar_fn):
    """
    Verifica el chip al arrancar Don y avisa al usuario.
    Si no hay chip, ofrece guía por voz.
    """
    info = detectar_chip()

    if info["tiene_chip"]:
        operador = info["operador"] or "tu operadora"
        numero   = info["numero"]

        if numero:
            hablar_fn(f"Chip detectado. Estás con {operador}, número {numero}.")
        else:
            hablar_fn(f"Chip detectado. Estás conectado con {operador}.")

        return True

    else:
        hablar_fn(
            "No detecté ningún chip. "
            "Insertá tu SIM y decime cuando esté listo, "
            "o decí: Don, ya inserté el chip."
        )
        return False


def esperar_chip(hablar_fn, intentos=5):
    """
    Espera a que el usuario inserte el chip.
    Se llama cuando el usuario dice 'ya inserté el chip'
    """
    hablar_fn("Dame un momento, estoy detectando el chip.")
    for i in range(intentos):
        time.sleep(3)
        info = detectar_chip()
        if info["tiene_chip"]:
            operador = info["operador"] or "tu operadora"
            hablar_fn(f"Perfecto, chip de {operador} detectado. Ya estás conectado.")
            return True

    hablar_fn("No pude detectar el chip. Fijate que esté bien insertado e intentá de nuevo.")
    return False


def manejar_comando_chip(texto, hablar_fn):
    """
    Detecta comandos relacionados al chip/SIM.
    Devuelve True si manejó el comando.
    """
    t = texto.lower()

    if any(p in t for p in ['inserté el chip', 'puse el chip', 'ya tiene chip', 'ya puse la sim']):
        esperar_chip(hablar_fn)
        return True

    if any(p in t for p in ['qué chip', 'qué sim', 'qué operadora', 'qué número tengo']):
        info = detectar_chip()
        if info["tiene_chip"]:
            partes = []
            if info["operador"]:
                partes.append(f"operadora {info['operador']}")
            if info["numero"]:
                partes.append(f"número {info['numero']}")
            hablar_fn("Tu chip es de " + " y tu ".join(partes) + "." if partes else "Chip detectado pero sin información disponible.")
        else:
            hablar_fn("No hay ningún chip insertado.")
        return True

    if any(p in t for p in ['cuánta batería', 'batería', 'carga tengo']):
        bat = leer_bateria()
        estado = "cargando" if bat["cargando"] else "en uso"
        hablar_fn(f"La batería está al {bat['nivel']} por ciento, {estado}.")
        return True

    return False