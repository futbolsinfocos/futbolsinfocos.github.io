"""Plan diario de Instagram (4 publicaciones):

  1-2. Partido destacado: los dos mejores resultados del día anterior (portada grande + resto de resultados).
  3.   Previa variada: los partidos más interesantes de hoy, de varias competiciones.
  4.   Horarios: todos los partidos de hoy por competición.

Se guardan en contenido/instagram/<fecha>-<tipo>.json y se publican el mismo día al aprobar la edición.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import yaml

from . import tarjetas
from .web import CONTENIDO, RAIZ

CARPETA = CONTENIDO / "instagram"
PESO_PRIORIDAD = {1: 30, 2: 18, 3: 8}


# ---------- elegir ----------

def _marcadores(p: dict) -> list[tuple[int, int, int]]:
    """Evolución del marcador: [(minuto, goles_local, goles_visitante), …] según los goleadores."""
    gl = gv = 0
    evolucion = []
    for g in sorted(p.get("goleadores", []), key=lambda g: g.get("min") or 0):
        if g.get("equipo") == p["local"]:
            gl += 1
        elif g.get("equipo") == p["visitante"]:
            gv += 1
        evolucion.append((g.get("min") or 0, gl, gv))
    return evolucion


def puntuar(p: dict, prioridad: int) -> float:
    """Cuánto 'interesa' un resultado: categoría, goles, goleada, remontada y gol decisivo al final."""
    gl, gv = p["goles_local"] or 0, p["goles_visitante"] or 0
    puntos = PESO_PRIORIDAD.get(prioridad, 5) + 2 * (gl + gv)
    if abs(gl - gv) >= 3:
        puntos += 6
    if gv > gl:
        puntos += 3  # victoria a domicilio
    ev = _marcadores(p)
    ganador = 1 if gl > gv else 2 if gv > gl else 0
    if ganador and any((l < v if ganador == 1 else v < l) for _, l, v in ev):
        puntos += 10  # remontada
    if ev and ev[-1][0] >= 85 and abs(gl - gv) <= 1:
        puntos += 6  # gol decisivo (victoria o empate) en el tramo final
    return puntos


def elegir_destacados(cronicas: list[dict], cfg: dict, n: int = 2) -> list[tuple[dict, dict]]:
    solo_web = set(cfg.get("solo_web", []))
    candidatos = [(puntuar(p, a.get("prioridad", 3)), a, p) for a in cronicas
                  if a.get("competicion") not in solo_web for p in a.get("partidos", [])]
    candidatos.sort(key=lambda x: -x[0])
    elegidos, usadas = [], set()
    for _, a, p in candidatos:  # primero, competiciones distintas
        if a["competicion"] not in usadas:
            elegidos.append((a, p))
            usadas.add(a["competicion"])
        if len(elegidos) == n:
            return elegidos
    for _, a, p in candidatos:
        if all(p is not q for _, q in elegidos):
            elegidos.append((a, p))
        if len(elegidos) == n:
            break
    return elegidos


def elegir_previa(comps: list[dict], cfg: dict, n: int = 6) -> list[dict]:
    """Los partidos de hoy más atractivos: por categoría, como mucho 2 por competición/grupo."""
    solo_web = set(cfg.get("solo_web", []))
    elegidos = []
    for c in sorted(comps, key=lambda c: c.get("prioridad", 3)):
        if c.get("competicion") in solo_web:
            continue
        for p in sorted(c["partidos"], key=lambda p: p.get("fecha") or "")[:2]:
            elegidos.append({**p, "etiqueta": c["etiqueta"]})
        if len(elegidos) >= n:
            break
    return elegidos[:n]  # agrupados por competición (un rótulo cada una), por hora dentro de cada una


# ---------- textos ----------

def _limpiar(md: str) -> str:
    md = re.sub(r"\*\*(.+?)\*\*", r"\1", md)
    return re.sub(r"\n{3,}", "\n\n", md).strip()


def _seccion_partido(a: dict, p: dict) -> str:
    """El apartado de la crónica dedicado a ese partido ('## Local X-Y Visitante')."""
    for trozo in re.split(r"\n(?=## )", a.get("cuerpo_markdown", "")):
        cab = trozo.split("\n", 1)[0]
        if cab.startswith("## ") and p["local"] in cab and p["visitante"] in cab:
            return _limpiar(trozo.split("\n", 1)[1] if "\n" in trozo else "")
    return a.get("entradilla", "")


def _tags(*nombres: str) -> str:
    out = []
    for n in nombres:
        t = "#" + re.sub(r"[^\wáéíóúñü]", "", n, flags=re.I)
        if len(t) > 2 and t not in out:
            out.append(t)
    return " ".join(out + ["#SinFocos", "#FútbolModesto"])


def _cuentas() -> dict:
    ruta = RAIZ / "instagram_equipos.yaml"
    return (yaml.safe_load(ruta.read_text()) or {}) if ruta.exists() else {}


def etiquetas(*equipos: str, maximo: int = 20) -> str:
    """'@cuenta1 @cuenta2' de los equipos con cuenta conocida (Instagram admite 20 menciones por texto)."""
    cuentas, out = _cuentas(), []
    for e in equipos:
        c = cuentas.get(e)
        if c and f"@{c}" not in out:
            out.append(f"@{c}")
    return " ".join(out[:maximo])


def texto_destacado(a: dict, p: dict) -> str:
    cuerpo = _seccion_partido(a, p)
    if len(cuerpo) > 1100:
        cuerpo = cuerpo[:1100].rsplit("\n", 1)[0]
    cab = f"⚽ {p['local']} {p['goles_local']}-{p['goles_visitante']} {p['visitante']}\n🏆 {a['etiqueta']}"
    menciones = etiquetas(p["local"], p["visitante"])
    pie = (f"📲 {menciones}\n\n" if menciones else "") + _tags(a["competicion"], p["local"], p["visitante"])
    cuerpo = cuerpo[:2200 - len(cab) - len(pie) - 60]
    return f"{cab}\n\n{cuerpo}\n\n📰 Crónica completa: enlace en la bio\n\n{pie}"


def texto_previa(partidos: list[dict], previas: dict) -> str:
    lineas = ["🔥 Los partidos que no te puedes perder hoy\n"]
    for p in partidos:
        lineas.append(f"🕐 {tarjetas._hora(p)} · {p['local']} - {p['visitante']} ({p['etiqueta']})")
        dato = previas.get(p.get("id"))
        if dato:
            lineas.append(f"   {dato}")
    menciones = etiquetas(*[e for p in partidos for e in (p["local"], p["visitante"])])
    lineas.append("\n¿Con cuál te quedas? 👇\n\n📰 Todas las previas: enlace en la bio\n\n"
                  + (f"📲 {menciones}\n\n" if menciones else "") + "#Previa #SinFocos #FútbolModesto")
    return "\n".join(lineas)[:2200]


def texto_horarios(comps: list[dict], fecha: str) -> str:
    total = sum(len(c["partidos"]) for c in comps)
    return (f"🗓️ Horarios de hoy, {tarjetas.dia_semana(fecha)} {tarjetas.fecha_corta(fecha)}: {total} partidos "
            f"en {len(comps)} competiciones.\n\nGuarda la publicación y no te pierdas ninguno 📌\n\n"
            "📰 Todos los partidos, en la web: enlace en la bio\n\n#Horarios #SinFocos #FútbolModesto")


# ---------- generar ----------

def _guardar(post: dict) -> str:
    CARPETA.mkdir(parents=True, exist_ok=True)
    (CARPETA / f"{post['slug']}.json").write_text(json.dumps(post, ensure_ascii=False, indent=2))
    return post["slug"]


def generar_redes(cfg: dict, fecha_resultados: str, hoy: str) -> list[str]:
    cuenta = cfg["medio"]["instagram"]
    carpeta_img = CONTENIDO / "img" / hoy / "instagram"
    arts = [json.loads(x.read_text()) for x in (CONTENIDO / "articulos").glob("*.json")]
    cronicas = [a for a in arts if a.get("tipo") != "previa" and a["fecha"] == fecha_resultados]
    previas_arts = [a for a in arts if a.get("tipo") == "previa" and a["fecha"] == hoy]
    creados = []

    for n, (a, p) in enumerate(elegir_destacados(cronicas, cfg), 1):
        slug = f"{hoy}-destacado-{n}"
        if (CARPETA / f"{slug}.json").exists():
            continue
        portada = tarjetas.tarjeta_destacado(a, p, cuenta, carpeta_img / f"{slug}.jpg")
        resto = [i for i in a.get("imagenes", [])[1:] if "clasificacion" not in i][:3]
        creados.append(_guardar({
            "slug": slug, "tipo": "destacado", "orden": n, "fecha": hoy, "articulo": a["slug"],
            "partido": f"{p['local']} {p['goles_local']}-{p['goles_visitante']} {p['visitante']}",
            "imagenes": [str(portada.relative_to(CONTENIDO))] + resto,
            "texto_instagram": texto_destacado(a, p)}))

    agenda_path = CONTENIDO / "agenda.json"
    agenda = json.loads(agenda_path.read_text()).get(hoy, []) if agenda_path.exists() else []
    if not agenda:  # sin agenda: se reconstruye con las previas del día
        agenda = [{"etiqueta": a["etiqueta"], "competicion": a["competicion"], "prioridad": a["prioridad"], "grupo": a["grupo"],
                   "partidos": a["proximos"]} for a in previas_arts]
    solo_web = set(cfg.get("solo_web", []))
    agenda = [c for c in agenda if c.get("competicion") not in solo_web and c["partidos"]]
    prio = {c["etiqueta"]: c.get("prioridad", 3) for c in cfg.get("competiciones", [])}
    for c in agenda:  # la prioridad manda la de config.yaml actual, no la guardada en la agenda
        c["prioridad"] = prio.get(c.get("competicion"), c.get("prioridad", 3))
    if agenda:
        datos_previa = {pp["id"]: pp.get("entradilla", "") for a in previas_arts
                        for pp in a.get("previas_partido", []) if pp.get("id")}
        slug = f"{hoy}-previa"
        if not (CARPETA / f"{slug}.json").exists():
            sel = elegir_previa(agenda, cfg)
            img = tarjetas.tarjeta_previa_variada(sel, hoy, cuenta, carpeta_img / f"{slug}.jpg")
            creados.append(_guardar({
                "slug": slug, "tipo": "previa", "orden": 3, "fecha": hoy,
                "partidos": [f"{p['local']} - {p['visitante']}" for p in sel],
                "imagenes": [str(img.relative_to(CONTENIDO))], "texto_instagram": texto_previa(sel, datos_previa)}))
        slug = f"{hoy}-horarios"
        if not (CARPETA / f"{slug}.json").exists():
            imgs = tarjetas.tarjetas_horarios(agenda, hoy, cuenta, carpeta_img, slug)
            creados.append(_guardar({
                "slug": slug, "tipo": "horarios", "orden": 4, "fecha": hoy,
                "imagenes": [str(i.relative_to(CONTENIDO)) for i in imgs],
                "texto_instagram": texto_horarios(agenda, hoy)}))
    slug = f"{hoy}-historias"  # una historia por categoría (todos sus grupos juntos), subida manual por ahora
    if cronicas and not (CARPETA / f"{slug}.json").exists():
        categorias: dict[str, list[dict]] = {}
        for a in cronicas:
            if a.get("competicion") in solo_web or not a.get("partidos"):
                continue
            categorias.setdefault(a["etiqueta"].split(" · ")[0], []).append(a)
        orden = lambda kv: (kv[1][0].get("grupo") != "espana", min(a.get("prioridad", 3) for a in kv[1]), kv[0])
        imgs = []
        for cat, arts_cat in sorted(categorias.items(), key=orden):
            base = re.sub(r"[^a-z0-9]+", "-", cat.lower().translate(str.maketrans("áéíóúñü", "aeiounu"))).strip("-")
            imgs += tarjetas.historias_categoria(cat, arts_cat, cuenta, CONTENIDO / "img" / hoy / "historias",
                                                 f"{fecha_resultados}-{base}")
        if imgs:
            creados.append(_guardar({"slug": slug, "tipo": "historias", "orden": 9, "fecha": hoy,
                                     "imagenes": [str(i.relative_to(CONTENIDO)) for i in imgs]}))
    for s in creados:
        print("✔ Instagram:", s)
    return creados
