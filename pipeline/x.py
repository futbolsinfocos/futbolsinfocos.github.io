"""Publicación en X (Twitter) con la API oficial, de pago por uso.

Cada post cuesta poco (unos 0,015 $), pero un post CON ENLACE cuesta bastante más (0,20 $). Por eso:
  · Resultados: un post por competición con las imágenes de la edición y SIN enlace
    ("crónicas: enlace en el perfil"). Las competiciones con muchos grupos (Segunda y Tercera
    Federación) van de 4 en 4 grupos por post, nunca mezcladas con otras competiciones.
  · Enlace: UN post al día con la crónica más destacada y su enlace a la web.
  · Previas: los días de `x.previas_dias` (por defecto el viernes), con imagen y sin enlace.

Claves (secretos del repositorio): X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_SECRET.
Lo publicado se marca en el propio artículo (x_post_id / x_enlace_id) para no repetirlo.
"""
from __future__ import annotations

import json
import os
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import requests
from requests_oauthlib import OAuth1

from .redes import puntuar
from .web import CONTENIDO

API = "https://api.x.com/2"
MAX_TEXTO = 270          # X permite 280 «caracteres» (los emojis cuentan doble): dejamos margen
MAX_IMAGENES = 4         # X admite como mucho 4 imágenes por post


class SinSaldo(RuntimeError):
    pass


class X:
    def __init__(self):
        self.auth = OAuth1(os.environ["X_API_KEY"], os.environ["X_API_SECRET"],
                           os.environ["X_ACCESS_TOKEN"], os.environ["X_ACCESS_SECRET"])

    def _revisar(self, r: requests.Response, que: str) -> dict:
        if r.status_code == 402:
            raise SinSaldo("X: no queda saldo en la cuenta de desarrollador (console.x.com › Billing)")
        if r.status_code >= 400:
            raise RuntimeError(f"X {que}: {r.status_code} {r.text[:500]}")
        return r.json()

    def subir_imagen(self, ruta) -> str:
        with open(ruta, "rb") as f:
            r = requests.post(f"{API}/media/upload", auth=self.auth, timeout=120,
                              files={"media": (os.path.basename(ruta), f, "image/jpeg")},
                              data={"media_category": "tweet_image"})
        d = self._revisar(r, "subir imagen")
        return str(d.get("data", d).get("id") or d.get("media_id_string"))

    def publicar(self, texto: str, imagenes: list = ()) -> str:
        cuerpo = {"text": texto}
        if imagenes:
            cuerpo["media"] = {"media_ids": [self.subir_imagen(i) for i in imagenes[:MAX_IMAGENES]]}
        r = requests.post(f"{API}/tweets", auth=self.auth, json=cuerpo, timeout=60)
        return str(self._revisar(r, "publicar")["data"]["id"])


# ---------- textos ----------

def _hashtags(arts: list[dict], n: int = 2) -> str:
    tags = []
    for a in arts:
        for h in a.get("hashtags", []):
            h = "#" + h.lstrip("#").replace(" ", "")
            if h not in tags:
                tags.append(h)
    return " ".join(tags[:n])


def _recortar(lineas: list[str], cierre: str) -> str:
    """Junta las líneas que quepan en un post, dejando siempre el cierre."""
    texto = ""
    for l in lineas:
        prueba = f"{texto}\n{l}" if texto else l
        if len(prueba) + len(cierre) + 2 > MAX_TEXTO:
            texto += "\n…"
            break
        texto = prueba
    return f"{texto}\n\n{cierre}"


def texto_resultados(arts: list[dict], cfg: dict) -> str:
    # en los posts de varios grupos, solo la etiqueta de la competición (no la de un grupo suelto)
    cierre = f"📰 Crónicas: enlace en el perfil\n{_hashtags(arts, 2 if len(arts) == 1 else 1)}".strip()
    if len(arts) == 1:
        a = arts[0]
        lineas = [f"⚽ {a['etiqueta']} · Resultados", ""]
        lineas += [f"{p['local']} {p['goles_local']}-{p['goles_visitante']} {p['visitante']}"
                   for p in a.get("partidos", []) if p.get("goles_local") is not None]
        if len(lineas) == 2:  # sin marcadores: el titular
            lineas.append(a["titular"])
        return _recortar(lineas, cierre)
    grupos = [a["etiqueta"].split("·")[-1].strip().replace("Grupo ", "") for a in arts]
    lista = ", ".join(grupos[:-1]) + f" y {grupos[-1]}"
    return _recortar([f"⚽ {arts[0]['competicion']} · Resultados", "", f"Grupos {lista} en las imágenes 👇"], cierre)


def texto_previa(a: dict) -> str:
    return _recortar([f"🔜 Hoy · {a['etiqueta']}", "", a["titular"]],
                     f"📰 Previa completa: enlace en el perfil\n{_hashtags([a])}".strip())


def texto_enlace(a: dict, cfg: dict) -> str:
    url = f"{cfg['medio']['url_web'].rstrip('/')}/articulos/{a['slug']}.html"
    # el enlace cuenta como 23 caracteres, sea cual sea su longitud
    hueco = MAX_TEXTO - 23 - 4 - len(_hashtags([a])) - 4
    titular = a["titular"] if len(a["titular"]) <= hueco else a["titular"][:hueco].rsplit(" ", 1)[0] + "…"
    return f"📰 {titular}\n\n{_hashtags([a])}\n\n{url}".replace("\n\n\n\n", "\n\n")


# ---------- qué publicar ----------

def _imagenes(a: dict, n: int) -> list:
    return [CONTENIDO / i for i in a.get("imagenes", []) if (CONTENIDO / i).exists()][:n]


def _lotes_resultados(arts: list[dict], cfg: dict) -> list[list[dict]]:
    """Un post por competición; las de `agrupar_instagram` van de 4 en 4 grupos."""
    agrupar = set(cfg.get("agrupar_instagram", []))
    sueltos, por_comp = [], {}
    for a in arts:
        if a.get("competicion") in agrupar:
            por_comp.setdefault((a["fecha"], a["competicion"]), []).append(a)
        else:
            sueltos.append([a])
    lotes = list(sueltos)
    for grupo in por_comp.values():
        grupo.sort(key=lambda a: int("".join(c for c in a["etiqueta"].split("·")[-1] if c.isdigit()) or 0))
        lotes += [grupo[i:i + MAX_IMAGENES] for i in range(0, len(grupo), MAX_IMAGENES)]
    return sorted(lotes, key=lambda l: (l[0].get("prioridad", 3), l[0]["fecha"]))


def _interes(a: dict) -> float:
    return max((puntuar(p, a.get("prioridad", 3)) for p in a.get("partidos", [])
                if p.get("goles_local") is not None), default=0)


def publicar_pendientes(cfg: dict, simular: bool = False) -> list[str]:
    xc = cfg.get("x", {})
    if not xc.get("activo", True) and not simular:
        print("X desactivado en config.yaml (x: activo: false); no se publica nada.")
        return []
    hoy_d = datetime.now(ZoneInfo(cfg["medio"].get("zona_horaria", "Europe/Madrid"))).date()
    hoy = hoy_d.isoformat()
    desde = max((hoy_d - timedelta(days=2)).isoformat(), str(xc.get("desde", "")))
    rutas = sorted((CONTENIDO / "articulos").glob("*.json"))
    todos = [(p, json.loads(p.read_text())) for p in rutas]
    por_slug = {a["slug"]: p for p, a in todos}
    solo_web = set(cfg.get("solo_web", []))

    def guardar(a: dict):
        por_slug[a["slug"]].write_text(json.dumps(a, ensure_ascii=False, indent=2))

    ya_hoy = len({a.get("x_post_id") for _, a in todos if a.get("x_publicado_en") == hoy})
    hueco = max(int(xc.get("max_posts_dia", 15)) - ya_hoy, 0)
    validos = [a for _, a in todos if a.get("competicion") not in solo_web and not a.get("x_omitir")]
    # crónicas de días ya cerrados (no las de hoy, que aún pueden ir a medias)
    cronicas = [a for a in validos if a.get("tipo") != "previa" and desde <= a["fecha"] < hoy]
    previas = [a for a in validos if a.get("tipo") == "previa" and a["fecha"] == hoy
               and hoy_d.weekday() in xc.get("previas_dias", [4])]

    tareas = []  # (tipo, artículos, texto, imágenes)
    enlace_hecho = any(a.get("x_enlace_en") == hoy for _, a in todos)
    candidatos = [a for a in cronicas if not a.get("x_enlace_id") and _interes(a) > 0]
    if xc.get("enlace_diario", True) and not enlace_hecho and candidatos:
        mejor = max(candidatos, key=lambda a: (a["fecha"], _interes(a)))
        tareas.append(("enlace", [mejor], texto_enlace(mejor, cfg), []))
    for lote in _lotes_resultados([a for a in cronicas if not a.get("x_post_id")], cfg):
        imgs = [i for a in lote for i in _imagenes(a, 1 if len(lote) > 1 else MAX_IMAGENES)]
        tareas.append(("post", lote, texto_resultados(lote, cfg), imgs))
    for a in sorted((a for a in previas if not a.get("x_post_id")), key=lambda a: a.get("prioridad", 3)):
        tareas.append(("post", [a], texto_previa(a), _imagenes(a, MAX_IMAGENES)))

    cliente = None if simular else X()
    hechos = []
    for tipo, lote, texto, imgs in tareas:
        if tipo == "post" and hueco <= 0:
            print("Límite diario de posts en X alcanzado; el resto sale en la próxima pasada.")
            break
        slugs = " + ".join(a["slug"] for a in lote)
        if simular:
            print(f"\n[simulación] {tipo} · {slugs} · {len(imgs)} imagen(es)\n{texto}")
            continue
        try:
            pid = cliente.publicar(texto, imgs)
        except SinSaldo as e:
            print(e)
            break
        for a in lote:
            if tipo == "enlace":
                a["x_enlace_id"], a["x_enlace_en"] = pid, hoy
            else:
                a["x_post_id"], a["x_publicado_en"] = pid, hoy
            guardar(a)
        hueco -= tipo == "post"
        hechos.append(f"{tipo}:{slugs}")
    return hechos
