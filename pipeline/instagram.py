"""Publicación en Instagram vía la API oficial de Meta (Instagram Graph API).

Requisitos: cuenta de Instagram profesional (Empresa o Creador), una app en developers.facebook.com
con permiso `instagram_business_content_publish` (o `instagram_content_publish`), y un token de larga
duración. Las imágenes deben estar en una URL pública: usamos la propia web.
"""
from __future__ import annotations

import json
import os
import time
from datetime import date

import requests

from .web import CONTENIDO

VERSION = os.environ.get("GRAPH_API_VERSION", "v23.0")
HOST = os.environ.get("GRAPH_API_HOST", "graph.instagram.com")  # o graph.facebook.com si usas login de Facebook


class Instagram:
    def __init__(self):
        self.usuario = os.environ["IG_USER_ID"]
        self.token = os.environ["IG_ACCESS_TOKEN"]
        self.base = f"https://{HOST}/{VERSION}"

    def _post(self, ruta: str, **datos) -> dict:
        r = requests.post(f"{self.base}/{ruta}", data={**datos, "access_token": self.token}, timeout=60)
        if r.status_code >= 400:
            raise RuntimeError(f"Instagram {ruta}: {r.status_code} {r.text}")
        return r.json()

    def _esperar(self, contenedor: str):
        for _ in range(30):
            r = requests.get(f"{self.base}/{contenedor}",
                             params={"fields": "status_code", "access_token": self.token}, timeout=30).json()
            if r.get("status_code") == "FINISHED":
                return
            if r.get("status_code") == "ERROR":
                raise RuntimeError(f"Contenedor {contenedor} con error: {r}")
            time.sleep(5)
        raise TimeoutError(f"Contenedor {contenedor} no terminó de procesarse")

    def publicar(self, urls: list[str], texto: str) -> str:
        if len(urls) == 1:
            c = self._post(f"{self.usuario}/media", image_url=urls[0], caption=texto)["id"]
        else:
            hijos = [self._post(f"{self.usuario}/media", image_url=u, is_carousel_item="true")["id"] for u in urls]
            for h in hijos:
                self._esperar(h)
            c = self._post(f"{self.usuario}/media", media_type="CAROUSEL",
                           children=",".join(hijos), caption=texto)["id"]
        self._esperar(c)
        return self._post(f"{self.usuario}/media_publish", creation_id=c)["id"]


class Make:
    """Alternativa sin app de Meta: manda el post a un escenario de Make.com (webhook) que publica en Instagram.
    El escenario recibe {"texto", "imagenes": [{"url", "tipo"}]} y usa el módulo de carrusel de Instagram."""

    def __init__(self, url: str):
        self.url = url

    def publicar(self, urls: list[str], texto: str) -> str:
        r = requests.post(self.url, json={"texto": texto, "imagenes": [{"url": u, "tipo": "IMAGE"} for u in urls]},
                          timeout=60)
        if r.status_code >= 400:
            raise RuntimeError(f"Make: {r.status_code} {r.text}")
        return f"make-{int(time.time())}"


def prueba_make(cfg: dict) -> None:
    """Manda un post de ejemplo al webhook de Make para que aprenda el formato de los datos."""
    base = cfg["medio"]["url_web"].rstrip("/")
    a = json.loads((CONTENIDO / "articulos" / "2026-11-12-copa-del-rey.json").read_text())
    Make(os.environ["MAKE_WEBHOOK_URL"]).publicar([f"{base}/{i}" for i in a["imagenes"]], "PRUEBA · " + a["titular"])
    print("Enviado el post de prueba a Make")


def texto_post(a: dict, cfg: dict) -> str:
    etiquetas = " ".join("#" + h.lstrip("#").replace(" ", "") for h in a.get("hashtags", [])[:8])
    que = "Previa" if a.get("tipo") == "previa" else "Crónica"
    return f"{a['texto_instagram']}\n\n📰 {que} completa: enlace en la bio\n\n{etiquetas}"[:2200]


def publicar_pendientes(cfg: dict, simular: bool = False) -> list[str]:
    """Publica los artículos aún no subidos a Instagram, por prioridad, respetando el límite diario."""
    base = cfg["medio"]["url_web"].rstrip("/")
    archivos = sorted((CONTENIDO / "articulos").glob("*.json"))
    arts = [(p, json.loads(p.read_text())) for p in archivos]
    hoy = date.today().isoformat()
    ya_hoy = sum(1 for _, a in arts if a.get("ig_publicado_en", "")[:10] == hoy)
    # las previas solo valen el mismo día del partido: una previa atrasada no se publica
    pendientes = sorted([x for x in arts if not x[1].get("ig_media_id") and x[1].get("imagenes")
                         and (x[1].get("tipo") != "previa" or x[1]["fecha"] == hoy)],
                        key=lambda x: (x[1].get("prioridad", 3), x[1]["fecha"]))
    hueco = max(cfg["limites"]["max_posts_instagram_dia"] - ya_hoy, 0)
    make = os.environ.get("MAKE_WEBHOOK_URL")
    ig = None if simular else (Make(make) if make else Instagram())
    hechos = []
    for ruta, a in pendientes[:hueco]:
        urls = [f"{base}/{img}" for img in a["imagenes"]]
        if len(urls) == 1:  # Make solo publica carruseles: se añade la imagen de cierre de la marca
            urls.append(f"{base}/img/cierre.jpg")
        if simular:
            print(f"[simulación] Publicaría {a['slug']} con {len(urls)} imagen(es)")
            continue
        a["ig_media_id"] = ig.publicar(urls, texto_post(a, cfg))
        a["ig_publicado_en"] = hoy
        ruta.write_text(json.dumps(a, ensure_ascii=False, indent=2))
        hechos.append(a["slug"])
    return hechos
