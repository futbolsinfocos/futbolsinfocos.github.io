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


SISTEMA_PREVIA = """Eres redactor de la sección de previas de un diario deportivo serio. Escribes la \
previa de los partidos que se juegan hoy en una competición. Español de España, estilo de agencia: \
sobrio, preciso, informativo. Frases cortas.

Qué recibes (JSON): la competición, los partidos (equipos, hora de Madrid, estadio, ciudad, jornada, \
árbitro) y, cuando los hay, "forma" (últimos resultados publicados de cada equipo, G/E/P con marcador) \
e "historial" (enfrentamientos previos entre esos dos equipos que tenemos publicados).

Lo que NO hace falta que escribas: la hora, el estadio, la ciudad, la jornada y el árbitro ya salen en una \
ficha fija debajo del título de cada partido. No los repitas salvo que aporten algo (p. ej. un horario distinto).

Normas estrictas:
- Usa EXCLUSIVAMENTE los datos del JSON. Prohibido inventar alineaciones, bajas, lesiones, declaraciones, \
cuotas, pronósticos, posiciones en la tabla, rachas o contexto histórico que no estén en los datos.
- Nada de relleno ni clichés: prohibido "el balón echa a rodar", "abrir boca", "cita", "duelo de \
alto voltaje", "con la misión de", "ante su gente", "noche mágica" y similares. Si no hay datos que \
analizar de un partido, deja su texto VACÍO. Es mejor una previa corta que una previa hueca.
- Cuando haya forma o historial, conviértelos en información útil: rachas ("tres victorias seguidas"), \
goles a favor y en contra, resultado del último enfrentamiento. Cifras exactas, sin adjetivos de más.
- Nombres de equipos tal cual vienen.

Campos:
- titular: informativo, máx. 90 caracteres, sin dos puntos al principio ni signos de exclamación. \
Destaca el partido o el dato más relevante.
- entradilla: 1-2 frases con lo esencial (cuántos partidos, el más destacado y por qué).
- presentacion: 1 párrafo corto de contexto de la jornada con datos reales; vacío si no aporta nada nuevo.
- claves: 0-3 frases con datos concretos (rachas, historial). Lista vacía si no hay datos.
- partidos: un elemento por partido (id) con "texto": 1-3 frases de análisis con datos, o "" si no hay.
- texto_instagram: lista de los partidos con su hora, 1-2 emojis como máximo, sin relleno.
- partido_destacado_id: el partido más relevante según los datos (o el de mayor categoría)."""

ESQUEMA_PREVIA = {
    "type": "object",
    "properties": {
        "titular": {"type": "string"},
        "entradilla": {"type": "string"},
        "presentacion": {"type": "string"},
        "claves": {"type": "array", "items": {"type": "string"}},
        "partidos": {"type": "array", "items": {
            "type": "object",
            "properties": {"id": {"type": "integer"}, "texto": {"type": "string"}},
            "required": ["id", "texto"], "additionalProperties": False}},
        "texto_instagram": {"type": "string"},
        "hashtags": {"type": "array", "items": {"type": "string"}},
        "partido_destacado_id": {"type": "integer"},
    },
    "required": ["titular", "entradilla", "presentacion", "claves", "partidos", "texto_instagram",
                 "hashtags", "partido_destacado_id"],
    "additionalProperties": False,
}


def redactar(paquete: dict, config: dict, demo: bool = False) -> dict:
    if demo or not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
        return redactar_plantilla(paquete)
    return _llamar(SISTEMA, "Escribe la crónica de esta jornada. Datos:\n", paquete, config, ESQUEMA)


def redactar_previa(paquete: dict, config: dict, demo: bool = False) -> dict:
    if demo or not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
        return previa_plantilla(paquete)
    from .previas import cuerpo, jornada_es
    datos = {**paquete, "partidos": [{**p, "jornada": jornada_es(p.get("jornada"))} for p in paquete["partidos"]]}
    texto = _llamar(SISTEMA_PREVIA, "Escribe la previa de los partidos de hoy. Datos:\n", datos, config, ESQUEMA_PREVIA)
    texto["cuerpo_markdown"] = cuerpo(paquete, texto)
    return texto


def _llamar(sistema: str, instruccion: str, paquete: dict, config: dict, esquema: dict) -> dict:
    import anthropic

    client = anthropic.Anthropic()
    modelo = config["ia"]["modelo"]
    peticion = dict(
        model=modelo,
        max_tokens=16000,
        system=sistema,
        output_config={"effort": config["ia"].get("esfuerzo", "low"),
                       "format": {"type": "json_schema", "schema": esquema}},
        messages=[{"role": "user", "content":
                   instruccion + json.dumps(paquete, ensure_ascii=False)}],
    )
    if "haiku" in modelo:
        resp = client.messages.create(**peticion)
    else:
        # Si el modelo principal declina por un falso positivo de seguridad, la API reintenta sola
        resp = client.beta.messages.create(**peticion, betas=["server-side-fallback-2026-07-01"],
                                           fallbacks="default")
    if resp.stop_reason == "refusal":
        raise RuntimeError(f"El modelo declinó el texto de {paquete['liga']['etiqueta']}")
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


def hora(iso: str) -> str:
    """'2026-11-14T18:30:00+01:00' → '18:30' (las fechas ya vienen en hora de Madrid)."""
    return iso[11:16] if len(iso) >= 16 else ""


def previa_plantilla(paquete: dict) -> dict:
    """Previa sin IA (modo demo o sin clave): solo datos, con la misma ficha que la versión con IA."""
    from .previas import cuerpo
    liga = paquete["liga"]["etiqueta"]
    ps = paquete["partidos"]
    texto = {
        "titular": f"{ps[0]['local']} - {ps[0]['visitante']} abre la jornada de {liga}",
        "entradilla": f"{len(ps)} partido{'s' if len(ps) != 1 else ''} hoy en {liga}. El primero, a las {hora(ps[0]['fecha'])}.",
        "presentacion": "", "claves": [], "partidos": [],
        "texto_instagram": f"📅 Hoy en {liga}\n" + "\n".join(
            f"{hora(p['fecha'])} {p['local']} - {p['visitante']}" for p in ps),
        "hashtags": ["futbol", liga.split(" ·")[0].replace(" ", "").lower()],
        "partido_destacado_id": ps[0]["id"],
    }
    texto["cuerpo_markdown"] = cuerpo(paquete, texto)
    return texto
