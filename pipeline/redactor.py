"""Redacción de crónicas con Claude a partir SOLO de datos verificados.

Regla de oro: el modelo no puede inventar. Recibe el JSON del partido y la clasificación
y devuelve titular, entradilla, cuerpo y texto para Instagram. Nada de citas, lesiones,
fichajes ni datos que no estén en la entrada.
"""
from __future__ import annotations

import json
import os

SISTEMA = """Eres redactor de un diario digital especializado en fútbol de categorías inferiores \
(Segunda, Primera y Segunda Federación, Tercera y ligas equivalentes en el extranjero).
Escribes en español de España, tono periodístico cercano, frases cortas.

Normas estrictas:
- Usa EXCLUSIVAMENTE los datos del JSON recibido. Si un dato no está, no lo menciones.
- Prohibido inventar declaraciones, lesiones, asistencias, público, tiempo, árbitros o contexto histórico.
- No valores la actuación de jugadores concretos más allá de quién marcó y en qué minuto.
- Los nombres de equipos y jugadores se copian tal cual vienen.
- Destaca lo noticiable con los datos: goleadas, remontadas (si el orden de goles lo muestra), \
cambios de liderato, equipos en zona alta o baja según la clasificación.
- El cuerpo va en Markdown: un párrafo de resumen de la jornada, luego un apartado por partido \
destacado y un cierre con la clasificación (top 3 y colista). Si la clasificación viene vacía \
(por ejemplo, en una copa), no escribas ese apartado ni menciones que falta."""

ESQUEMA = {
    "type": "object",
    "properties": {
        "titular": {"type": "string", "description": "Máx. 90 caracteres, sin clickbait"},
        "entradilla": {"type": "string", "description": "1-2 frases"},
        "cuerpo_markdown": {"type": "string"},
        "texto_instagram": {"type": "string", "description": "Máx. 600 caracteres, con 2-3 emojis"},
        "hashtags": {"type": "array", "items": {"type": "string"}},
        "partido_destacado_id": {"type": "integer"},
    },
    "required": ["titular", "entradilla", "cuerpo_markdown", "texto_instagram", "hashtags",
                 "partido_destacado_id"],
    "additionalProperties": False,
}


def redactar(paquete: dict, config: dict, demo: bool = False) -> dict:
    if demo or not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
        return redactar_plantilla(paquete)
    import anthropic

    client = anthropic.Anthropic()
    modelo = config["ia"]["modelo"]
    peticion = dict(
        model=modelo,
        max_tokens=16000,
        system=SISTEMA,
        output_config={"effort": config["ia"].get("esfuerzo", "low"),
                       "format": {"type": "json_schema", "schema": ESQUEMA}},
        messages=[{"role": "user", "content":
                   "Escribe la crónica de esta jornada. Datos:\n" +
                   json.dumps(paquete, ensure_ascii=False)}],
    )
    if "haiku" in modelo:
        resp = client.messages.create(**peticion)
    else:
        # Si el modelo principal declina por un falso positivo de seguridad, la API reintenta sola
        resp = client.beta.messages.create(**peticion, betas=["server-side-fallback-2026-07-01"],
                                           fallbacks="default")
    if resp.stop_reason == "refusal":
        raise RuntimeError(f"El modelo declinó la crónica de {paquete['liga']['etiqueta']}")
    if resp.stop_reason == "max_tokens":
        raise RuntimeError("Respuesta cortada por max_tokens")
    texto = next(b.text for b in resp.content if b.type == "text")
    return json.loads(texto)


def redactar_plantilla(paquete: dict) -> dict:
    """Versión sin IA (modo demo o si no hay clave): crónica mínima pero correcta."""
    liga = paquete["liga"]["etiqueta"]
    ps = paquete["partidos"]
    destacado = max(ps, key=lambda p: abs(p["goles_local"] - p["goles_visitante"]) + p["goles_local"] + p["goles_visitante"])
    lineas = [f"- **{p['local']} {p['goles_local']}-{p['goles_visitante']} {p['visitante']}**" for p in ps]
    tabla = paquete["clasificacion"]
    cierre = ""
    if tabla:
        top = ", ".join(f"{t['equipo']} ({t['pts']})" for t in tabla[:3])
        cierre = f"\n\n## Clasificación\n\nArriba: {top}. Cierra la tabla {tabla[-1]['equipo']} con {tabla[-1]['pts']} puntos."
    total = sum(p["goles_local"] + p["goles_visitante"] for p in ps)
    return {
        "titular": f"{destacado['local']} {destacado['goles_local']}-{destacado['goles_visitante']} {destacado['visitante']}, lo más destacado en {liga}",
        "entradilla": f"La jornada en {liga} dejó {len(ps)} partidos y {total} goles.",
        "cuerpo_markdown": f"## Resultados\n\n" + "\n".join(lineas) + cierre,
        "texto_instagram": f"⚽ Resultados de {liga}\n" + "\n".join(
            f"{p['local']} {p['goles_local']}-{p['goles_visitante']} {p['visitante']}" for p in ps),
        "hashtags": ["futbolmodesto", liga.split(" ·")[0].replace(" ", "").lower()],
        "partido_destacado_id": destacado["id"],
    }
