"""Noticias del periódico (solo web). Dos tipos:

A · "datos":   salen de nuestros propios resultados guardados (partidos locos, rachas,
                resumen del fin de semana por categoría). No pueden traer datos de fuera.
B · "fuentes": fichajes y cambios de entrenador leídos de RSS de otros medios. Se reescriben
                con nuestras palabras a partir del texto original y siempre se cita y enlaza la fuente.

Se guardan en contenido/noticias/<slug>.json (carpeta aparte: no van a Instagram).
Las redacta un modelo barato (config: noticias.modelo). Sin clave de API se usa una plantilla
solo con datos (tipo A) y el tipo B se salta.
"""
from __future__ import annotations

import hashlib
import html
import json
import os
import re
import sys
import unicodedata
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

from .nombres import es
from .web import CONTENIDO, RAIZ

CARPETA = CONTENIDO / "noticias"
VISTAS = RAIZ / "data" / "noticias_vistas.json"
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36",
      "Accept-Language": "es-ES,es;q=0.9"}


def _slug(txt: str) -> str:
    t = unicodedata.normalize("NFKD", txt).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")[:80]


def _hay_clave() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))


def _guardar(n: dict) -> str:
    CARPETA.mkdir(parents=True, exist_ok=True)
    (CARPETA / f"{n['slug']}.json").write_text(json.dumps(n, ensure_ascii=False, indent=2))
    print(f"✔ Noticia ({n['categoria']}): {n['titular']}")
    return n["slug"]


def _cronicas() -> list[dict]:
    arts = [json.loads(p.read_text()) for p in (CONTENIDO / "articulos").glob("*.json")]
    return sorted((a for a in arts if a.get("tipo") != "previa" and a.get("partidos")), key=lambda a: a["fecha"])


# ───────────────────────── A · noticias a partir de nuestros datos ─────────────────────────

def _goles(p: dict) -> tuple[int, int] | None:
    gl, gv = p.get("goles_local"), p.get("goles_visitante")
    return (gl, gv) if gl is not None and gv is not None else None


def _partido(p: dict, a: dict) -> dict:
    gl, gv = _goles(p)
    return {"fecha": a["fecha"], "competicion": a["etiqueta"], "jornada": p.get("jornada"),
            "local": es(p["local"]), "visitante": es(p["visitante"]), "marcador": f"{gl}-{gv}",
            "estadio": p.get("estadio"),
            "goleadores": [{"min": g.get("min"), "equipo": es(g.get("equipo", "")), "jugador": g.get("jugador"),
                            "tipo": g.get("tipo")} for g in p.get("goleadores") or []]}


def candidatos_partidos_locos(cronicas: list[dict], fecha: str) -> list[dict]:
    """Partidos con 7 o más goles o 5 o más de diferencia."""
    out = []
    for a in cronicas:
        if a["fecha"] != fecha:
            continue
        for p in a["partidos"]:
            g = _goles(p)
            if not g:
                continue
            total, dif = sum(g), abs(g[0] - g[1])
            if total >= 7 or dif >= 5:
                out.append({"clave": f"loco-{p['id']}", "tipo": "partido_loco", "puntos": total + dif + 10,
                            "etiqueta": a["etiqueta"], "competicion": a["competicion"], "grupo": a["grupo"],
                            "datos": {"partido": _partido(p, a), "goles_totales": total, "diferencia": dif,
                                      "otros_partidos_del_grupo_ese_dia": [
                                          f'{es(o["local"])} {o["goles_local"]}-{o["goles_visitante"]} {es(o["visitante"])}'
                                          for o in a["partidos"] if o["id"] != p["id"] and _goles(o)]}})
    return out


def _historial_equipos(cronicas: list[dict]) -> dict[tuple[str, str], list[dict]]:
    """(etiqueta, equipo) → resultados en orden cronológico."""
    h: dict[tuple[str, str], list[dict]] = {}
    for a in cronicas:
        for p in a["partidos"]:
            g = _goles(p)
            if not g:
                continue
            for eq, gf, gc, rival in [(p["local"], g[0], g[1], p["visitante"]), (p["visitante"], g[1], g[0], p["local"])]:
                h.setdefault((a["etiqueta"], eq), []).append(
                    {"fecha": a["fecha"], "rival": es(rival), "marcador": f"{gf}-{gc}",
                     "r": "G" if gf > gc else "E" if gf == gc else "P"})
    return h


RACHAS = [  # (nombre, condición del resultado, mínimo de partidos)
    ("victorias seguidas", lambda r: r == "G", 4),
    ("partidos sin perder", lambda r: r != "P", 6),
    ("partidos sin ganar", lambda r: r != "G", 6),
    ("derrotas seguidas", lambda r: r == "P", 4),
]


def candidatos_rachas(cronicas: list[dict], fecha: str) -> list[dict]:
    """Equipos que ayer alargaron una racha (con los resultados que tenemos guardados)."""
    grupo = {a["etiqueta"]: (a["competicion"], a["grupo"]) for a in cronicas}
    out = []
    for (etiqueta, eq), res in _historial_equipos(cronicas).items():
        if res[-1]["fecha"] != fecha:
            continue
        for nombre, cond, minimo in RACHAS:
            n = 0
            for x in reversed(res):
                if not cond(x["r"]):
                    break
                n += 1
            if n >= minimo:
                out.append({"clave": f"racha-{_slug(etiqueta)}-{_slug(eq)}", "tipo": "racha", "puntos": n * 2,
                            "etiqueta": etiqueta, "competicion": grupo[etiqueta][0], "grupo": grupo[etiqueta][1],
                            "datos": {"equipo": es(eq), "racha": f"{n} {nombre}", "partidos": res[-n:],
                                      "aviso": "La racha cuenta solo los partidos que tenemos registrados."}})
                break  # una racha por equipo (la primera de la lista que cumpla)
    return out


def candidatos_fin_de_semana(cronicas: list[dict], fecha: str, competiciones: list[str]) -> list[dict]:
    """El domingo (resultados de sábado y domingo... y viernes): un resumen por categoría con todos sus grupos."""
    d = date.fromisoformat(fecha)
    if d.weekday() != 6:
        return []
    dias = {(d - timedelta(days=i)).isoformat() for i in range(3)}  # viernes a domingo
    out = []
    for comp in competiciones:
        arts = [a for a in cronicas if a["competicion"] == comp and a["fecha"] in dias]
        partidos = [(p, a) for a in arts for p in a["partidos"] if _goles(p)]
        if len(partidos) < 4:
            continue
        goles = [sum(_goles(p)) for p, _ in partidos]
        por_grupo: dict[str, dict] = {}
        for p, a in partidos:
            gl, gv = _goles(p)
            g = por_grupo.setdefault(a["etiqueta"], {"partidos": 0, "goles": 0})
            g["partidos"] += 1
            g["goles"] += gl + gv
        mas_goles = max(partidos, key=lambda x: sum(_goles(x[0])))
        goleada = max(partidos, key=lambda x: abs(_goles(x[0])[0] - _goles(x[0])[1]))
        out.append({"clave": f"finde-{_slug(comp)}", "tipo": "fin_de_semana", "puntos": 100,
                    "etiqueta": comp, "competicion": comp, "grupo": arts[0]["grupo"],
                    "datos": {"categoria": comp, "dias": sorted(dias), "partidos": len(partidos),
                              "goles": sum(goles), "media_goles": round(sum(goles) / len(partidos), 2),
                              "victorias_local": sum(1 for p, _ in partidos if _goles(p)[0] > _goles(p)[1]),
                              "empates": sum(1 for p, _ in partidos if _goles(p)[0] == _goles(p)[1]),
                              "victorias_visitante": sum(1 for p, _ in partidos if _goles(p)[0] < _goles(p)[1]),
                              "partido_con_mas_goles": _partido(*mas_goles),
                              "mayor_diferencia": _partido(*goleada),
                              "por_grupo": por_grupo}})
    return out


SISTEMA_DATOS = """Eres redactor de un diario digital de fútbol de categorías inferiores. Escribes noticias \
cortas a partir de datos de resultados. Español de España, estilo de agencia, frases cortas.

Normas estrictas:
- Usa EXCLUSIVAMENTE los datos del JSON. Prohibido inventar declaraciones, lesiones, público, clasificación, \
puntos, contexto histórico o cualquier dato que no esté.
- Nombres de equipos y jugadores tal cual vienen.
- Nada de clichés ni relleno ("el balón echa a rodar", "noche mágica", "duelo de alto voltaje"…).
- Nunca digas qué datos faltan ni los menciones ("no constan los goleadores", "se desconoce el estadio"): \
simplemente no hables de ellos. Nada de frases obvias como "el empate deja el reparto de puntos".
- Si hay pocos datos, escribe solo 1-2 párrafos. Mejor corta que hinchada.
- Si vienen "otros_partidos_del_grupo_ese_dia", puedes usarlos para dar contexto (por ejemplo, el total de goles \
del día en el grupo).
- Si el JSON trae un "aviso", respétalo: por ejemplo, di "en los partidos que lleva registrados este diario" \
si la racha puede ser más larga.
- titular: informativo, máx. 90 caracteres, sin exclamaciones ni preguntas.
- entradilla: 1-2 frases con lo esencial y una cifra.
- cuerpo: 2-4 párrafos cortos en Markdown, sin títulos. En un resumen de fin de semana puedes usar una lista \
corta con los datos por grupo."""

ESQUEMA_DATOS = {
    "type": "object",
    "properties": {"titular": {"type": "string"}, "entradilla": {"type": "string"},
                   "cuerpo_markdown": {"type": "string"}},
    "required": ["titular", "entradilla", "cuerpo_markdown"],
    "additionalProperties": False,
}


def _plantilla_datos(c: dict) -> dict:
    d = c["datos"]
    if c["tipo"] == "partido_loco":
        p = d["partido"]
        return {"titular": f'{p["local"]} {p["marcador"]} {p["visitante"]}: {d["goles_totales"]} goles en {c["etiqueta"]}',
                "entradilla": f'El {p["local"]} y el {p["visitante"]} firmaron un {p["marcador"]} con {d["goles_totales"]} goles.',
                "cuerpo_markdown": f'**{p["local"]} {p["marcador"]} {p["visitante"]}** ({c["etiqueta"]}).'}
    if c["tipo"] == "racha":
        return {"titular": f'El {d["equipo"]} suma {d["racha"]}',
                "entradilla": f'El {d["equipo"]} encadena {d["racha"]} en {c["etiqueta"]}.',
                "cuerpo_markdown": "\n".join(f'- {x["fecha"]}: {x["marcador"]} ante {x["rival"]}' for x in d["partidos"])}
    return {"titular": f'{d["categoria"]}: {d["goles"]} goles en {d["partidos"]} partidos este fin de semana',
            "entradilla": f'Media de {d["media_goles"]} goles por partido en {d["categoria"]}.',
            "cuerpo_markdown": "\n".join(f'- **{g}**: {v["partidos"]} partidos, {v["goles"]} goles'
                                         for g, v in d["por_grupo"].items())}


def generar_datos(cfg: dict, fecha: str) -> list[str]:
    nc = cfg["noticias"]
    cronicas = [a for a in _cronicas() if a["competicion"] not in nc.get("excluir", [])]
    finde = candidatos_fin_de_semana(cronicas, fecha, nc.get("resumen_fin_de_semana", []))
    otros = sorted(candidatos_partidos_locos(cronicas, fecha) + candidatos_rachas(cronicas, fecha),
                   key=lambda c: -c["puntos"])[: nc.get("max_datos_dia", 3)]
    creados = []
    for c in finde + otros:
        slug = f"{fecha}-{c['clave']}"[:90]
        if (CARPETA / f"{slug}.json").exists():
            continue
        try:
            texto = (_llamar(SISTEMA_DATOS, "Escribe la noticia. Datos:\n" + json.dumps(c["datos"], ensure_ascii=False),
                             ESQUEMA_DATOS, nc) if _hay_clave() else _plantilla_datos(c))
        except Exception as e:
            print(f"ERROR en la noticia {slug}: {e}", file=sys.stderr)
            continue
        creados.append(_guardar({
            "slug": slug, "tipo": "noticia", "origen": "datos", "fecha": fecha,
            "categoria": {"fin_de_semana": "Fin de semana", "racha": "Rachas"}.get(c["tipo"], "Noticia"),
            "etiqueta": c["etiqueta"], "competicion": c["competicion"], "grupo": c["grupo"],
            **{k: texto[k].strip() for k in ("titular", "entradilla", "cuerpo_markdown")},
        }))
    return creados


# ───────────────────────── B · fichajes y banquillos de otros medios ─────────────────────────

def _texto_limpio(s: str | None) -> str:
    s = re.sub(r"<(script|style)\b.*?</\1>", " ", s or "", flags=re.S | re.I)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


def leer_feed(url: str, nombre: str, sesion) -> list[dict]:
    r = sesion.get(url, headers=UA, timeout=25)
    r.raise_for_status()
    raiz = ET.fromstring(r.content)
    ns = {"atom": "http://www.w3.org/2005/Atom", "content": "http://purl.org/rss/1.0/modules/content/"}
    items = []
    for it in raiz.iter("item"):
        fuente = it.find("source")
        items.append({
            "titulo": _texto_limpio(it.findtext("title")),
            "enlace": (it.findtext("link") or "").strip(),
            "resumen": _texto_limpio(it.findtext("description"))[:600],
            "contenido": _texto_limpio(it.findtext("content:encoded", namespaces=ns)),
            "fecha": it.findtext("pubDate"),
            "medio": (fuente.text.strip() if fuente is not None and fuente.text else nombre),
        })
    for it in raiz.iter("{http://www.w3.org/2005/Atom}entry"):
        link = it.find("atom:link", ns)
        items.append({"titulo": _texto_limpio(it.findtext("atom:title", namespaces=ns)),
                      "enlace": link.get("href", "") if link is not None else "",
                      "resumen": _texto_limpio(it.findtext("atom:summary", namespaces=ns))[:600],
                      "contenido": _texto_limpio(it.findtext("atom:content", namespaces=ns)),
                      "fecha": it.findtext("atom:updated", namespaces=ns), "medio": nombre})
    for x in items:  # Google Noticias pone " - Medio" al final del titular
        if x["medio"] != nombre and x["titulo"].endswith(" - " + x["medio"]):
            x["titulo"] = x["titulo"][: -len(x["medio"]) - 3].strip()
    return items


def _reciente(item: dict, horas: int) -> bool:
    if not item.get("fecha"):
        return True
    try:
        d = parsedate_to_datetime(item["fecha"])
    except (TypeError, ValueError):
        try:
            d = datetime.fromisoformat(item["fecha"].replace("Z", "+00:00"))
        except ValueError:
            return True
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - d < timedelta(hours=horas)


def resolver_google_news(url: str, sesion) -> str | None:
    """Los enlaces de Google Noticias no llevan a la noticia directamente: hay que pedirle a Google la URL real."""
    m = re.search(r"/articles/([^?/]+)", url)
    if not m:
        return None
    ident = m.group(1)
    pagina = sesion.get(f"https://news.google.com/articles/{ident}", headers=UA, timeout=25).text
    sg = re.search(r'data-n-a-sg="([^"]+)"', pagina)
    ts = re.search(r'data-n-a-ts="([^"]+)"', pagina)
    if not (sg and ts):
        return None
    peticion = ["Fbv4je", f'["garturlreq",[["X","X",["X","X"],null,null,1,1,"US:en",null,1,null,null,null,null,null,0,1],'
                          f'"X","X",1,[1,1,1],1,1,null,0,0,null,0],"{ident}",{ts.group(1)},"{sg.group(1)}"]']
    r = sesion.post("https://news.google.com/_/DotsSplashUi/data/batchexecute",
                    headers={**UA, "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"},
                    data={"f.req": json.dumps([[peticion]])}, timeout=25)
    try:
        bloque = json.loads(r.text.split("\n\n", 1)[1])
        destino = json.loads(bloque[0][2])[1]
        return destino if isinstance(destino, str) and destino.startswith("http") else None
    except (IndexError, ValueError, TypeError):
        return None


def fecha_publicacion(pagina: str) -> datetime | None:
    """Fecha de publicación que la propia web declara (meta article:published_time o datePublished)."""
    m = (re.search(r'article:published_time"\s+content="([^"]+)"', pagina)
         or re.search(r'content="([^"]+)"\s+property="article:published_time"', pagina)
         or re.search(r'"datePublished"\s*:\s*"([^"]+)"', pagina))
    if not m:
        return None
    try:
        d = datetime.fromisoformat(m.group(1).strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def texto_articulo(url: str, sesion, horas: int = 72) -> str:
    """Párrafos de la noticia original (solo para que la IA la entienda; nunca se publica tal cual).
    Devuelve "" si la propia web dice que la noticia es de hace más de `horas`."""
    r = sesion.get(url, headers=UA, timeout=25)
    r.raise_for_status()
    publicada = fecha_publicacion(r.text)
    if publicada and datetime.now(timezone.utc) - publicada > timedelta(hours=horas):
        print(f"    antigua ({publicada:%Y-%m-%d}), se descarta")
        return ""
    cuerpo = re.search(r"<article\b.*?</article>", r.text, re.S | re.I)
    parrafos = [_texto_limpio(p) for p in re.findall(r"<p\b[^>]*>(.*?)</p>", cuerpo.group(0) if cuerpo else r.text, re.S | re.I)]
    return "\n".join(p for p in parrafos if len(p) > 60)[:8000]


def _equipos_conocidos(cfg: dict) -> dict[str, str]:
    """Equipo → etiqueta (competición · grupo), de lo que tenemos guardado de las competiciones de España."""
    equipos: dict[str, str] = {}
    for a in _cronicas():
        if a.get("grupo") == "espana":
            for p in a["partidos"]:
                equipos[es(p["local"])] = equipos[es(p["visitante"])] = a["etiqueta"]
    agenda = CONTENIDO / "agenda.json"
    if agenda.exists():
        for dia in json.loads(agenda.read_text()).values():
            for comp in dia:
                if comp.get("grupo") == "espana":
                    for p in comp["partidos"]:
                        equipos.setdefault(es(p["local"]), comp["etiqueta"])
                        equipos.setdefault(es(p["visitante"]), comp["etiqueta"])
    return equipos


SISTEMA_ELEGIR = """Eres el editor de un diario de fútbol de categorías inferiores de España (LaLiga Hypermotion, \
Primera, Segunda y Tercera Federación). Recibes titulares de otros medios y eliges cuáles merecen una noticia \
propia en nuestra sección de mercado y banquillos.

Elige SOLO titulares que cumplan todo esto:
- Tratan de un FICHAJE, una BAJA o RESCISIÓN, una RENOVACIÓN, o un CAMBIO DE ENTRENADOR (destitución, dimisión, \
nuevo técnico) de un club de esas categorías.
- El hecho es OFICIAL o está confirmado en el titular ("nuevo jugador", "ficha", "destituye", "anuncia", \
"es el nuevo entrenador", "rescinde"). Descarta rumores, "suena", "interesa", "podría", "negocia", previas, \
crónicas, declaraciones y opinión.
- No es de Primera División (LaLiga EA Sports) ni de fútbol femenino o base, salvo que el protagonista llegue \
o salga de un club de nuestras categorías.
- El titular anuncia el HECHO en sí: la llegada, la salida, el cese o el nombramiento. Descarta piezas \
sobre el debut o la presentación de alguien ya fichado, ruedas de prensa, previas de partido y declaraciones, \
aunque hablen de un entrenador nuevo.
- Si varios titulares cuentan el mismo hecho, elige solo uno (el del medio más cercano al club).

Para cada elegido indica: id, categoria ("Fichajes" o "Banquillos"), equipo (nombre del club tal como aparece \
en la lista de equipos si está; si no, como en el titular) y etiqueta (la de la lista de equipos, o la \
competición si no está en la lista: "LaLiga Hypermotion", "Primera Federación", "Segunda Federación", \
"Tercera Federación"). Ordénalos de más a menos importante. Si ninguno vale, devuelve la lista vacía."""

ESQUEMA_ELEGIR = {
    "type": "object",
    "properties": {"elegidos": {"type": "array", "items": {
        "type": "object",
        "properties": {"id": {"type": "integer"}, "categoria": {"type": "string", "enum": ["Fichajes", "Banquillos"]},
                       "equipo": {"type": "string"}, "etiqueta": {"type": "string"}},
        "required": ["id", "categoria", "equipo", "etiqueta"], "additionalProperties": False}}},
    "required": ["elegidos"],
    "additionalProperties": False,
}

SISTEMA_REESCRIBIR = """Eres redactor de un diario digital de fútbol de categorías inferiores. Te paso una \
noticia publicada por otro medio. Escribe NUESTRA versión, con tus propias palabras.

Normas estrictas:
- Cuenta solo hechos que estén en el texto original. Prohibido añadir datos, cifras, fechas o contexto que no estén.
- No copies frases del original. Reescribe todo con otra estructura y otras palabras. Si quieres recoger lo que \
dijo alguien, resúmelo en estilo indirecto, sin comillas.
- Si el original solo da el hecho y poco más, escribe una noticia corta (1-2 párrafos). Mejor corta que hinchada.
- Español de España, estilo de agencia, frases cortas, sin clichés ni adjetivos de más.
- titular: informativo, máx. 90 caracteres, sin exclamaciones.
- entradilla: 1-2 frases con el hecho principal.
- parrafos: 1 a 4 párrafos.
- valida: false si el tema principal del texto no es el anuncio en sí (por ejemplo, es la previa del debut \
de un entrenador, una rueda de prensa o declaraciones), o si el texto original no confirma de forma oficial el fichaje o el cambio de entrenador \
(es un rumor, una opinión, o el texto no trata de eso), o si el texto parece de otra temporada. En ese caso el \
resto puede ir vacío.
- competicion y grupo: la categoría y el grupo del club protagonista según el texto ("Grupo II" → 2). \
"otra" si el club no es de esas categorías (en ese caso, valida: false)."""

ESQUEMA_REESCRIBIR = {
    "type": "object",
    "properties": {"valida": {"type": "boolean"}, "titular": {"type": "string"}, "entradilla": {"type": "string"},
                   "parrafos": {"type": "array", "items": {"type": "string"}},
                   "competicion": {"type": "string", "enum": ["LaLiga Hypermotion", "Primera Federación",
                                                             "Segunda Federación", "Tercera Federación", "otra"]},
                   "grupo": {"type": "integer", "description": "Número de grupo si el texto lo dice; 0 si no"}},
    "required": ["valida", "titular", "entradilla", "parrafos", "competicion", "grupo"],
    "additionalProperties": False,
}


def _clave_item(x: dict) -> str:
    return hashlib.sha1(_slug(x["titulo"]).encode()).hexdigest()[:16]


def generar_fuentes(cfg: dict, fecha: str, prueba: bool = False) -> list[str]:
    import requests

    nc = cfg["noticias"]
    if not prueba and not _hay_clave():
        print("Noticias de fuentes: sin clave de Anthropic, se saltan.")
        return []
    sesion = requests.Session()
    vistas = json.loads(VISTAS.read_text()) if VISTAS.exists() else []
    items, titulos = [], set()
    for f in nc.get("fuentes", []):
        try:
            nuevos = leer_feed(f["url"], f["nombre"], sesion)
        except Exception as e:
            print(f"Fuente {f['nombre']} no disponible: {e}", file=sys.stderr)
            continue
        for x in nuevos:
            k = _clave_item(x)
            if x["titulo"] and k not in titulos and k not in vistas and _reciente(x, nc.get("horas", 36)):
                titulos.add(k)
                items.append(x)
    print(f"Noticias de fuentes: {len(items)} titulares nuevos")
    if not items:
        return []
    equipos = _equipos_conocidos(cfg)
    lista = [{"id": i, "titular": x["titulo"], "medio": x["medio"], "resumen": x["resumen"][:250]}
             for i, x in enumerate(items[:150])]
    if prueba:
        for x in lista[:40]:
            print(" ·", x["medio"], "|", x["titular"])
        clave = re.compile(r"nuevo jugador|ficha|entrenador|banquillo|destitu|t[ée]cnico", re.I)
        elegidos = [{"id": x["id"], "categoria": "?", "equipo": "?", "etiqueta": "?"}
                    for x in lista if clave.search(x["titular"])][:6]
    else:
        elegidos = _llamar(SISTEMA_ELEGIR, json.dumps({
            "equipos": [f"{e} ({t})" for e, t in sorted(equipos.items())], "titulares": lista}, ensure_ascii=False),
            ESQUEMA_ELEGIR, nc)["elegidos"]
    print(f"Elegidos: {len(elegidos)}")
    etiquetas = set(equipos.values())
    creados, maximo = [], nc.get("max_fuentes_dia", 3)
    for e in elegidos:
        if len(creados) >= maximo:
            break
        x = items[e["id"]] if 0 <= e["id"] < len(items) else None
        if x is None:
            continue
        vistas.append(_clave_item(x))
        try:
            url = x["enlace"]
            if "news.google.com" in url:
                url = resolver_google_news(url, sesion) or ""
            texto = x["contenido"] if len(x["contenido"]) > 600 else (texto_articulo(url, sesion, nc.get("horas", 36) * 2) if url else "")
        except Exception as err:
            print(f"No se pudo leer «{x['titulo']}»: {err}", file=sys.stderr)
            continue
        print(f"  {x['medio']} | {x['titulo'][:70]} → {url[:80] or 'sin URL'} ({len(texto)} letras)")
        if len(texto) < 300 or not url:
            continue
        if prueba:
            print("    ", texto[:200].replace("\n", " "))
            continue
        try:
            t = _llamar(SISTEMA_REESCRIBIR, json.dumps({"medio": x["medio"], "titular": x["titulo"], "texto": texto},
                                                       ensure_ascii=False), ESQUEMA_REESCRIBIR, nc)
        except Exception as err:
            print(f"ERROR reescribiendo «{x['titulo']}»: {err}", file=sys.stderr)
            continue
        if not t["valida"] or not t["parrafos"]:
            print("  descartada: no confirma un fichaje o cambio de entrenador")
            continue
        # La categoría que dice el texto original manda sobre la que se deduce del titular
        if t["competicion"] == "otra":
            print("  descartada: el club no es de nuestras categorías")
            continue
        con_grupo = f'{t["competicion"]} · Grupo {t["grupo"]}'
        etiqueta = (con_grupo if t["grupo"] and con_grupo in etiquetas else
                    e["etiqueta"] if e["etiqueta"] in etiquetas and e["etiqueta"].startswith(t["competicion"]) else
                    t["competicion"])
        slug = f"{fecha}-{_slug(t['titular'])}"[:90]
        creados.append(_guardar({
            "slug": slug, "tipo": "noticia", "origen": "fuente", "fecha": fecha, "categoria": e["categoria"],
            "etiqueta": etiqueta, "competicion": etiqueta.split(" · ")[0], "grupo": "espana",
            "equipo": e["equipo"], "titular": t["titular"].strip(), "entradilla": t["entradilla"].strip(),
            "cuerpo_markdown": "\n\n".join(p.strip() for p in t["parrafos"]),
            "fuente": {"medio": x["medio"], "url": url, "titular": x["titulo"]},
        }))
    VISTAS.parent.mkdir(exist_ok=True)
    VISTAS.write_text(json.dumps(vistas[-3000:]))
    return creados


# ───────────────────────── común ─────────────────────────

def _llamar(sistema: str, contenido: str, esquema: dict, nc: dict) -> dict:
    import anthropic

    resp = anthropic.Anthropic().messages.create(
        model=nc.get("modelo", "claude-haiku-5-5"), max_tokens=8000, system=sistema,
        output_config={"effort": nc.get("esfuerzo", "low"), "format": {"type": "json_schema", "schema": esquema}},
        messages=[{"role": "user", "content": contenido}])
    if resp.stop_reason in ("refusal", "max_tokens"):
        raise RuntimeError(f"respuesta incompleta ({resp.stop_reason})")
    return json.loads(next(b.text for b in resp.content if b.type == "text"))


def generar_noticias(cfg: dict, fecha: str) -> list[str]:
    nc = cfg.get("noticias") or {}
    if not nc.get("activo"):
        return []
    creados = []
    for paso in (generar_datos, generar_fuentes):
        try:  # las noticias nunca tumban la edición
            creados += paso(cfg, fecha)
        except Exception as e:
            print(f"ERROR en noticias ({paso.__name__}): {e}", file=sys.stderr)
    return creados
