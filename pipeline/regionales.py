"""Regionales: los partidos gordos de cada jornada, enviados por los corresponsales.

Los corresponsales rellenan un formulario de Google (previa o resultado de un partido regional).
Las respuestas van a una hoja de cálculo publicada como CSV (config: regionales.respuestas_csv).
Cada mañana se leen las respuestas nuevas, un modelo barato las pone en limpio SIN AÑADIR datos
y se guardan en contenido/regionales/<slug>.json, que entran en el PR diario para revisarlas.

También se puede añadir un partido a mano creando ese .json (mismos campos).
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import sys
import unicodedata
from datetime import date, datetime

from .web import CONTENIDO, RAIZ

CARPETA = CONTENIDO / "regionales"
VISTAS = RAIZ / "data" / "regionales_vistas.json"

# Columna del formulario → campo. Se busca por palabras del título de la pregunta, así no
# importa que el formulario tenga la pregunta escrita un poco distinta.
COLUMNAS = [
    ("recibido", ("marca temporal", "timestamp")),
    ("tipo", ("previa o resultado", "qué nos mandas", "tipo")),
    ("categoria", ("categoría", "categoria")),
    ("comunidad", ("comunidad", "provincia", "zona")),
    ("local", ("equipo local", "local")),
    ("visitante", ("equipo visitante", "visitante")),
    ("fecha", ("fecha del partido", "fecha")),
    ("hora", ("hora",)),
    ("resultado", ("resultado", "marcador")),
    ("texto", ("por qué", "cuéntanos", "crónica", "cronica", "texto")),
    ("firma", ("firma", "tu nombre", "nombre")),
]


def _slug(txt: str) -> str:
    t = unicodedata.normalize("NFKD", txt).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")[:80]


def _mapear_columnas(cabecera: list[str]) -> dict[str, int]:
    usadas, mapa = set(), {}
    for campo, claves in COLUMNAS:
        for i, titulo in enumerate(cabecera):
            t = titulo.strip().lower()
            if i not in usadas and any(k in t for k in claves):
                mapa[campo] = i
                usadas.add(i)
                break
    return mapa


def leer_respuestas(texto_csv: str) -> list[dict]:
    filas = list(csv.reader(io.StringIO(texto_csv)))
    if not filas:
        return []
    mapa = _mapear_columnas(filas[0])
    out = []
    for f in filas[1:]:
        r = {c: (f[i].strip() if i < len(f) else "") for c, i in mapa.items()}
        if r.get("local") and r.get("visitante"):
            out.append(r)
    return out


def _fecha_iso(txt: str) -> str | None:
    """Google Forms da la fecha como 15/11/2026 (o 2026-11-15)."""
    txt = (txt or "").strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d/%m/%y", "%d-%m-%Y"):
        try:
            return datetime.strptime(txt, fmt).date().isoformat()
        except ValueError:
            pass
    return None


def _marcador(txt: str) -> tuple[int, int] | None:
    m = re.search(r"(\d{1,2})\s*[-–:]\s*(\d{1,2})", txt or "")
    return (int(m.group(1)), int(m.group(2))) if m else None


def _clave(r: dict) -> str:
    base = "|".join(r.get(k, "") for k in ("recibido", "local", "visitante", "fecha"))
    return hashlib.sha1(base.encode()).hexdigest()[:16]


ESQUEMA = {
    "type": "object", "additionalProperties": False,
    "properties": {
        "valida": {"type": "boolean"},
        "motivo": {"type": "string"},
        "titular": {"type": "string"},
        "texto": {"type": "string"},
    },
    "required": ["valida", "motivo", "titular", "texto"],
}

SISTEMA = """Eres redactor de Sin Focos, un periódico de fútbol modesto español. Un corresponsal nos manda un
partido de fútbol regional. Ponlo en limpio para publicarlo.

Reglas:
- Usa SOLO lo que dice el corresponsal. No inventes datos, nombres, goleadores, clasificaciones ni historia.
- valida = false si no es un partido de fútbol real, es una broma, insulta a alguien o no se entiende.
- motivo: 1 a 3 palabras que digan por qué es un partido gordo (p. ej. "Derbi", "Líder contra segundo",
  "Por el ascenso", "Racha", "Con historia"). Si no se sabe, "Partido de la jornada".
- titular: corto y periodístico, con los dos equipos.
- texto: 40 a 120 palabras, en español neutro, tono cercano, sin exagerar. Corrige faltas.
  En una previa, cuenta por qué hay que verlo. En un resultado, cuenta lo que pasó."""


def _redactar(r: dict, tipo: str, rc: dict) -> dict:
    from .noticias import _hay_clave, _llamar
    if not _hay_clave():  # sin clave: se publica tal cual lo manda el corresponsal
        return {"valida": True, "motivo": "Partido de la jornada",
                "titular": f'{r["local"]} - {r["visitante"]}', "texto": r.get("texto", "")}
    datos = "\n".join(f"{k}: {r.get(k, '')}" for k in
                      ("categoria", "comunidad", "local", "visitante", "fecha", "hora", "resultado", "texto"))
    return _llamar(SISTEMA, f"Tipo: {tipo}\n{datos}", ESQUEMA, rc)


def generar_regionales(cfg: dict) -> list[str]:
    rc = cfg.get("regionales") or {}
    url = rc.get("respuestas_csv")
    if not url:
        return []
    import requests

    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    resp.encoding = "utf-8"
    vistas = set(json.loads(VISTAS.read_text())) if VISTAS.exists() else set()
    creados = []
    for r in leer_respuestas(resp.text):
        clave = _clave(r)
        if clave in vistas:
            continue
        vistas.add(clave)
        marcador = _marcador(r.get("resultado", ""))
        tipo = "resultado" if marcador and "previa" not in r.get("tipo", "").lower() else "previa"
        fecha = _fecha_iso(r.get("fecha", "")) or date.today().isoformat()
        try:
            t = _redactar(r, tipo, rc)
        except Exception as e:
            print(f"ERROR redactando regional {r['local']}-{r['visitante']}: {e}", file=sys.stderr)
            vistas.discard(clave)  # se reintenta mañana
            continue
        if not t["valida"]:
            print(f"Descartado (no válido): {r['local']} - {r['visitante']}")
            continue
        s = _slug(f"{fecha}-{tipo}-{r['local']}-{r['visitante']}")
        item = {
            "slug": s, "tipo": tipo, "fecha": fecha, "hora": r.get("hora", "")[:5],
            "categoria": r.get("categoria", ""), "comunidad": r.get("comunidad", ""),
            "local": r["local"], "visitante": r["visitante"],
            "goles_local": marcador[0] if marcador and tipo == "resultado" else None,
            "goles_visitante": marcador[1] if marcador and tipo == "resultado" else None,
            "motivo": t["motivo"], "titular": t["titular"], "texto": t["texto"],
            "firma": r.get("firma", ""), "recibido": r.get("recibido", ""),
        }
        CARPETA.mkdir(parents=True, exist_ok=True)
        (CARPETA / f"{s}.json").write_text(json.dumps(item, ensure_ascii=False, indent=2))
        creados.append(f"regional:{s}")
        print(f"✔ Regional ({tipo}): {t['titular']}")
    VISTAS.parent.mkdir(exist_ok=True)
    VISTAS.write_text(json.dumps(sorted(vistas), indent=0))
    return creados


def cargar() -> list[dict]:
    if not CARPETA.exists():
        return []
    return sorted((json.loads(p.read_text()) for p in CARPETA.glob("*.json")),
                  key=lambda x: (x["fecha"], x.get("hora") or ""))
