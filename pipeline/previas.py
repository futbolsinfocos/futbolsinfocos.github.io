"""Piezas fijas de las previas: jornada en español, historial entre equipos y la ficha de cada partido.

La IA solo escribe el análisis; los datos (hora, estadio, árbitro, forma) los pone el código,
así salen siempre igual de ordenados y no hay relleno cuando faltan datos.
"""
from __future__ import annotations

import html
import re
import unicodedata
from datetime import date

from .nombres import es

DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre",
         "octubre", "noviembre", "diciembre"]


def slug_partido(fecha: str, p: dict) -> str:
    """Nombre de la página de la previa de un partido: '2026-11-14-racing-de-santander-real-zaragoza'."""
    t = unicodedata.normalize("NFKD", f'{fecha}-{es(p["local"])}-{es(p["visitante"])}').encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")[:90]


def dia_partido(iso: str | None) -> str:
    """'2026-11-14T21:00:00+01:00' → 'sábado 14 de noviembre'."""
    if not iso:
        return ""
    d = date.fromisoformat(iso[:10])
    return f"{DIAS[d.weekday()]} {d.day} de {MESES[d.month - 1]}"


def entrada_basica(p: dict, competicion: str) -> str:
    """Primer párrafo solo con datos (para cuando no hay texto de la IA): quién, cuándo, dónde y qué."""
    t = f'El {es(p["local"])} recibe al {es(p["visitante"])}'
    if p.get("fecha"):
        t += f' este {dia_partido(p["fecha"])} a las {p["fecha"][11:16]}'
    if p.get("estadio"):
        t += f' en {p["estadio"]}'
    j = jornada_es(p.get("jornada"))
    if j.startswith("Jornada"):
        t += f", en la {j.lower()} de {competicion}"
    elif j:
        t += f" ({j.lower()} de {competicion})"
    else:
        t += f", en partido de {competicion}"
    return t + "."


def jornada_es(txt: str | None) -> str:
    """'Regular Season - 14' → 'Jornada 14'; 'League A - 5' → 'Liga A · Jornada 5';
    'Group 15 - 11' → 'Jornada 11'; 'Round of 128' → 'Ronda de 128'."""
    if not txt:
        return ""
    t = txt.strip()
    m = re.match(r"^(Regular Season|Group \w+|Girone \w+|Apertura|Clausura)\s*-\s*(\d+)$", t)
    if m:
        return f"Jornada {m.group(2)}"
    m = re.match(r"^League ([A-D])\s*-\s*(\d+)$", t)
    if m:
        return f"Liga {m.group(1)} · Jornada {m.group(2)}"
    fijas = {"Final": "Final", "Semi-finals": "Semifinales", "Quarter-finals": "Cuartos de final",
             "Round of 16": "Octavos de final", "Round of 32": "Dieciseisavos de final",
             "Play-offs": "Eliminatoria", "Relegation Round": "Fase de descenso"}
    if t in fijas:
        return fijas[t]
    m = re.match(r"^Round of (\d+)$", t)
    if m:
        return f"Ronda de {m.group(1)}"
    m = re.match(r"^(\d+)(st|nd|rd|th) Round$", t)
    if m:
        return f"Ronda {m.group(1)}"
    return t


def historial(articulos: list[dict], local: str, visitante: str, n: int = 3) -> list[dict]:
    """Últimos enfrentamientos entre los dos equipos que tenemos publicados (más reciente primero)."""
    par = {local, visitante}
    salida = []
    for a in sorted(articulos, key=lambda a: a["fecha"], reverse=True):
        for p in a.get("partidos", []):
            if {p["local"], p["visitante"]} == par and p.get("goles_local") is not None:
                salida.append({"fecha": a["fecha"], "competicion": a["etiqueta"],
                               "resultado": f'{p["local"]} {p["goles_local"]}-{p["goles_visitante"]} {p["visitante"]}'})
                if len(salida) >= n:
                    return salida
    return salida


def _forma_html(forma: list[dict]) -> str:
    # Más antiguo a la izquierda, como en las tablas de clasificación
    return "".join(f'<span class="f{r["resultado"]}" title="{html.escape(r["marcador"] + " vs " + r["rival"])}">'
                   f'{r["resultado"]}</span>' for r in reversed(forma))


def ficha(p: dict, forma: dict) -> str:
    """Línea de datos fija bajo el título de cada partido (HTML dentro del markdown)."""
    datos = [f'<b>{html.escape(p["fecha"][11:16])}</b>'] if p.get("fecha") else []
    sede = p.get("estadio") or ""
    if p.get("ciudad") and p["ciudad"] not in sede:
        sede = f'{sede} ({p["ciudad"]})' if sede else p["ciudad"]
    if sede:
        datos.append(html.escape(sede))
    if p.get("jornada"):
        datos.append(html.escape(jornada_es(p["jornada"])))
    if p.get("arbitro"):
        datos.append("Árbitro: " + html.escape(re.sub(r",.*$", "", p["arbitro"])))
    out = f'<p class="ficha">{" · ".join(datos)}</p>'
    filas = [f'<span class="eq">{html.escape(es(e))}</span>{_forma_html(forma[e])}'
             for e in (p["local"], p["visitante"]) if forma.get(e)]
    if filas:
        out += '<p class="forma">' + "<br>".join(filas) + "</p>"
    return out


def cuerpo(paq: dict, texto: dict) -> str:
    """Monta el artículo de la jornada: presentación, claves y un apartado por partido con su ficha,
    la entradilla de su previa y el enlace a la previa completa (página propia de cada partido)."""
    analisis = {x["id"]: (x.get("entradilla") or x.get("texto") or "").strip() for x in texto.get("partidos", [])}
    partes = [texto.get("presentacion", "").strip()]
    claves = [c.strip() for c in texto.get("claves", []) if c.strip()]
    if claves:
        partes.append("## Claves de la jornada\n\n" + "\n".join(f"- {c}" for c in claves))
    for p in paq["partidos"]:
        bloque = f'## {es(p["local"])} - {es(p["visitante"])}\n\n{ficha(p, paq.get("forma", {}))}'
        if analisis.get(p["id"]):
            bloque += "\n\n" + analisis[p["id"]]
        bloque += f'\n\n[Leer la previa completa →](../previas/{slug_partido(paq["fecha"], p)}.html)'
        partes.append(bloque)
    return "\n\n".join(x for x in partes if x)
