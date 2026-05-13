#!/usr/bin/env python3
"""
DON - Asistente de voz personal
Versión 2.0 — con música, radio y sincronización SD
"""

import os
import time
import json
import threading
from groq import Groq
from don_musica import (
    manejar_comando_musica,
    sincronizar_sd,
    iniciar_monitoreo_sd,
    cargar_biblioteca
)

# ─── CONFIGURACIÓN ───────────────────────────────────────
API_KEY = os.getenv("GROQ_API_KEY", "")
NOMBRE_ASISTENTE   = "Don"
PALABRA_CLAVE      = "don"
DURACION_GRABACION = 5
ARCHIVO_CONFIG     = os.path.expanduser("~/.don_config.json")

client = Groq(api_key=API_KEY)

# Memoria de conversación
historial = [
    {
        "role": "system",
        "content": f"""Sos {NOMBRE_ASISTENTE}, un asistente de voz argentino, amigable y directo.
Respondés en 1 o 2 oraciones máximo, de forma natural como si hablaras.
Podés recordar lo que se habló antes en la conversación.
Si te piden hacer una llamada, decí el número en voz alta.
Si te piden un recordatorio, confirmalo con hora y mensaje.
Conocés la música del usuario y podés recomendarla.
Cuando el usuario pide música o radio, simplemente confirmá que lo vas a hacer."""
    }
]

# ─── CONFIG ──────────────────────────────────────────────

def cargar_config():
    """Carga la configuración guardada desde el setup"""
    if not os.path.exists(ARCHIVO_CONFIG):
        return {}
    try:
        with open(ARCHIVO_CONFIG) as f:
            return json.load(f)
    except:
        return {}

# ─── VOZ ─────────────────────────────────────────────────

def hablar(texto):
    """Convierte texto a voz"""
    texto_limpio = texto.replace('"', '').replace("'", '').replace('`', '')
    os.system(f'termux-tts-speak -l es "{texto_limpio}"')
    # Notificar a la pantalla web que Don está hablando
    _set_estado_pantalla(True)
    time.sleep(len(texto) * 0.06)  # Espera aproximada
    _set_estado_pantalla(False)


def _set_estado_pantalla(hablando: bool):
    """Escribe el estado para que la pantalla web lo lea"""
    try:
        estado = {"hablando": hablando}
        with open(os.path.expanduser("~/.don_estado.json"), 'w') as f:
            json.dump(estado, f)
    except:
        pass

# ─── AUDIO ───────────────────────────────────────────────

def grabar_audio(segundos=DURACION_GRABACION, archivo="audio.wav"):
    os.system(f"termux-microphone-record -f {archivo} -l {segundos} -r 16000")
    time.sleep(segundos + 0.5)


def transcribir(archivo="audio.wav"):
    try:
        with open(archivo, "rb") as f:
            resultado = client.audio.transcriptions.create(
                file=(archivo, f.read()),
                model="whisper-large-v3",
                language="es"
            )
        return resultado.text.strip()
    except Exception as e:
        print(f"Error transcribiendo: {e}")
        return ""


def detectar_palabra_clave():
    os.system("rm -f escucha.wav")
    os.system("termux-microphone-record -f escucha.wav -l 3 -r 16000")
    time.sleep(4.5)
    try:
        with open("escucha.wav", "rb") as f:
            resultado = client.audio.transcriptions.create(
                file=("escucha.wav", f.read()),
                model="whisper-large-v3",
                language="es"
            )
        texto = resultado.text.lower()
        print(f"  [escucha]: {texto}")
        return PALABRA_CLAVE in texto
    except:
        return False

# ─── IA ──────────────────────────────────────────────────

def responder_ia(texto_usuario):
    """Llama a la IA con historial de conversación"""
    historial.append({"role": "user", "content": texto_usuario})
    try:
        respuesta = client.chat.completions.create(
            messages=historial,
            model="llama-3.3-70b-versatile",
            max_tokens=150
        )
        texto_respuesta = respuesta.choices[0].message.content
        historial.append({"role": "assistant", "content": texto_respuesta})
        # Limitar historial (últimas 10 interacciones)
        if len(historial) > 21:
            historial[1:3] = []
        return texto_respuesta
    except Exception as e:
        print(f"Error en IA: {e}")
        return "No pude procesar eso, intentá de nuevo."

# ─── LLAMADAS ────────────────────────────────────────────

def manejar_llamada(texto):
    """Detecta si piden una llamada y la realiza"""
    import re
    t = texto.lower()
    if any(p in t for p in ['llamá', 'llama a', 'llamar a', 'marcá']):
        numero = re.search(r'[\d\s\-\+]{6,}', texto)
        if numero:
            num = numero.group().replace(' ', '').replace('-', '')
            hablar(f"Llamando al {num}.")
            os.system(f"termux-telephony-call {num}")
            return True
        else:
            hablar("¿A qué número querés que llame?")
            return True
    return False

# ─── RECORDATORIOS ───────────────────────────────────────

recordatorios = []

def manejar_recordatorio(texto):
    """Detecta y programa recordatorios simples"""
    import re
    t = texto.lower()
    if any(p in t for p in ['recordame', 'recordá', 'avisame', 'poné un recordatorio']):
        # Buscar hora en el texto
        hora = re.search(r'(\d{1,2})[:\.]?(\d{2})?\s*(am|pm)?', t)
        if hora:
            h = hora.group(0)
            hablar(f"Listo, te recuerdo a las {h}.")
            # TODO: integrar con termux-notification para alarma real
        else:
            hablar("¿A qué hora querés que te recuerde?")
        return True
    return False

# ─── PROCESADOR CENTRAL ──────────────────────────────────

def procesar(texto):
    """
    Decide qué hacer con lo que dijo el usuario.
    Orden de prioridad: llamadas → música/radio → recordatorios → IA
    """
    # 1. Llamadas
    if manejar_llamada(texto):
        return

    # 2. Música y radio
    if manejar_comando_musica(texto, hablar):
        return

    # 3. Recordatorios
    if manejar_recordatorio(texto):
        return

    # 4. Respuesta general por IA
    respuesta = responder_ia(texto)
    print(f"{NOMBRE_ASISTENTE}: {respuesta}")
    hablar(respuesta)

# ─── INICIO ──────────────────────────────────────────────

def inicio():
    """Rutina de arranque de Don"""
    config = cargar_config()
    nombre_usuario = config.get('usuario', '')

    print(f"\n{'='*40}")
    print(f"  {NOMBRE_ASISTENTE} v2.0")
    print(f"  Usuario: {nombre_usuario or 'sin configurar'}")
    print(f"  Palabra clave: '{PALABRA_CLAVE}'")
    print(f"{'='*40}\n")

    # Sincronizar música de la SD al arrancar
    biblioteca = sincronizar_sd(hablar)
    canciones = len(biblioteca)

    # Saludo personalizado
    if nombre_usuario:
        if canciones > 0:
            hablar(f"Hola {nombre_usuario}, estoy listo. Tengo {canciones} canciones cargadas.")
        else:
            hablar(f"Hola {nombre_usuario}, estoy listo. Decí mi nombre para hablar.")
    else:
        hablar(f"Hola, soy {NOMBRE_ASISTENTE}. Decí mi nombre para activarme.")

    # Monitoreo de SD en segundo plano
    iniciar_monitoreo_sd(hablar)

# ─── LOOP PRINCIPAL ──────────────────────────────────────

def main():
    inicio()

    while True:
        try:
            print("👂 Escuchando palabra clave...")

            if detectar_palabra_clave():
                hablar("Te escucho.")
                print("🎙️  Grabando...")

                grabar_audio()
                texto = transcribir()

                if not texto:
                    hablar("No entendí, repetí por favor.")
                    continue

                print(f"Vos: {texto}")
                procesar(texto)
                print()

        except KeyboardInterrupt:
            print("\nApagando Don...")
            hablar("Hasta luego.")
            break
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(2)


if __name__ == "__main__":
    main()