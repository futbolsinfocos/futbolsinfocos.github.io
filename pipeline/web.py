"""Generador de la web estática (periódico). Lee contenido/articulos/*.json y escribe _site/.

Web estática = gratis de alojar (GitHub Pages / Cloudflare Pages), rapidísima y sin
mantenimiento ni actualizaciones de seguridad como un WordPress.
"""
from __future__ import annotations

import html
import json
import shutil
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path

import markdown

from .tarjetas import fecha_larga

RAIZ = Path(__file__).resolve().parent.parent
CONTENIDO = RAIZ / "contenido"
SALIDA = RAIZ / "_site"

CSS = """
:root{--fondo:#faf8f2;--tinta:#111;--suave:#5f5f5f;--acento:#9a7400;--linea:#e2ded2;--tarjeta:#fff}
@media (prefers-color-scheme:dark){:root{--fondo:#111;--tinta:#f5f5f5;--suave:#a0a0a0;--acento:#FFD400;--linea:#2a2a2a;--tarjeta:#1a1a1a}}
*{box-sizing:border-box}body{margin:0;background:var(--fondo);color:var(--tinta);font:17px/1.6 Georgia,'Times New Roman',serif}
a{color:inherit}header{border-top:8px solid #FFD400;border-bottom:3px solid var(--tinta);padding:18px 16px 10px;text-align:center}
header .marca{font:800 clamp(30px,6vw,52px)/1.05 system-ui,sans-serif;letter-spacing:-.02em;text-decoration:none}
header .lema{color:var(--suave);font-style:italic;margin:4px 0 10px}
nav{display:flex;gap:18px;justify-content:center;font:600 14px system-ui,sans-serif;text-transform:uppercase;letter-spacing:.06em}
nav a{text-decoration:none}nav a:hover{color:var(--acento)}
main{max-width:1080px;margin:0 auto;padding:24px 16px 60px}
.rejilla{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:22px}
.pieza{background:var(--tarjeta);border:1px solid var(--linea);border-radius:6px;overflow:hidden}
.pieza img{width:100%;aspect-ratio:4/5;object-fit:cover;display:block}
.pieza div{padding:14px 16px 18px}.pieza h2{font-size:21px;line-height:1.25;margin:4px 0 8px}
.pieza a{text-decoration:none}.cat{font:700 12px system-ui,sans-serif;color:var(--acento);text-transform:uppercase;letter-spacing:.08em}
.fecha{font:13px system-ui,sans-serif;color:var(--suave)}
article{max-width:720px;margin:0 auto}article h1{font-size:clamp(28px,5vw,42px);line-height:1.15;margin:8px 0 12px}
article .entradilla{font-size:20px;color:var(--suave);margin:0 0 20px}article img{width:100%;max-width:540px;border-radius:6px;display:block;margin:20px auto}
article h2{font:700 20px system-ui,sans-serif;margin-top:32px}
table{border-collapse:collapse;width:100%;font:15px system-ui,sans-serif}td,th{border-bottom:1px solid var(--linea);padding:6px 8px;text-align:left}
footer{border-top:1px solid var(--linea);color:var(--suave);font:13px system-ui,sans-serif;text-align:center;padding:24px 16px}
"""


def _pagina(cfg: dict, titulo: str, cuerpo: str, prof: str = "", descripcion: str = "") -> str:
    m = cfg["medio"]
    return f"""<!doctype html><html lang="{m['idioma']}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(titulo)}</title><meta name="description" content="{html.escape(descripcion or m['lema'])}">
<link rel="alternate" type="application/rss+xml" href="{prof}rss.xml"><style>{CSS}</style></head><body>
<header><a class="marca" href="{prof}index.html">{html.escape(m['nombre'])}</a><p class="lema">{html.escape(m['lema'])}</p>
<nav><a href="{prof}index.html">Portada</a><a href="{prof}espana.html">España</a><a href="{prof}internacional.html">Internacional</a></nav></header>
<main>{cuerpo}</main>
<footer>Datos de resultados y clasificaciones: API-Football. Crónicas elaboradas automáticamente a partir de esos datos y revisadas por la redacción.<br>
¿Ves un error? Escríbenos y lo corregimos.</footer></body></html>"""


def cargar_articulos() -> list[dict]:
    arts = [json.loads(p.read_text()) for p in (CONTENIDO / "articulos").glob("*.json")]
    return sorted(arts, key=lambda a: (a["fecha"], -a.get("prioridad", 3)), reverse=True)


def _tarjeta(a: dict, prof: str = "") -> str:
    img = f'<img src="{prof}{a["imagenes"][0]}" alt="" loading="lazy">' if a.get("imagenes") else ""
    return (f'<section class="pieza"><a href="{prof}articulos/{a["slug"]}.html">{img}<div>'
            f'<span class="cat">{html.escape(a["etiqueta"])}</span><h2>{html.escape(a["titular"])}</h2>'
            f'<span class="fecha">{fecha_larga(a["fecha"])}</span></div></a></section>')


def construir(cfg: dict) -> Path:
    arts = cargar_articulos()
    if SALIDA.exists():
        shutil.rmtree(SALIDA)
    (SALIDA / "articulos").mkdir(parents=True)
    if (CONTENIDO / "img").exists():
        shutil.copytree(CONTENIDO / "img", SALIDA / "img")
    nombre = cfg["medio"]["nombre"]

    for archivo, filtro, titulo in [("index.html", None, nombre),
                                    ("espana.html", "espana", f"España · {nombre}"),
                                    ("internacional.html", "internacional", f"Internacional · {nombre}")]:
        lista = [a for a in arts if filtro is None or a["grupo"] == filtro][:60]
        cuerpo = '<div class="rejilla">' + "".join(_tarjeta(a) for a in lista) + "</div>" if lista else "<p>Aún no hay noticias.</p>"
        (SALIDA / archivo).write_text(_pagina(cfg, titulo, cuerpo))

    for a in arts:
        img = f'<img src="../{a["imagenes"][0]}" alt="Resultados de {html.escape(a["etiqueta"])}">' if a.get("imagenes") else ""
        cuerpo = (f'<article><span class="cat">{html.escape(a["etiqueta"])}</span><h1>{html.escape(a["titular"])}</h1>'
                  f'<p class="fecha">{fecha_larga(a["fecha"])}</p><p class="entradilla">{html.escape(a["entradilla"])}</p>{img}'
                  + markdown.markdown(a["cuerpo_markdown"], extensions=["tables"]) + "</article>")
        (SALIDA / "articulos" / f"{a['slug']}.html").write_text(
            _pagina(cfg, f"{a['titular']} · {nombre}", cuerpo, "../", a["entradilla"]))

    _rss(cfg, arts[:40])
    (SALIDA / ".nojekyll").write_text("")
    return SALIDA


def _rss(cfg: dict, arts: list[dict]):
    base = cfg["medio"]["url_web"].rstrip("/")
    items = "".join(
        f"<item><title>{html.escape(a['titular'])}</title><link>{base}/articulos/{a['slug']}.html</link>"
        f"<guid>{base}/articulos/{a['slug']}.html</guid><description>{html.escape(a['entradilla'])}</description>"
        f"<pubDate>{format_datetime(datetime.fromisoformat(a['fecha']).replace(tzinfo=timezone.utc))}</pubDate></item>"
        for a in arts)
    (SALIDA / "rss.xml").write_text(
        f'<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>{html.escape(cfg["medio"]["nombre"])}</title>'
        f"<link>{base}</link><description>{html.escape(cfg['medio']['lema'])}</description>{items}</channel></rss>")
