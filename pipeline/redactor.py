"""Redacción de crónicas con Claude a partir SOLO de datos verificados.

Regla de oro: el modelo no puede inventar. Recibe el JSON del partido y la clasificación
y devuelve titular, entradilla, cuerpo y texto para Instagram. Nada de citas, lesiones,
fichajes ni datos que no estén en la entrada.
"""
from __future__ import annotations

import json
import os

SISTEMA = """Eres redactor de la sección de fútbol de un diario deportivo nacional serio (estilo Marca, As o \
El País deportes) especializado en categorías inferiores: Primera, Segunda y Tercera Federación, Segunda División \
y ligas extranjeras. Escribes en español de España, con oficio: frases cortas, verbos precisos, datos exactos, \
ritmo de periódico. Cada partido es una noticia y cada jornada una historia.

Qué recibes (JSON): la competición, los partidos (resultado, goleadores con minuto y tipo, expulsiones en "rojas", \
penaltis fallados en "penaltis_fallados", estadio, árbitro y, si las hay, "estadisticas" de posesión, tiros, \
a puerta, córners, faltas y tarjetas), la clasificación tras la jornada (puesto, puntos, G/E/P, goles, \
racha "forma" con W=ganado D=empate L=perdido, del más antiguo al más reciente, y "zona": ascenso, playoff o descenso) \
y "movimientos" (puesto de cada equipo antes y después de la jornada).

Normas estrictas:
- Usa EXCLUSIVAMENTE los datos del JSON. Si un dato no está, no lo menciones ni lo supongas.
- Prohibido inventar declaraciones, lesiones, asistencias, jugadas, ocasiones, público, tiempo, ambiente, \
alineaciones o contexto histórico. No describas cómo fue un gol: solo quién, en qué minuto y si fue de penalti o en propia.
- No valores la actuación de jugadores más allá de los hechos (goles, dobletes, expulsiones, penaltis fallados).
- Nombres de equipos y jugadores tal cual vienen. Si a un gol o una expulsión le falta el nombre, cuéntalo sin \
nombre ("una expulsión en el 61") y nunca digas que el dato falta.
- Para decir si un equipo sube o baja en la tabla usa SOLO "movimientos" (campo "cambio"); no lo deduzcas tú.
- "Goleó" solo con tres o más goles de diferencia.
- Prohibidos los clichés: "el balón echa a rodar", "partido de infarto", "duelo de titanes", "tres puntos de oro", \
"se llevó el gato al agua", "ver puerta", "a balón parado", "dar la campanada" y similares.
- Lo noticiable primero: cambios de liderato, entradas o salidas de la zona de ascenso, play-off o descenso \
(usa "movimientos" y "zona"), goleadas, remontadas (solo si el orden de goles lo demuestra), goles en el descuento \
(minuto 90 o más), expulsiones, penaltis fallados, rachas (cuenta en "forma": "tercera victoria seguida", \
"cinco partidos sin ganar") y, si hay estadísticas, un dato que cuente el partido ("ganó con solo dos tiros a puerta").

Estructura del cuerpo (Markdown):
1. Un párrafo de entrada con la historia de la jornada: lo más importante con cifras.
2. Un apartado "## Local X-Y Visitante" por CADA partido, ordenados de más a menos noticiable. \
Cada uno con un párrafo (dos en los dos más importantes): resultado, goles con minuto, expulsiones o penaltis \
fallados si los hay, y qué supone en la tabla para los dos equipos (puesto y puntos, si sube o baja). \
Nunca agrupes partidos en una lista de "otros resultados".
3. "## Así queda la clasificación": un párrafo con la cabeza, la zona de play-off o ascenso y la parte baja, \
con puntos y distancias ("a dos puntos del play-off"). Si la clasificación viene vacía (una copa), no escribas este apartado.
- Si los partidos son de varias divisiones de la misma competición (la jornada dice "Liga A", "Liga B"…, \
como en la Nations League), ordénalos por división de la A a la D y sepáralos con un subtítulo por división, \
tanto en el cuerpo como en texto_instagram (una línea "Liga A", sus partidos; "Liga B", los suyos…).

Crónica del partido estrella ("cronica_estrella"): solo si el JSON trae "con_cronica_estrella": true. \
Elige el partido más noticiable y escribe su crónica propia, que se publica en su página como una noticia: \
titular informativo (máx. 90 caracteres), entradilla de 1-2 frases, 4-6 párrafos en pirámide invertida \
(resultado y su consecuencia; cómo se fue construyendo el marcador por minutos; expulsiones o penaltis; \
estadísticas si las hay; situación de ambos en la tabla y racha) y "el_dato": una frase con la cifra más llamativa. \
Si "con_cronica_estrella" es false, devuelve cronica_estrella con partido_id 0 y el resto vacío."""

ESQUEMA = {
    "type": "object",
    "properties": {
        "titular": {"type": "string", "description": "Máx. 90 caracteres, sin clickbait"},
        "entradilla": {"type": "string", "description": "1-2 frases"},
        "cuerpo_markdown": {"type": "string"},
        "texto_instagram": {"type": "string", "description": "Pie de Instagram: 1-2 frases de resumen con lo más destacado de la jornada y después una línea por partido con resultado y goleadores (minuto). Máx. 900 caracteres, 2-3 emojis"},
        "hashtags": {"type": "array", "items": {"type": "string"}},
        "partido_destacado_id": {"type": "integer"},
        "cronica_estrella": {"type": "object", "properties": {
            "partido_id": {"type": "integer"},
            "titular": {"type": "string"},
            "entradilla": {"type": "string"},
            "parrafos": {"type": "array", "items": {"type": "string"}},
            "el_dato": {"type": "string"}},
            "required": ["partido_id", "titular", "entradilla", "parrafos", "el_dato"], "additionalProperties": False},
    },
    "required": ["titular", "entradilla", "cuerpo_markdown", "texto_instagram", "hashtags",
                 "partido_destacado_id", "cronica_estrella"],
    "additionalProperties": False,
}


SISTEMA_PREVIA = """Eres redactor de la sección de previas de un diario deportivo nacional serio (estilo Marca, \
As o El País deportes). Escribes las previas de los partidos que se juegan hoy en una competición: un texto general \
de la jornada y una previa completa de cada partido, que se publica en su propia página como una noticia. \
Español de España, con oficio: sobrio, preciso, con cifras. Frases cortas.

Qué recibes (JSON): la competición, la clasificación actual, y cada partido con hora de Madrid, estadio, ciudad, \
jornada, árbitro y, cuando los hay:
- "contexto": cómo llega cada equipo ("local" y "visitante"): puesto, puntos, partidos ganados/empatados/perdidos, \
goles a favor y en contra, "zona" (ascenso, playoff, descenso), su rendimiento en casa (local) o fuera (visitante), \
"racha" (últimos partidos, del más reciente al más antiguo, con rival, campo y marcador) y su máximo goleador.
- "historial": últimos enfrentamientos entre ambos (más reciente primero).

En la página de cada partido ya salen, fuera de tu texto, la ficha (estadio, hora, árbitro), un cuadro comparativo \
con puesto, puntos, goles y racha, y el historial. Tu texto no debe ser una lista de esas cifras: debe interpretarlas.

Normas estrictas:
- Usa EXCLUSIVAMENTE los datos del JSON. Prohibido inventar alineaciones, bajas, lesiones, sanciones, declaraciones, \
cuotas, pronósticos o contexto histórico que no esté en los datos.
- Prohibidos los clichés: "el balón echa a rodar", "abrir boca", "cita", "duelo de alto voltaje", "con la misión de", \
"ante su gente", "noche mágica", "partido de máxima igualdad", "final anticipada" y similares.
- Encuentra el ángulo: qué se juega cada uno en la tabla (liderato, play-off, descenso, distancia en puntos entre ellos), \
rachas ("lleva cuatro sin perder", "no gana fuera desde…" solo si la racha lo muestra), contraste casa/fuera, \
el goleador que llega en forma, el último precedente.
- Nombres de equipos tal cual vienen.
- Si los partidos son de varias divisiones de la misma competición (la jornada dice "Liga A", "Liga B"…, \
como en la Nations League), ordénalos por división de la A a la D y sepáralos con un subtítulo por división, \
tanto en el cuerpo como en texto_instagram.

Campos generales (artículo de la jornada):
- titular: informativo y con gancho, máx. 90 caracteres, sin exclamaciones.
- entradilla: 1-2 frases con lo esencial de la jornada (el partido grande y por qué).
- presentacion: 1 párrafo de contexto de la jornada en la tabla; vacío si no hay datos.
- claves: 0-3 frases con datos concretos de la jornada.
- texto_instagram: resumen de la previa en 2-4 frases con datos reales y después la lista de partidos con su hora. \
Máx. 900 caracteres, 1-2 emojis.
- partido_destacado_id: el partido más relevante según los datos.

Previa de cada partido (campo "partidos", uno por cada partido recibido, con su id):
- titular: como una noticia, con el ángulo del partido (no solo "X recibe a Y"), máx. 90 caracteres.
- entradilla: 1-2 frases con lo que está en juego.
- parrafos: 2 a 5 párrafos en pirámide invertida. Primero, qué se juega y cuándo y dónde. Después, cómo llega el local \
(puesto, puntos, racha, en casa, goleador), cómo llega el visitante (lo mismo, fuera) y el contexto en la tabla. \
Si casi no hay datos, 1-2 párrafos; nunca relleno.
- el_dato: una frase con la cifra más llamativa del partido; "" si no hay.
- precedente: 1-2 frases sobre el último enfrentamiento si viene en "historial"; "" si no.
- claves: 0-3 claves, cada una con "titulo" (2-5 palabras) y "texto" (una frase con un dato)."""

ESQUEMA_PREVIA = {
    "type": "object",
    "properties": {
        "titular": {"type": "string"},
        "entradilla": {"type": "string"},
        "presentacion": {"type": "string"},
        "claves": {"type": "array", "items": {"type": "string"}},
        "partidos": {"type": "array", "items": {
            "type": "object",
            "properties": {
                "id": {"type": "integer"},
                "titular": {"type": "string"},
                "entradilla": {"type": "string"},
                "parrafos": {"type": "array", "items": {"type": "string"}},
                "precedente": {"type": "string"},
                "el_dato": {"type": "string"},
                "claves": {"type": "array", "items": {
                    "type": "object",
                    "properties": {"titulo": {"type": "string"}, "texto": {"type": "string"}},
                    "required": ["titulo", "texto"], "additionalProperties": False}},
            },
            "required": ["id", "titular", "entradilla", "parrafos", "precedente", "el_dato", "claves"],
            "additionalProperties": False}},
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
    from .previas import jornada_es
    datos = {**paquete, "partidos": [{**p, "jornada": jornada_es(p.get("jornada"))} for p in paquete["partidos"]],
             "con_cronica_estrella": paquete["liga"].get("prioridad", 3) <= 1}
    return _llamar(SISTEMA, "Escribe la crónica de esta jornada. Datos:\n", datos, config, ESQUEMA)


def redactar_previa(paquete: dict, config: dict, demo: bool = False) -> dict:
    if demo or not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
        return previa_plantilla(paquete)
    from .previas import cuerpo, jornada_es
    datos = {**paquete, "partidos": [{**p, "jornada": jornada_es(p.get("jornada"))} for p in paquete["partidos"]]}
    texto = _llamar(SISTEMA_PREVIA, "Escribe las previas de los partidos de hoy. Datos:\n", datos, config, ESQUEMA_PREVIA)
    texto["cuerpo_markdown"] = cuerpo(paquete, texto)
    texto["previas_partido"] = previas_partido(paquete, texto)
    return texto


def _sin_escudos(x):
    """Quita las URL de escudos e ids internos: a la IA no le sirven y encarecen la petición."""
    if isinstance(x, dict):
        return {k: _sin_escudos(v) for k, v in x.items() if not k.startswith("escudo") and k != "equipo_id"}
    if isinstance(x, list):
        return [_sin_escudos(v) for v in x]
    return x


def _llamar(sistema: str, instruccion: str, paquete: dict, config: dict, esquema: dict) -> dict:
    import anthropic

    client = anthropic.Anthropic()
    ia = config["ia"]
    prioridad = (paquete.get("liga") or {}).get("prioridad", 3)
    # Ahorro: el modelo bueno solo para las categorías principales; el resto, el barato
    modelo = ia["modelo"] if prioridad <= ia.get("modelo_bueno_hasta_prioridad", 9) else ia.get("modelo_barato", ia["modelo"])
    peticion = dict(
        model=modelo,
        max_tokens=32000,
        system=sistema,
        output_config={"effort": config["ia"].get("esfuerzo", "low"),
                       "format": {"type": "json_schema", "schema": esquema}},
        messages=[{"role": "user", "content":
                   instruccion + json.dumps(_sin_escudos(paquete), ensure_ascii=False)}],
    )
    if "haiku" in modelo:
        with client.messages.stream(**peticion) as flujo:
            resp = flujo.get_final_message()
    else:
        # Si el modelo principal declina por un falso positivo de seguridad, la API reintenta sola
        with client.beta.messages.stream(**peticion, betas=["server-side-fallback-2026-07-01"],
                                         fallbacks="default") as flujo:
            resp = flujo.get_final_message()
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
    texto["previas_partido"] = previas_partido(paquete, texto)
    return texto


def previas_partido(paquete: dict, texto: dict) -> list[dict]:
    """Una previa por partido (para su página propia). Si la IA no escribió nada de un partido,
    sale igual con un titular y un primer párrafo hechos solo con los datos."""
    from .previas import entrada_basica, slug_partido
    from .nombres import es
    escritos = {x["id"]: x for x in texto.get("partidos", [])}
    comp = paquete["liga"]["competicion"]
    salida = []
    for p in paquete["partidos"]:
        x = escritos.get(p["id"], {})
        parrafos = [t.strip() for t in x.get("parrafos", []) if t.strip()] or [entrada_basica(p, comp)]
        salida.append({
            "id": p["id"], "slug": slug_partido(paquete["fecha"], p),
            "titular": (x.get("titular") or "").strip() or f'{es(p["local"])} - {es(p["visitante"])}, previa del partido',
            "entradilla": (x.get("entradilla") or "").strip() or
                          f'Todo lo que hay que saber del {es(p["local"])} - {es(p["visitante"])} de {paquete["liga"]["etiqueta"]}.',
            "parrafos": parrafos,
            "precedente": (x.get("precedente") or "").strip(),
            "el_dato": (x.get("el_dato") or "").strip(),
            "claves": [c for c in x.get("claves", []) if c.get("titulo") and c.get("texto")],
        })
    return salida
