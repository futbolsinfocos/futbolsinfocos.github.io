"""Generador de la web estática (periódico). Lee contenido/articulos/*.json y escribe _site/.

Web estática = gratis de alojar (GitHub Pages / Cloudflare Pages), rapidísima y sin
mantenimiento ni actualizaciones de seguridad como un WordPress.
"""
from __future__ import annotations

import html
import re
import unicodedata
import json
import shutil
import zipfile
from datetime import date, datetime, timedelta, timezone
from email.utils import format_datetime
from pathlib import Path

import markdown

from urllib.parse import quote

from .nombres import es
from .previas import dia_partido, jornada_es
from .tarjetas import fecha_larga

RAIZ = Path(__file__).resolve().parent.parent
CONTENIDO = RAIZ / "contenido"
SALIDA = RAIZ / "_site"

FUENTES = ('<link rel="preconnect" href="https://fonts.googleapis.com">'
           '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
           '<link href="https://fonts.googleapis.com/css2?family=Oswald:wght@500;600;700'
           '&family=Inter:wght@400;600;700&family=Source+Serif+4:wght@400;600&display=swap" rel="stylesheet">')

CSS = """
:root{--fondo:#0d0d0d;--panel:#181818;--linea:#2a2a2a;--tinta:#f2f2f2;--suave:#a8a8a8;--amarillo:#FFD400;--negro:#111}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--fondo);color:var(--tinta);font:16px/1.55 Inter,system-ui,sans-serif}
a{color:inherit;text-decoration:none}img{display:block;max-width:100%}
.tit{font-family:Oswald,'Arial Narrow',Impact,sans-serif;text-transform:uppercase;letter-spacing:.01em}
.ticker{background:var(--amarillo);color:var(--negro);overflow:hidden;white-space:nowrap}
.ticker .in{display:inline-flex;width:max-content;animation:rueda var(--dur,40s) linear infinite}
.ticker:hover .in,.ticker:focus-within .in{animation-play-state:paused}
.ticker .tira{display:inline-flex;gap:26px;padding:8px 13px;font:700 14px Inter,sans-serif}
.ticker .tira>a{display:inline-flex;align-items:center}
@keyframes rueda{from{transform:translateX(0)}to{transform:translateX(-50%)}}
@media (prefers-reduced-motion:reduce){.ticker{overflow-x:auto}.ticker .in{animation:none}.ticker .tira[aria-hidden]{display:none}}
.ticker b{background:var(--negro);color:var(--amarillo);padding:1px 7px;border-radius:3px;margin:0 7px;font-variant-numeric:tabular-nums}
.ticker .lt{font-size:11px;text-transform:uppercase;letter-spacing:.08em;opacity:.7}
header{display:flex;align-items:center;gap:14px;max-width:1180px;margin:0 auto;padding:16px}
header .logo{width:46px;height:46px;border-radius:8px;flex:none}
header .n{font-size:30px;line-height:1;font-weight:700}header .l{font-size:12px;color:#999;margin-top:3px}
nav{margin-left:auto;display:flex;gap:22px;font:500 15px Oswald,sans-serif;text-transform:uppercase;letter-spacing:.05em}
nav a:hover,nav a.on{color:var(--amarillo)}
main{max-width:1180px;margin:0 auto;padding:8px 16px 50px}
.tag{display:inline-block;background:var(--amarillo);color:var(--negro);font:700 11px Inter,sans-serif;text-transform:uppercase;letter-spacing:.08em;padding:4px 8px;border-radius:3px}
.hero{display:grid;grid-template-columns:1.4fr 1fr;gap:18px}
.big{position:relative;border-radius:14px;overflow:hidden;min-height:440px;background:var(--panel);display:block}
.big img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;object-position:top;opacity:.16;filter:grayscale(1)}
.big .t{position:absolute;left:0;right:0;bottom:0;padding:26px;background:linear-gradient(transparent,#000 55%)}
.big h2{font-size:38px;line-height:1.05;margin:10px 0}.big p{color:#ccc;margin:0}
.mini{display:flex;flex-direction:column;gap:18px}
.mini a{background:var(--panel);border-radius:14px;padding:20px;flex:1;border-left:4px solid var(--amarillo);display:block}
.mini h3{font-size:23px;line-height:1.15;margin:10px 0 6px}.mini p{color:#aaa;margin:0;font-size:14px}
a:hover h2,a:hover h3{color:var(--amarillo)}
.sec{font-size:22px;margin:36px 0 14px;display:flex;align-items:center;gap:10px;font-weight:700}
.sec:after{content:"";flex:1;height:2px;background:var(--linea)}
.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:18px}
.card{background:var(--panel);border-radius:14px;overflow:hidden;display:block}
.card img{width:100%;aspect-ratio:16/9;object-fit:cover;object-position:top}
.card div{padding:16px}.card h3{font-size:20px;line-height:1.2;margin:8px 0 6px;font-weight:600}
.fecha{font-size:13px;color:var(--suave)}
.vacio{background:var(--panel);border-radius:14px;padding:40px 24px;text-align:center;color:var(--suave)}
article{max-width:760px;margin:0 auto}
article h1{font-size:clamp(30px,5.5vw,48px);line-height:1.05;margin:14px 0 10px}
article .entradilla{font-size:19px;color:#ccc;margin:12px 0 22px}
article .fotos{display:flex;gap:12px;overflow-x:auto;margin:22px 0}
article .fotos img{width:min(100%,420px);flex:none;border-radius:10px}
article h2{font:600 24px Oswald,sans-serif;text-transform:uppercase;margin:34px 0 8px;color:var(--amarillo)}
article p{margin:0 0 14px}article strong{color:#fff}
.volver{display:inline-block;margin-top:30px;color:var(--amarillo);font-weight:600}
table{border-collapse:collapse;width:100%;font-size:15px;margin:10px 0 20px}
td,th{border-bottom:1px solid var(--linea);padding:7px 8px;text-align:left}th{color:var(--suave);font-weight:600}
.dia{margin-bottom:30px}.comp{margin:0 0 18px;background:var(--panel);border-radius:14px;padding:14px 18px}
.comp h3{font-size:18px;margin:0 0 8px}.comp h3 a:hover{color:var(--amarillo)}
.partido{display:grid;grid-template-columns:1fr auto 1fr;gap:12px;align-items:center;padding:7px 0;border-top:1px solid var(--linea)}
.partido .l{text-align:right}.partido b.hora{background:none;color:var(--amarillo);border:2px solid var(--amarillo)}.partido b{background:var(--amarillo);color:var(--negro);border-radius:4px;padding:2px 9px;font-variant-numeric:tabular-nums;white-space:nowrap}
.ligas{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:14px}
.ligas a{background:var(--panel);border-radius:12px;padding:16px 18px;border-left:4px solid var(--amarillo);display:block}
.ligas a span{font-size:20px;font-weight:600;display:block}.ligas a:hover span{color:var(--amarillo)}.ligas small{color:var(--suave)}
.liga{display:grid;grid-template-columns:1fr 1fr;gap:24px}.pos{color:var(--amarillo)}
.lt-p{display:block;font:700 11px Inter,sans-serif;text-transform:uppercase;letter-spacing:.08em;color:var(--suave);margin:12px 0 4px}
.lt-p:first-child{margin-top:0}.lt-p:hover{color:var(--amarillo)}
.partido .centro{display:flex;flex-direction:column;align-items:center;gap:5px}
.btn-previa{display:inline-block;font:700 11px Inter,sans-serif;text-transform:uppercase;letter-spacing:.06em;
 color:var(--negro);background:var(--amarillo);padding:3px 9px;border-radius:99px}
.btn-previa:hover{background:#fff}article h2{scroll-margin-top:16px}
article .ficha{margin:-2px 0 10px;font-size:14px;color:var(--suave)}article .ficha b{color:var(--amarillo)}
article .forma{font-size:13px;color:var(--suave);margin:0 0 12px;line-height:2}
article .forma .eq{display:inline-block;min-width:150px;margin-right:6px}
article .forma span[class^=f]{display:inline-block;width:22px;height:22px;line-height:22px;text-align:center;border-radius:4px;
 margin-right:3px;font-weight:700;font-size:12px;color:#111}
.fG{background:#3ec46d}.fE{background:#bdbdbd}.fP{background:#e5534b}
/* Previa de un partido (página propia, estilo periódico) */
.pp{max-width:1100px;margin:0 auto;padding-top:14px}
.pp .miga{font:500 13px Oswald,sans-serif;text-transform:uppercase;letter-spacing:.08em;color:var(--amarillo)}
.pp .miga span{color:#888}.pp .miga a:hover{color:#fff}
.pp h1{font-size:clamp(30px,5.2vw,52px);line-height:1.05;margin:12px 0 14px;max-width:920px}
.pp .entr{font:400 clamp(18px,2.4vw,21px)/1.5 'Source Serif 4',Georgia,serif;color:#cfcfcf;max-width:820px;margin:0 0 18px}
.pp .firma{display:flex;flex-wrap:wrap;gap:8px 14px;align-items:center;justify-content:space-between;font-size:13px;color:var(--suave);
 border-top:1px solid var(--linea);border-bottom:1px solid var(--linea);padding:10px 0;margin-bottom:26px}
.pp .firma b{color:#eee}
.comparte{display:flex;gap:8px}.comparte a,.comparte button{font:700 12px Inter,sans-serif;border-radius:99px;padding:6px 12px;
 border:1px solid var(--linea);background:var(--panel);color:#eee;cursor:pointer}
.comparte a:hover,.comparte button:hover{border-color:var(--amarillo);color:var(--amarillo)}
.marcador{display:grid;grid-template-columns:1fr auto 1fr;align-items:center;gap:10px;background:var(--panel);
 border:1px solid var(--linea);border-radius:12px;padding:20px 26px;margin-bottom:30px}
.marcador .eq{display:flex;align-items:center;gap:14px;font:700 clamp(17px,2.6vw,26px)/1.1 Oswald,sans-serif;text-transform:uppercase}
.marcador .eq.v{flex-direction:row-reverse;text-align:right}
.escudo{position:relative;flex:none;width:58px;height:58px;border-radius:50%;background:#262626;color:var(--amarillo);
 display:flex;align-items:center;justify-content:center;font:700 18px Oswald,sans-serif}
.escudo img{position:absolute;inset:0;width:100%;height:100%;object-fit:contain;background:var(--panel)}
.marcador .hora{text-align:center;padding:0 10px}.marcador .hora b{display:block;font:700 clamp(28px,4vw,40px)/1 Oswald,sans-serif;color:var(--amarillo)}
.marcador .hora span{font-size:12px;color:var(--suave);text-transform:uppercase;letter-spacing:.08em}
.pp .cols{display:grid;grid-template-columns:minmax(0,1fr) 340px;gap:44px;align-items:start}
.pp .texto p{font:400 19px/1.7 'Source Serif 4',Georgia,serif;color:#e4e4e4;margin:0 0 20px}
.pp .texto .cap{float:left;font:700 60px/.85 Oswald,sans-serif;color:var(--amarillo);margin:6px 8px 0 0}
.pp .texto h2{font:700 22px Oswald,sans-serif;text-transform:uppercase;color:var(--amarillo);margin:32px 0 14px;letter-spacing:.03em}
.claves{list-style:none;padding:0;margin:0}.claves li{border-left:4px solid var(--amarillo);padding:10px 16px;margin-bottom:12px;
 background:var(--panel);font-size:16px;line-height:1.5}.claves b{color:#fff}
.pp aside .caja{background:var(--panel);border:1px solid var(--linea);border-radius:12px;padding:18px 20px;margin-bottom:18px}
.pp aside h3{font:700 16px Oswald,sans-serif;text-transform:uppercase;letter-spacing:.06em;margin:0 0 10px;color:var(--amarillo)}
.dato{display:flex;justify-content:space-between;gap:12px;font-size:14px;padding:8px 0;border-bottom:1px solid #222;text-align:right}
.dato:last-child{border:0}.dato span{color:var(--suave);text-align:left}
.racha{display:flex;justify-content:space-between;align-items:center;gap:10px;font-size:14px;margin:10px 0}
.racha i{display:inline-block;width:24px;height:24px;line-height:24px;text-align:center;border-radius:4px;font:700 12px Inter,sans-serif;
 font-style:normal;color:#111;margin-left:3px}
.pp .nota{font-size:12px;color:#777;margin:6px 0 0}
.mas{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:14px}
.mas a{background:var(--panel);border-radius:12px;padding:14px 16px;border-left:4px solid var(--amarillo);display:block}
.mas small{color:var(--amarillo);font-weight:700}.mas strong{display:block;font:600 18px/1.2 Oswald,sans-serif;text-transform:uppercase;margin:4px 0}
.mas span{font-size:14px;color:var(--suave)}.mas a:hover strong{color:var(--amarillo)}
@media(max-width:820px){.pp .cols{display:flex;flex-direction:column;gap:6px}.pp aside{order:-1;width:100%}
 .marcador{padding:16px 12px;gap:6px}.escudo{width:42px;height:42px;font-size:14px}.marcador .eq{flex-direction:column;text-align:center;gap:8px}
 .marcador .eq.v{flex-direction:column;text-align:center}.pp .texto p{font-size:18px}}
/* Noticias */
.notis{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}
.notis a{background:var(--panel);border-radius:12px;padding:16px 18px;border-top:4px solid var(--amarillo);display:block}
.notis small{color:var(--amarillo);font:700 11px Inter,sans-serif;text-transform:uppercase;letter-spacing:.08em}
.notis strong{display:block;font:600 19px/1.2 Oswald,sans-serif;text-transform:uppercase;margin:6px 0}
.notis span{font-size:14px;color:var(--suave)}.notis a:hover strong{color:var(--amarillo)}
.card.sin-img div{border-top:4px solid var(--amarillo)}
.fuente{background:var(--panel);border-left:4px solid var(--amarillo);border-radius:8px;padding:12px 16px;font-size:14px;color:var(--suave);margin:26px 0 0}
.fuente a{color:var(--amarillo);font-weight:600}
@media(max-width:820px){.notis{grid-template-columns:1fr}}
/* Regionales */
.regs{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}
.rg{background:var(--panel);border-radius:12px;padding:16px 18px;border:1px solid var(--linea);display:block}
a.rg:hover{border-color:var(--amarillo)}
.rgt{display:flex;justify-content:space-between;align-items:center;gap:8px;margin-bottom:12px}
.rgt small{color:var(--suave);font-size:12px;text-align:right}
.rgm{display:grid;grid-template-columns:1fr auto 1fr;gap:10px;align-items:center;font:600 17px/1.15 Oswald,sans-serif;text-transform:uppercase}
.rgm span:first-child{text-align:right}
.rgm b{background:var(--amarillo);color:var(--negro);border-radius:4px;padding:2px 8px;font-size:14px;white-space:nowrap}
.rgm b.hora{background:none;border:2px solid var(--amarillo);color:var(--amarillo)}
.rg p{color:#bbb;font-size:14px;margin:12px 0 0;text-align:center}
.regcab{display:flex;justify-content:space-between;align-items:end;gap:12px;flex-wrap:wrap;margin:-4px 0 14px;color:var(--suave);font-size:14px}
.regcab a{color:var(--amarillo);font-weight:700}
.rgart{background:var(--panel);border-radius:14px;padding:20px 22px;margin-bottom:16px;scroll-margin-top:16px}
.rgart h3{font-size:24px;line-height:1.15;margin:10px 0 6px}.rgart .rgm{margin:14px 0}
.rgart .txt{font:400 18px/1.65 'Source Serif 4',Georgia,serif;color:#e4e4e4;margin:10px 0 0}
.rgart .firma{font-size:13px;color:var(--suave);margin-top:10px}.rgart .firma b{color:#eee}
.llamada{background:var(--amarillo);color:var(--negro);border-radius:14px;padding:22px 24px;margin:8px 0 26px}
.llamada h2{font:700 24px/1.1 Oswald,sans-serif;text-transform:uppercase;margin:0 0 6px}.llamada p{margin:0 0 12px}
.llamada a{display:inline-block;background:var(--negro);color:var(--amarillo);font-weight:700;padding:8px 16px;border-radius:99px}
/* Más fútbol (segundo plano) */
.sec.peq{font-size:17px;color:var(--suave)}
.franja{display:flex;gap:10px;overflow-x:auto;padding-bottom:6px}
.franja a{flex:none;background:#141414;border:1px solid var(--linea);border-radius:10px;padding:10px 14px;min-width:170px}
.franja small{display:block;color:var(--suave);font-size:11px;text-transform:uppercase;letter-spacing:.06em}
.franja span{font-weight:600;font-size:14px}.franja a:hover{border-color:var(--amarillo)}
@media(max-width:820px){.regs{grid-template-columns:1fr}}
footer{border-top:1px solid var(--linea);color:var(--suave);font-size:13px;text-align:center;padding:28px 16px 36px}
footer .redes{margin-bottom:10px}footer .redes a{color:var(--amarillo);font-weight:600;margin:0 8px}
@media(max-width:820px){.hero,.grid,.liga{grid-template-columns:1fr}.big{min-height:360px}.big h2{font-size:28px}
 header{flex-wrap:wrap;padding:14px 16px 6px}nav{margin-left:0;width:100%;gap:14px;overflow-x:auto;padding:4px 0 6px;font-size:13px}}
"""

NAV = [("index.html", "Portada"), ("rfef.html", "RFEF"), ("regionales.html", "Regionales"),
       ("partidos.html", "Partidos"), ("resultados.html", "Resultados"), ("ligas.html", "Ligas"),
       ("mas-futbol.html", "Más fútbol")]


def _e(t) -> str:
    return html.escape(str(t))


def _instagram(cfg: dict) -> tuple[str, str]:
    usuario = cfg["medio"].get("instagram", "").lstrip("@")
    return usuario, f"https://www.instagram.com/{usuario}/"


def _ticker(arts: list[dict], prof: str) -> str:
    """Barra amarilla con los resultados del último día con partidos."""
    con_partidos = [a for a in arts if a.get("partidos")]
    if not con_partidos:
        return ""
    ultimo = max(a["fecha"] for a in con_partidos)
    piezas = []
    for a in sorted((a for a in con_partidos if a["fecha"] == ultimo), key=lambda a: a.get("prioridad", 3)):
        piezas.append(f'<a class="lt" href="{prof}ligas/{_slug_liga(a["etiqueta"])}.html">{_e(a["etiqueta"])}</a>')
        for p in a["partidos"]:
            piezas.append(f'<a href="{prof}articulos/{a["slug"]}.html">{_e(es(p["local"]))}'
                          f'<b>{p["goles_local"]} - {p["goles_visitante"]}</b>{_e(es(p["visitante"]))}</a>')
    # La tira se repite dos veces y se desplaza en bucle: al llegar a la mitad vuelve al principio
    # sin que se note. Velocidad constante: ~3 s por elemento.
    tira = "".join(piezas)
    segundos = max(20, round(len(piezas) * 3.2))
    return (f'<div class="ticker" style="--dur:{segundos}s"><div class="in">'
            f'<div class="tira">{tira}</div><div class="tira" aria-hidden="true">{tira}</div></div></div>')


def _pagina(cfg: dict, titulo: str, cuerpo: str, prof: str = "", descripcion: str = "",
            activa: str = "", ticker: str = "") -> str:
    m = cfg["medio"]
    usuario, url_ig = _instagram(cfg)
    nav = "".join(f'<a href="{prof}{h}"{" class=on" if h == activa else ""}>{t}</a>' for h, t in NAV)
    ig = f'<a href="{url_ig}" rel="noopener">Instagram @{_e(usuario)}</a>' if usuario else ""
    return f"""<!doctype html><html lang="{m['idioma']}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{_e(titulo)}</title><meta name="description" content="{_e(descripcion or m['lema'])}">
<meta name="theme-color" content="#0d0d0d"><link rel="icon" href="{prof}img/logo.png">
<meta property="og:title" content="{_e(titulo)}"><meta property="og:description" content="{_e(descripcion or m['lema'])}">
<link rel="alternate" type="application/rss+xml" href="{prof}rss.xml">{FUENTES}<style>{CSS}</style></head><body>
{ticker}
<header><a href="{prof}index.html"><img class="logo" src="{prof}img/logo.png" alt="{_e(m['nombre'])}"></a>
<a href="{prof}index.html"><div class="n tit">{_e(m['nombre'])}</div><div class="l">{_e(m['lema'])}</div></a>
<nav>{nav}</nav></header>
<main>{cuerpo}</main>
<footer><div class="redes">{ig}<a href="{prof}rss.xml">RSS</a></div>
Datos de resultados y clasificaciones: API-Football. Crónicas elaboradas automáticamente a partir de esos datos y revisadas por la redacción.
Las noticias de otros medios se redactan de nuevo y enlazan siempre a su fuente original.
Los partidos de Regional los cuentan nuestros corresponsales.<br>
¿Ves un error? Escríbenos y lo corregimos.</footer></body></html>"""


NOTICIAS: list[dict] = []  # se rellena en construir()
LIGAS: set[str] = set()  # etiquetas con página propia en ligas/


def cargar_noticias() -> list[dict]:
    carpeta = CONTENIDO / "noticias"
    ns = [json.loads(p.read_text()) for p in carpeta.glob("*.json")] if carpeta.exists() else []
    # las de fin de semana y las de datos delante dentro del mismo día; luego las de otros medios
    return sorted(ns, key=lambda n: (n["fecha"], n.get("origen") == "datos", n["slug"]), reverse=True)


def _noticias_de(etiqueta: str | None = None, competicion: str | None = None, grupo: str | None = None) -> list[dict]:
    return [n for n in NOTICIAS if (etiqueta is None or n["etiqueta"] == etiqueta)
            and (competicion is None or n.get("competicion") == competicion)
            and (grupo is None or n.get("grupo") == grupo)]


def _bloque_noticias(lista: list[dict], prof: str = "", titulo: str = "Últimas noticias") -> str:
    if not lista:
        return ""
    return (f'<h2 class="sec tit">{titulo}</h2><section class="notis">' + "".join(
        f'<a href="{_url(n, prof)}"><small>{_e(_etiqueta(n))}</small><strong>{_e(n["titular"])}</strong>'
        f'<span>{_e(n["entradilla"])}</span></a>' for n in lista) + "</section>")


def _tarjeta(a: dict, prof: str, cabecera: str) -> str:
    img = _img(a, prof)
    return (f'<a class="card{"" if img else " sin-img"}" href="{_url(a, prof)}">{img}<div>{cabecera}'
            f'<h3 class="tit">{_e(a["titular"])}</h3><span class="fecha">{fecha_larga(a["fecha"])}</span></div></a>')


def cargar_articulos() -> list[dict]:
    arts = [json.loads(p.read_text()) for p in (CONTENIDO / "articulos").glob("*.json")]
    return sorted(arts, key=_orden, reverse=True)


def _orden(a: dict) -> tuple:
    """Más nuevo primero. Cada edición trae las crónicas de ayer y las previas de hoy:
    las crónicas van delante y las previas justo detrás, dentro de la misma edición."""
    previa = a.get("tipo") == "previa"
    d = date.fromisoformat(a["fecha"]) - timedelta(days=1 if previa else 0)
    return (d.isoformat(), 0 if previa else 1, -a.get("prioridad", 3))


def _etiqueta(a: dict) -> str:
    if a.get("tipo") == "noticia":
        return f'{a["categoria"]} · {a["etiqueta"]}'
    return ("Previa · " if a.get("tipo") == "previa" else "") + a["etiqueta"]


def _imagenes(a: dict) -> list[str]:
    return a.get("imagenes") or a.get("imagenes_web") or []


def _img(a: dict, prof: str) -> str:
    imgs = _imagenes(a)
    return f'<img src="{prof}{imgs[0]}" alt="" loading="lazy">' if imgs else ""


def _url(a: dict, prof: str) -> str:
    if a.get("tipo") == "noticia":
        return f'{prof}noticias/{a["slug"]}.html'
    return f'{prof}articulos/{a["slug"]}.html'


def _portada(lista: list[dict], prof: str = "", extra: str = "") -> str:
    if not lista:
        return '<div class="vacio">Aún no hay noticias. La próxima edición sale mañana a primera hora.</div>'
    a0, resto = lista[0], lista[1:]
    hero = (f'<a class="big" href="{_url(a0, prof)}">{_img(a0, prof)}<div class="t"><span class="tag">{_e(_etiqueta(a0))}</span>'
            f'<h2 class="tit">{_e(a0["titular"])}</h2><p>{_e(a0["entradilla"])}</p></div></a>')
    mini = "".join(f'<a href="{_url(a, prof)}"><span class="tag">{_e(_etiqueta(a))}</span><h3 class="tit">{_e(a["titular"])}</h3>'
                   f'<p>{_e(a["entradilla"])}</p></a>' for a in resto[:2])
    out = f'<section class="hero">{hero}<div class="mini">{mini}</div></section>' if mini else \
          f'<section class="hero" style="grid-template-columns:1fr">{hero}</section>'
    out += extra
    if resto[2:]:
        out += '<h2 class="sec tit">Más noticias</h2><section class="grid">' + "".join(
            f'<a class="card" href="{_url(a, prof)}">{_img(a, prof)}<div><span class="tag">{_e(_etiqueta(a))}</span>'
            f'<h3 class="tit">{_e(a["titular"])}</h3><span class="fecha">{fecha_larga(a["fecha"])}</span></div></a>'
            for a in resto[2:]) + "</section>"
    return out


def _slug_liga(etiqueta: str) -> str:
    t = unicodedata.normalize("NFKD", etiqueta).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")


def _filas_partidos(partidos: list[dict]) -> str:
    return "".join(f'<div class="partido"><span class="l">{_e(es(p["local"]))}</span>'
                   f'<b>{p["goles_local"]} - {p["goles_visitante"]}</b><span>{_e(es(p["visitante"]))}</span></div>'
                   for p in partidos)


def _tabla(tabla: list[dict]) -> str:
    filas = "".join(f'<tr><td><b class="pos">{t["pos"]}</b></td><td>{_e(es(t["equipo"]))}</td><td>{t.get("pj", "")}</td>'
                    f'<td>{t.get("dg", "")}</td><td><strong>{t["pts"]}</strong></td></tr>' for t in tabla)
    return f'<div class="comp"><table><tr><th>#</th><th>Equipo</th><th>PJ</th><th>DG</th><th>Pts</th></tr>{filas}</table></div>'


def _ligas(arts: list[dict]) -> dict[str, list[dict]]:
    """etiqueta → artículos de esa liga (ya ordenados de más nuevo a más viejo)."""
    out: dict[str, list[dict]] = {}
    for a in arts:
        out.setdefault(a["etiqueta"], []).append(a)
    return out


PAISES = {"Spain": "España", "England": "Inglaterra", "Italy": "Italia", "Germany": "Alemania",
          "France": "Francia", "Portugal": "Portugal", "Netherlands": "Países Bajos", "World": "Selecciones"}


def _indice_ligas(cfg: dict, ligas: dict[str, list[dict]]) -> str:
    """Todas las competiciones de config.yaml, tengan ya noticias o no, agrupadas por país."""
    out = '<h1 class="sec tit">Ligas</h1>'
    por_pais: dict[str, list[dict]] = {}
    for c in cfg.get("competiciones", []):
        por_pais.setdefault(PAISES.get(c.get("pais"), c.get("pais", "Otras")), []).append(c)
    for pais, comps in por_pais.items():
        out += f'<h2 class="tit" style="font-size:20px;color:var(--amarillo);margin:26px 0 12px">{_e(pais)}</h2><div class="ligas">'
        for c in comps:
            suyas = [a for e, l in ligas.items() for a in l if a.get("competicion", a["etiqueta"]) == c["etiqueta"]]
            jugadas = [a["fecha"] for a in suyas if a.get("partidos")]
            proximas = [a["fecha"] for a in suyas if a.get("proximos")]
            nota = (f'Última jornada: {fecha_larga(max(jugadas))}' if jugadas else
                    f'Próximo partido: {fecha_larga(max(proximas))}' if proximas else "Próximamente")
            out += (f'<a href="ligas/{_slug_liga(c["etiqueta"])}.html"><span class="tit">{_e(c["etiqueta"])}</span>'
                    f'<small>{nota}</small></a>')
        out += "</div>"
    return out


def _pagina_competicion(c: dict, ligas: dict[str, list[dict]]) -> str:
    """Página de una competición con grupos (p. ej. Tercera Federación): enlaces a cada grupo + noticias."""
    prof = "../"
    grupos = {e: l for e, l in ligas.items() if l[0].get("competicion") == c["etiqueta"]}
    out = (f'<span class="tag">{_e(PAISES.get(c.get("pais"), ""))}</span>'
           f'<h1 class="tit" style="font-size:clamp(30px,5vw,46px);margin:12px 0 4px">{_e(c["etiqueta"])}</h1>')
    if not grupos:
        return out + ('<div class="vacio" style="margin-top:24px">Todavía no hay partidos de esta competición. '
                      'En cuanto se juegue la próxima jornada aparecerán aquí sus resultados y noticias.</div>')
    out += '<h2 class="sec tit">Grupos</h2><div class="ligas">' + "".join(
        f'<a href="{_slug_liga(e)}.html"><span class="tit">{_e(e.split(" · ", 1)[-1])}</span>'
        f'<small>{fecha_larga(l[0]["fecha"])}</small></a>'
        for e, l in sorted(grupos.items(), key=lambda x: [int(n) if n.isdigit() else n for n in re.split(r"(\d+)", x[0])])) + "</div>"
    noticias = sorted([a for l in grupos.values() for a in l] + _noticias_de(competicion=c["etiqueta"]),
                      key=lambda a: a["fecha"], reverse=True)[:12]
    out += '<h2 class="sec tit">Últimas noticias</h2><section class="grid">' + "".join(
        _tarjeta(a, prof, f'<span class="tag">{_e(_etiqueta(a))}</span>') for a in noticias) + "</section>"
    return out


def _pagina_liga(etiqueta: str, lista: list[dict]) -> str:
    prof = "../"
    out = f'<span class="tag">{"España" if lista[0]["grupo"] == "espana" else "Internacional"}</span>' \
          f'<h1 class="tit" style="font-size:clamp(30px,5vw,46px);margin:12px 0 4px">{_e(etiqueta)}</h1>'
    previa = next((a for a in lista if a.get("proximos")), None)
    ultima_jugada = next((a["fecha"] for a in lista if a.get("partidos")), "")
    if previa and previa["fecha"] > ultima_jugada:
        filas = "".join(f'<div class="partido"><span class="l">{_e(es(p["local"]))}</span>'
                        f'<b class="hora">{_e(p["fecha"][11:16] or "--:--")}</b><span>{_e(es(p["visitante"]))}</span></div>'
                        for p in previa["proximos"])
        out += (f'<h2 class="sec tit">Próximos partidos</h2><div class="comp"><h3 class="tit">'
                f'<a href="{_url(previa, prof)}">{fecha_larga(previa["fecha"])} · Leer la previa →</a></h3>{filas}</div>')
    out += '<div class="liga">'
    # Resultados: las 3 últimas jornadas con partidos
    res = "".join(f'<div class="comp"><h3 class="tit">{fecha_larga(a["fecha"])}</h3>{_filas_partidos(a["partidos"])}</div>'
                  for a in [a for a in lista if a.get("partidos")][:3])
    out += f'<section><h2 class="sec tit">Resultados</h2>{res or "<div class=vacio>Sin resultados todavía.</div>"}</section>'
    tabla = next((a["clasificacion"] for a in lista if a.get("clasificacion")), None)
    out += '<section><h2 class="sec tit">Clasificación</h2>' + (_tabla(tabla) if tabla else
           '<div class="vacio">La clasificación aparecerá aquí en cuanto la fuente de datos la publique.</div>') + "</section>"
    out += "</div>"
    noticias = sorted(lista + _noticias_de(etiqueta=etiqueta), key=lambda a: a["fecha"], reverse=True)[:12]
    out += '<h2 class="sec tit">Últimas noticias</h2><section class="grid">' + "".join(
        _tarjeta(a, prof, f'<span class="tag">{_e(_etiqueta(a))}</span>') for a in noticias) + "</section>"
    return out


DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]

# Cambia "viernes, 13 de noviembre" por "Hoy"/"Mañana" según el día en que se mire la web
SCRIPT_DIAS = """<script>(function(){function iso(d){return d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0')+'-'+String(d.getDate()).padStart(2,'0')}
var h=new Date(),m=new Date();m.setDate(h.getDate()+1);var n={};n[iso(h)]='Hoy · ';n[iso(m)]='Mañana · ';
document.querySelectorAll('[data-dia]').forEach(function(e){var p=n[e.getAttribute('data-dia')];if(p)e.textContent=p+e.textContent;});
document.querySelectorAll('[data-pasado]').forEach(function(e){if(e.getAttribute('data-pasado')<iso(h))e.style.display='none';});})();</script>"""


def cargar_agenda() -> dict:
    f = CONTENIDO / "agenda.json"
    return json.loads(f.read_text()) if f.exists() else {}


def _dia(fecha: str) -> str:
    d = date.fromisoformat(fecha)
    return f"{DIAS[d.weekday()].capitalize()}, {fecha_larga(fecha)}"


def _ancla(texto: str) -> str:
    """Id de un título dentro de un artículo (el mismo que pone el extension 'toc' de markdown)."""
    return _slug_liga(re.sub(r"[*_`]", "", texto))


def _mapa_previas(arts: list[dict]) -> dict:
    """id de partido → enlace a su previa: su página propia o, en previas antiguas, su apartado en la de la jornada."""
    mapa = {}
    for a in arts:
        if a.get("tipo") != "previa":
            continue
        if a.get("previas_partido"):
            mapa.update({pp["id"]: f'previas/{pp["slug"]}.html' for pp in a["previas_partido"]})
            continue
        titulos = [l[3:].strip() for l in a.get("cuerpo_markdown", "").splitlines() if l.startswith("## ")]
        for p in a.get("proximos", []):
            loc, vis = es(p["local"]).lower(), es(p["visitante"]).lower()
            t = next((t for t in titulos if loc in t.lower() and vis in t.lower()), None)
            mapa[p["id"]] = f'articulos/{a["slug"]}.html' + (f"#{_ancla(t)}" if t else "")
    return mapa


def _escudo(nombre: str, url: str | None) -> str:
    """Escudo del equipo; si no hay o no carga, sus iniciales."""
    ini = "".join(w[0] for w in re.findall(r"[A-Za-zÀ-ÿ]+", nombre) if w[0].isupper())[:3] or nombre[:2]
    img = f'<img src="{_e(url)}" alt="" loading="lazy" onerror="this.remove()">' if url else ""
    return f'<span class="escudo" aria-hidden="true">{_e(ini)}{img}</span>'


def _parrafo_inicial(t: str) -> str:
    """Primer párrafo con la letra (o palabra corta, p. ej. 'El') grande del principio, como en prensa."""
    m = re.match(r"^(\S+?)(\s.*)$", t, re.S)
    if m and len(m.group(1)) <= 3 and m.group(1).isalpha():
        return f'<p><span class="cap">{_e(m.group(1))}</span>{_e(m.group(2))}</p>'
    return f'<p><span class="cap">{_e(t[:1])}</span>{_e(t[1:])}</p>'


def _pagina_previa(cfg: dict, a: dict, pp: dict, p: dict) -> str:
    """Previa de un partido en su propia página, maquetada como una noticia de periódico."""
    prof = "../"
    loc, vis = es(p["local"]), es(p["visitante"])
    jornada = jornada_es(p.get("jornada"))
    hora = (p.get("fecha") or "")[11:16]
    url = f'{cfg["medio"]["url_web"].rstrip("/")}/previas/{pp["slug"]}.html'
    comparte = (f'<div class="comparte"><a href="https://wa.me/?text={quote(pp["titular"] + " " + url)}" target="_blank" rel="noopener">WhatsApp</a>'
                f'<a href="https://twitter.com/intent/tweet?text={quote(pp["titular"])}&amp;url={quote(url)}" target="_blank" rel="noopener">X</a>'
                f'<button type="button" onclick="navigator.clipboard&&navigator.clipboard.writeText(\'{url}\').then(()=>{{this.textContent=\'¡Copiado!\'}})">'
                'Copiar enlace</button></div>')
    out = (f'<div class="pp"><div class="miga"><a href="{prof}ligas/{_slug_liga(a["etiqueta"])}.html">Previa · {_e(a["etiqueta"])}</a>'
           + (f' <span>· {_e(jornada)}</span>' if jornada else "") + '</div>'
           f'<h1 class="tit">{_e(pp["titular"])}</h1><p class="entr">{_e(pp["entradilla"])}</p>'
           f'<div class="firma"><div><b>Redacción {_e(cfg["medio"]["nombre"])}</b> · Madrid · {fecha_larga(a["fecha"])}</div>{comparte}</div>'
           f'<div class="marcador"><div class="eq">{_escudo(loc, p.get("escudo_local"))}<span>{_e(loc)}</span></div>'
           f'<div class="hora"><b>{_e(hora or "--:--")}</b><span>{_e(dia_partido(p.get("fecha")))}</span></div>'
           f'<div class="eq v">{_escudo(vis, p.get("escudo_visitante"))}<span>{_e(vis)}</span></div></div>')
    # Texto
    parrafos = pp.get("parrafos") or []
    texto = (_parrafo_inicial(parrafos[0]) if parrafos else "") + "".join(f"<p>{_e(t)}</p>" for t in parrafos[1:])
    if pp.get("precedente"):
        texto += f'<h2>El último precedente</h2><p>{_e(pp["precedente"])}</p>'
    if pp.get("claves"):
        texto += '<h2>Las claves</h2><ul class="claves">' + "".join(
            f'<li><b>{_e(c["titulo"].rstrip("."))}.</b> {_e(c["texto"])}</li>' for c in pp["claves"]) + "</ul>"
    # Cuadro de datos y racha
    sede = p.get("estadio") or "Por confirmar"
    arbitro = re.sub(r",.*$", "", p.get("arbitro") or "") or "Por confirmar"
    datos = [("Competición", a["etiqueta"]), ("Jornada", jornada.removeprefix("Jornada ")), ("Estadio", sede), ("Ciudad", p.get("ciudad")),
             ("Día", dia_partido(p.get("fecha")).capitalize()), ("Hora", hora), ("Árbitro", arbitro)]
    caja = '<div class="caja"><h3>Ficha del partido</h3>' + "".join(
        f'<div class="dato"><span>{k}</span>{_e(v)}</div>' for k, v in datos if v) + "</div>"
    forma = a.get("forma") or {}
    if forma.get(p["local"]) or forma.get(p["visitante"]):
        filas = ""
        for e in (p["local"], p["visitante"]):
            res = "".join(f'<i class="f{r["resultado"]}" title="{_e(r["marcador"] + " vs " + es(r["rival"]))}">{r["resultado"]}</i>'
                          for r in reversed(forma.get(e, [])))
            filas += f'<div class="racha">{_e(es(e))}<span>{res or "<small>Sin datos</small>"}</span></div>'
        caja += (f'<div class="caja"><h3>Cómo llegan</h3>{filas}'
                 '<p class="nota">Últimos partidos publicados; el más reciente, a la derecha.</p></div>')
    out += f'<div class="cols"><div class="texto">{texto}</div><aside>{caja}</aside></div>'
    # Más previas de la misma jornada
    partidos = {x["id"]: x for x in a.get("proximos", [])}
    otras = [o for o in a.get("previas_partido", []) if o["id"] != pp["id"] and o["id"] in partidos]
    if otras:
        out += '<h2 class="sec tit">Más previas de la jornada</h2><div class="mas">' + "".join(
            f'<a href="{o["slug"]}.html"><small>{_e((partidos[o["id"]].get("fecha") or "")[11:16])}</small>'
            f'<strong>{_e(es(partidos[o["id"]]["local"]))} - {_e(es(partidos[o["id"]]["visitante"]))}</strong>'
            + ("" if o["titular"].endswith("previa del partido") else f'<span>{_e(o["titular"])}</span>')
            + '</a>' for o in otras) + "</div>"
    out += (f'<a class="volver" href="{_url(a, prof)}">← Previa de toda la jornada de {_e(a["etiqueta"])}</a></div>')
    return out


PREVIAS: dict = {}  # se rellena en construir()


def _fila_agenda(p: dict, prof: str = "") -> str:
    if p.get("goles_local") is not None and p.get("goles_visitante") is not None:
        centro = f'<b>{p["goles_local"]} - {p["goles_visitante"]}</b>'
    else:
        centro = f'<b class="hora">{_e((p.get("fecha") or "")[11:16] or "--:--")}</b>'
    if p.get("id") in PREVIAS and p.get("goles_local") is None:  # botón debajo de la hora
        centro = (f'<span class="centro">{centro}'
                  f'<a class="btn-previa" href="{prof}{PREVIAS[p["id"]]}">Previa</a></span>')
    return (f'<div class="partido"><span class="l">{_e(es(p["local"]))}</span>{centro}'
            f'<span>{_e(es(p["visitante"]))}</span></div>')


PRIORIDAD: dict[str, int] = {}  # competición → prioridad actual en config.yaml (se rellena en construir())
PRINCIPAL: set[str] = set()     # competiciones que van delante (la RFEF)


def _prio_comp(c: dict) -> tuple:
    return (PRIORIDAD.get(c.get("competicion"), c.get("prioridad", 3)), c["etiqueta"])


def _agenda(agenda: dict, prof: str = "") -> str:
    out = '<h1 class="sec tit">Partidos</h1>'
    if not agenda:
        return out + '<div class="vacio">El calendario se actualiza cada mañana.</div>'
    for fecha in sorted(agenda):
        comps = agenda[fecha]
        total = sum(len(c["partidos"]) for c in comps)
        out += (f'<section class="dia" data-pasado="{fecha}"><h2 class="tit" data-dia="{fecha}" '
                f'style="font-size:20px;color:var(--amarillo)">{_dia(fecha)}</h2>')
        if not total:
            out += '<div class="vacio">No hay partidos de nuestras ligas este día.</div></section>'
            continue
        for c in sorted(comps, key=_prio_comp):
            out += (f'<div class="comp"><h3 class="tit"><a href="{prof}ligas/{_slug_liga(c["etiqueta"])}.html">'
                    f'{_e(c["etiqueta"])} →</a></h3>{"".join(_fila_agenda(p) for p in c["partidos"])}</div>')
        out += "</section>"
    return out + SCRIPT_DIAS


def _agenda_portada(agenda: dict) -> str:
    """Bloque compacto en la portada con los partidos del primer día de la agenda."""
    for fecha in sorted(agenda):
        comps = sorted((c for c in agenda[fecha] if c["partidos"]), key=_prio_comp)
        if not comps:
            continue
        filas, n = "", 0
        for c in comps:
            if n >= 8:
                break
            filas += (f'<a class="lt-p" href="ligas/{_slug_liga(c["etiqueta"])}.html">{_e(c["etiqueta"])}</a>'
                      + "".join(_fila_agenda(p) for p in c["partidos"][:8 - n]))
            n += len(c["partidos"][:8 - n])
        total = sum(len(c["partidos"]) for c in comps)
        return (f'<div data-pasado="{fecha}"><h2 class="sec tit">Partidos · <span data-dia="{fecha}">{_dia(fecha)}</span></h2>'
                f'<div class="comp">{filas}<h3 class="tit" style="margin:10px 0 0">'
                f'<a href="partidos.html">Ver todos los partidos ({total}) →</a></h3></div></div>')
    return ""


def _resultados(arts: list[dict]) -> str:
    """Todos los resultados de los últimos 7 días con partidos, agrupados por día y competición."""
    dias = sorted({a["fecha"] for a in arts if a.get("partidos")}, reverse=True)[:7]
    if not dias:
        return '<h1 class="sec tit">Resultados</h1><div class="vacio">Aún no hay resultados.</div>'
    out = '<h1 class="sec tit">Resultados</h1>'
    for d in dias:
        out += f'<section class="dia"><h2 class="tit" style="font-size:20px;color:var(--amarillo)">{fecha_larga(d)}</h2>'
        for a in sorted((a for a in arts if a["fecha"] == d and a.get("partidos")), key=lambda a: a.get("prioridad", 3)):
            out += (f'<div class="comp"><h3 class="tit"><a href="ligas/{_slug_liga(a["etiqueta"])}.html">{_e(a["etiqueta"])} →</a></h3>'
                    f'{_filas_partidos(a["partidos"])}</div>')
        out += "</section>"
    return out


def _marcador_regional(r: dict) -> str:
    if r.get("goles_local") is not None and r.get("goles_visitante") is not None:
        return f'<b>{r["goles_local"]} - {r["goles_visitante"]}</b>'
    return f'<b class="hora">{_e(r.get("hora") or "--:--")}</b>'


def _cuando(r: dict) -> str:
    d = date.fromisoformat(r["fecha"])
    return f'{DIAS[d.weekday()][:3].capitalize()} {d.day}'


def _tarjeta_regional(r: dict, prof: str = "") -> str:
    lugar = " · ".join(x for x in (r.get("categoria"), r.get("comunidad")) if x)
    pie = r["titular"] if r["tipo"] == "resultado" else f'{_cuando(r)} · {r["titular"]}'
    return (f'<a class="rg" href="{prof}regionales.html#{r["slug"]}"><div class="rgt"><span class="tag">{_e(r["motivo"])}</span>'
            f'<small>{_e(lugar)}</small></div><div class="rgm"><span>{_e(r["local"])}</span>{_marcador_regional(r)}'
            f'<span>{_e(r["visitante"])}</span></div><p>{_e(pie)}</p></a>')


def _llamada(rc: dict) -> str:
    url = rc.get("formulario_url")
    boton = f'<a href="{_e(url)}" rel="noopener">Mándanos tu partido →</a>' if url else ""
    return ('<div class="llamada"><h2>¿Juegas, entrenas o eres de un club de Regional?</h2>'
            '<p>Cuéntanos los partidos gordos de tu zona (derbis, duelos por el ascenso, historias de barrio) '
            'y los publicamos con tu firma.</p>' + boton + '</div>')


def _proximos_y_resultados(regs: list[dict]) -> tuple[list[dict], list[dict]]:
    hoy = date.today().isoformat()
    proximos = [r for r in regs if r["tipo"] == "previa" and r["fecha"] >= hoy]
    resultados = sorted((r for r in regs if r["tipo"] == "resultado"), key=lambda r: r["fecha"], reverse=True)
    return proximos, resultados


def _regionales_portada(regs: list[dict], rc: dict) -> str:
    proximos, resultados = _proximos_y_resultados(regs)
    n = rc.get("max_portada", 6)
    elegidos = proximos[:n] or resultados[:n]
    url = rc.get("formulario_url")
    cab = ('<h2 class="sec tit">Regionales · Los partidos de la jornada</h2><div class="regcab">'
           '<span>Los duelos que no te puedes perder en toda España, elegidos cada semana.</span>'
           + (f'<a href="{_e(url)}" rel="noopener">¿Conoces un partido gordo? Cuéntanoslo →</a>' if url else
              '<a href="regionales.html">Ver todos →</a>') + '</div>')
    if not elegidos:
        return cab + _llamada(rc)
    return cab + '<section class="regs">' + "".join(_tarjeta_regional(r) for r in elegidos) + '</section>'


def _articulo_regional(r: dict) -> str:
    lugar = " · ".join(x for x in (r.get("categoria"), r.get("comunidad")) if x)
    firma = f'<div class="firma">Por <b>{_e(r["firma"])}</b>, corresponsal de Sin Focos</div>' if r.get("firma") else ""
    parrafos = "".join(f'<p class="txt">{_e(p)}</p>' for p in r.get("texto", "").split("\n") if p.strip())
    return (f'<div class="rgart" id="{r["slug"]}"><span class="tag">{_e(r["motivo"])}</span> '
            f'<span class="fecha">{_e(lugar)} · {_dia(r["fecha"])}</span><h3 class="tit">{_e(r["titular"])}</h3>'
            f'<div class="rgm"><span>{_e(r["local"])}</span>{_marcador_regional(r)}<span>{_e(r["visitante"])}</span></div>'
            f'{parrafos}{firma}</div>')


def _pagina_regionales(regs: list[dict], rc: dict) -> str:
    proximos, resultados = _proximos_y_resultados(regs)
    out = ('<h1 class="sec tit">Regionales</h1><p style="color:var(--suave);margin:-6px 0 18px">'
           'Los partidos gordos del fútbol regional de toda España, contados por gente de allí.</p>')
    if proximos:
        out += '<h2 class="sec tit">Próximos partidos</h2>' + "".join(_articulo_regional(r) for r in proximos)
    if resultados:
        out += '<h2 class="sec tit">Resultados</h2>' + "".join(_articulo_regional(r) for r in resultados[:30])
    if not proximos and not resultados:
        out += '<div class="vacio" style="margin-bottom:20px">Muy pronto, los primeros partidos de Regional.</div>'
    return out + _llamada(rc)


def _franja_mas(secundario: list[dict]) -> str:
    """Franja pequeña al final de la portada con los últimos resultados de lo que va en segundo plano."""
    con_partidos = [a for a in secundario if a.get("partidos")]
    piezas = []
    if con_partidos:
        ultimo = max(a["fecha"] for a in con_partidos)
        for a in sorted((a for a in con_partidos if a["fecha"] == ultimo), key=lambda a: a.get("prioridad", 3)):
            for p in a["partidos"]:
                piezas.append(f'<a href="articulos/{a["slug"]}.html"><small>{_e(a["etiqueta"])}</small>'
                              f'<span>{_e(es(p["local"]))} {p["goles_local"]}-{p["goles_visitante"]} {_e(es(p["visitante"]))}</span></a>')
    piezas = piezas[:14] + ['<a href="mas-futbol.html"><small>Segunda, copas y Europa</small><span>Ver todo →</span></a>']
    return ('<h2 class="sec tit peq">También · Segunda, copas, selecciones y primeras divisiones</h2>'
            f'<div class="franja">{"".join(piezas)}</div>')


def construir(cfg: dict) -> Path:
    PRIORIDAD.clear()
    PRIORIDAD.update({c["etiqueta"]: c.get("prioridad", 3) for c in cfg.get("competiciones", [])})
    PRINCIPAL.clear()
    PRINCIPAL.update(cfg.get("principal") or [])
    arts = cargar_articulos()
    for a in arts:  # la prioridad que manda es la de config.yaml de hoy, no la del día en que se escribió
        a["prioridad"] = PRIORIDAD.get(a.get("competicion"), 3)
    arts.sort(key=_orden, reverse=True)
    agenda = cargar_agenda()
    NOTICIAS.clear()
    NOTICIAS.extend(cargar_noticias())
    PREVIAS.clear()
    PREVIAS.update(_mapa_previas(arts))
    if SALIDA.exists():
        shutil.rmtree(SALIDA)
    (SALIDA / "articulos").mkdir(parents=True)
    (SALIDA / "ligas").mkdir()
    if (CONTENIDO / "img").exists():
        shutil.copytree(CONTENIDO / "img", SALIDA / "img")
    (SALIDA / "img").mkdir(exist_ok=True)
    logo = RAIZ / "marca" / "logo-sinfocos-SF.png"
    if logo.exists():
        from PIL import Image
        Image.open(logo).convert("RGB").resize((192, 192)).save(SALIDA / "img" / "logo.png")
    nombre = cfg["medio"]["nombre"]

    from .regionales import cargar as cargar_regionales
    regs = cargar_regionales()
    rc = cfg.get("regionales") or {}
    principal = [a for a in arts if a.get("competicion") in PRINCIPAL]
    secundario = [a for a in arts if a.get("competicion") not in PRINCIPAL]
    noticias_rfef = [n for n in NOTICIAS if n.get("competicion") in PRINCIPAL]
    noticias_mas = [n for n in NOTICIAS if n.get("competicion") not in PRINCIPAL]

    extra = _regionales_portada(regs, rc) + _bloque_noticias(noticias_rfef[:6])
    extra += (_agenda_portada(agenda) + SCRIPT_DIAS) if agenda else ""
    (SALIDA / "index.html").write_text(_pagina(
        cfg, nombre, _portada(principal[:60], extra=extra) + _franja_mas(secundario), activa="index.html",
        ticker=_ticker(arts, "")))
    (SALIDA / "rfef.html").write_text(_pagina(
        cfg, f"RFEF · {nombre}", '<h1 class="sec tit">Primera, Segunda y Tercera Federación</h1>'
        + _portada(principal[:60], extra=_bloque_noticias(noticias_rfef[:6])), activa="rfef.html",
        descripcion="Crónicas, previas y noticias de Primera, Segunda y Tercera Federación", ticker=_ticker(arts, "")))
    (SALIDA / "mas-futbol.html").write_text(_pagina(
        cfg, f"Más fútbol · {nombre}", '<h1 class="sec tit">Más fútbol</h1>'
        + _portada(secundario[:60], extra=_bloque_noticias(noticias_mas[:6])), activa="mas-futbol.html",
        descripcion="Segunda División, copas, selecciones y primeras divisiones", ticker=_ticker(arts, "")))
    (SALIDA / "regionales.html").write_text(_pagina(
        cfg, f"Regionales · {nombre}", _pagina_regionales(regs, rc), activa="regionales.html",
        descripcion="Los partidos gordos del fútbol regional de toda España", ticker=_ticker(arts, "")))
    for viejo, nuevo in [("espana.html", "rfef.html"), ("internacional.html", "mas-futbol.html")]:  # enlaces antiguos
        (SALIDA / viejo).write_text(f'<!doctype html><meta charset="utf-8"><meta http-equiv="refresh" content="0;url={nuevo}">'
                                    f'<link rel="canonical" href="{nuevo}"><a href="{nuevo}">{nuevo}</a>')
    (SALIDA / "partidos.html").write_text(
        _pagina(cfg, f"Partidos de hoy y mañana · {nombre}", _agenda(agenda), activa="partidos.html",
                descripcion="Horarios de los partidos de hoy y mañana", ticker=_ticker(arts, "")))
    (SALIDA / "resultados.html").write_text(
        _pagina(cfg, f"Resultados · {nombre}", _resultados(arts), activa="resultados.html", ticker=_ticker(arts, "")))

    ligas = _ligas(arts)
    LIGAS.clear()
    LIGAS.update(ligas, (c["etiqueta"] for c in cfg.get("competiciones", [])))
    (SALIDA / "ligas.html").write_text(
        _pagina(cfg, f"Ligas · {nombre}", _indice_ligas(cfg, ligas), activa="ligas.html", ticker=_ticker(arts, "")))
    for etiqueta, lista in ligas.items():
        (SALIDA / "ligas" / f"{_slug_liga(etiqueta)}.html").write_text(
            _pagina(cfg, f"{etiqueta} · {nombre}", _pagina_liga(etiqueta, lista), "../",
                    f"Resultados, clasificación y noticias de {etiqueta}", ticker=_ticker(arts, "../")))
    for c in cfg.get("competiciones", []):  # competiciones con grupos o sin partidos todavía
        if c["etiqueta"] in ligas:
            continue
        (SALIDA / "ligas" / f"{_slug_liga(c['etiqueta'])}.html").write_text(
            _pagina(cfg, f"{c['etiqueta']} · {nombre}", _pagina_competicion(c, ligas), "../",
                    f"Resultados, clasificación y noticias de {c['etiqueta']}", ticker=_ticker(arts, "../")))

    for a in arts:
        fotos = "".join(f'<img src="../{i}" alt="{_e(a["etiqueta"])}">' for i in _imagenes(a))
        cuerpo = (f'<article><a class="tag" href="../ligas/{_slug_liga(a["etiqueta"])}.html">{_e(_etiqueta(a))} →</a><h1 class="tit">{_e(a["titular"])}</h1>'
                  f'<p class="fecha">{fecha_larga(a["fecha"])}</p><p class="entradilla">{_e(a["entradilla"])}</p>'
                  + (f'<div class="fotos">{fotos}</div>' if fotos else "")
                  + markdown.markdown(a["cuerpo_markdown"], extensions=["tables", "toc"],
                                      extension_configs={"toc": {"slugify": lambda t, sep: _ancla(t)}})
                  + '<a class="volver" href="../index.html">← Volver a la portada</a></article>')
        (SALIDA / "articulos" / f"{a['slug']}.html").write_text(
            _pagina(cfg, f"{a['titular']} · {nombre}", cuerpo, "../", a["entradilla"], ticker=_ticker(arts, "../")))

    (SALIDA / "previas").mkdir()
    for a in arts:  # una página por partido con su previa completa
        partidos = {p["id"]: p for p in a.get("proximos", [])}
        for pp in a.get("previas_partido", []):
            if pp["id"] in partidos:
                (SALIDA / "previas" / f'{pp["slug"]}.html').write_text(
                    _pagina(cfg, f'{pp["titular"]} · {nombre}', _pagina_previa(cfg, a, pp, partidos[pp["id"]]), "../",
                            pp["entradilla"], ticker=_ticker(arts, "../")))

    (SALIDA / "noticias").mkdir()
    for n in NOTICIAS:  # una página por noticia
        (SALIDA / "noticias" / f'{n["slug"]}.html').write_text(
            _pagina(cfg, f'{n["titular"]} · {nombre}', _pagina_noticia(n), "../", n["entradilla"],
                    ticker=_ticker(arts, "../")))

    _historias(cfg)
    _rss(cfg, sorted(arts[:40] + NOTICIAS[:20], key=lambda a: a["fecha"], reverse=True))
    (SALIDA / ".nojekyll").write_text("")
    return SALIDA


def _pagina_noticia(n: dict) -> str:
    prof = "../"
    f = n.get("fuente")
    fuente = (f'<p class="fuente">Fuente: <a href="{_e(f["url"])}" rel="noopener nofollow" target="_blank">{_e(f["medio"])}</a>'
              f' · «{_e(f["titular"])}». Noticia redactada por nuestra redacción a partir de esa información.</p>') if f else ""
    relacionadas = [x for x in NOTICIAS if x["slug"] != n["slug"] and x.get("competicion") == n.get("competicion")][:3]
    pagina = n["etiqueta"] if n["etiqueta"] in LIGAS else n.get("competicion", n["etiqueta"])
    return (f'<article><a class="tag" href="{prof}ligas/{_slug_liga(pagina)}.html">{_e(_etiqueta(n))} →</a>'
            f'<h1 class="tit">{_e(n["titular"])}</h1><p class="fecha">{fecha_larga(n["fecha"])}</p>'
            f'<p class="entradilla">{_e(n["entradilla"])}</p>'
            + markdown.markdown(n["cuerpo_markdown"]) + fuente
            + _bloque_noticias(relacionadas, prof, "Más noticias")
            + f'<a class="volver" href="{prof}index.html">← Volver a la portada</a></article>')


def _historias(cfg: dict):
    """historias.html (sin enlace en el menú): las historias del día para guardarlas y subirlas desde el móvil."""
    archivos = sorted((CONTENIDO / "instagram").glob("*-historias.json"), reverse=True)[:3]
    bloques = []
    for n, f in enumerate(archivos):
        h = json.loads(f.read_text())
        fotos = "".join(f'<a href="{i}" download><img src="{i}" alt="Historia" loading="lazy" '
                        f'style="width:100%;max-width:360px;border-radius:12px;margin:8px 0"></a>' for i in h["imagenes"])
        lista = html.escape(json.dumps(h["imagenes"]))
        zip_nombre = f"historias-{h['fecha']}.zip"  # por si el móvil no deja compartir varias fotos a la vez
        with zipfile.ZipFile(SALIDA / zip_nombre, "w") as z:
            for k, i in enumerate(h["imagenes"], 1):
                if (CONTENIDO / i).exists():
                    z.write(CONTENIDO / i, f"{k}-{Path(i).name}")
        boton = ('<button class="btn-historias" data-imgs="{l}" data-zip="{z}" '
                 'style="background:#FFD400;color:#111;border:0;border-radius:10px;padding:14px 22px;'
                 'font-weight:800;font-size:17px;margin:8px 0 14px;cursor:pointer">'
                 '⬇ Guardar todas ({k})</button>').format(l=lista, z=zip_nombre, k=len(h["imagenes"]))
        bloques.append(f'<h2>Historias del {fecha_larga(h["fecha"])}</h2>{boton}'
                       f'<p>En el móvil se abre el menú de compartir: elige "Guardar imágenes" (o "Guardar en Fotos") '
                       f'y se guardan todas de golpe. También puedes mantener pulsada cada una.</p>'
                       f'<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:10px">{fotos}</div>')
    bloques.append('''<script>
document.querySelectorAll(".btn-historias").forEach(b => b.addEventListener("click", async () => {
  const urls = JSON.parse(b.dataset.imgs), texto = b.textContent;
  b.textContent = "Preparando…";
  try {
    const files = await Promise.all(urls.map(async (u, i) =>
      new File([await (await fetch(u)).blob()], (i + 1) + "-" + u.split("/").pop(), {type: "image/jpeg"})));
    if (navigator.canShare && navigator.canShare({files})) await navigator.share({files});
    else location.href = b.dataset.zip;
  } catch (e) { if (e.name !== "AbortError") location.href = b.dataset.zip; }
  b.textContent = texto;
}));
</script>''')
    cuerpo = "<article>" + ("".join(bloques) or "<p>Todavía no hay historias.</p>") + "</article>"
    (SALIDA / "historias.html").write_text(
        _pagina(cfg, f"Historias · {cfg['medio']['nombre']}", cuerpo, descripcion="Historias de Instagram del día"))


def _rss(cfg: dict, arts: list[dict]):
    base = cfg["medio"]["url_web"].rstrip("/")
    items = "".join(
        f"<item><title>{html.escape(a['titular'])}</title><link>{base}/{_url(a, '')}</link>"
        f"<guid>{base}/{_url(a, '')}</guid><description>{html.escape(a['entradilla'])}</description>"
        f"<pubDate>{format_datetime(datetime.fromisoformat(a['fecha']).replace(tzinfo=timezone.utc))}</pubDate></item>"
        for a in arts)
    (SALIDA / "rss.xml").write_text(
        f'<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>{html.escape(cfg["medio"]["nombre"])}</title>'
        f"<link>{base}</link><description>{html.escape(cfg['medio']['lema'])}</description>{items}</channel></rss>")
