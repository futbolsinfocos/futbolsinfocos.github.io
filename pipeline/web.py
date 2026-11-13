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
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path

import markdown

from .tarjetas import fecha_larga

RAIZ = Path(__file__).resolve().parent.parent
CONTENIDO = RAIZ / "contenido"
SALIDA = RAIZ / "_site"

FUENTES = ('<link rel="preconnect" href="https://fonts.googleapis.com">'
           '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
           '<link href="https://fonts.googleapis.com/css2?family=Oswald:wght@500;600;700'
           '&family=Inter:wght@400;600;700&display=swap" rel="stylesheet">')

CSS = """
:root{--fondo:#0d0d0d;--panel:#181818;--linea:#2a2a2a;--tinta:#f2f2f2;--suave:#a8a8a8;--amarillo:#FFD400;--negro:#111}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--fondo);color:var(--tinta);font:16px/1.55 Inter,system-ui,sans-serif}
a{color:inherit;text-decoration:none}img{display:block;max-width:100%}
.tit{font-family:Oswald,'Arial Narrow',Impact,sans-serif;text-transform:uppercase;letter-spacing:.01em}
.ticker{background:var(--amarillo);color:var(--negro);overflow-x:auto;white-space:nowrap;scrollbar-width:none}
.ticker::-webkit-scrollbar{display:none}
.ticker .in{display:inline-flex;gap:26px;padding:8px 16px;font:700 14px Inter,sans-serif}
.ticker .in>a{display:inline-flex;align-items:center}
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
.partido .l{text-align:right}.partido b{background:var(--amarillo);color:var(--negro);border-radius:4px;padding:2px 9px;font-variant-numeric:tabular-nums;white-space:nowrap}
.ligas{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:14px}
.ligas a{background:var(--panel);border-radius:12px;padding:16px 18px;border-left:4px solid var(--amarillo);display:block}
.ligas a span{font-size:20px;font-weight:600;display:block}.ligas a:hover span{color:var(--amarillo)}.ligas small{color:var(--suave)}
.liga{display:grid;grid-template-columns:1fr 1fr;gap:24px}.pos{color:var(--amarillo)}
footer{border-top:1px solid var(--linea);color:var(--suave);font-size:13px;text-align:center;padding:28px 16px 36px}
footer .redes{margin-bottom:10px}footer .redes a{color:var(--amarillo);font-weight:600;margin:0 8px}
@media(max-width:820px){.hero,.grid,.liga{grid-template-columns:1fr}.big{min-height:360px}.big h2{font-size:28px}
 header{flex-wrap:wrap;padding:14px 16px 6px}nav{margin-left:0;width:100%;gap:14px;overflow-x:auto;padding:4px 0 6px;font-size:13px}}
"""

NAV = [("index.html", "Portada"), ("espana.html", "España"), ("internacional.html", "Internacional"),
       ("ligas.html", "Ligas"), ("resultados.html", "Resultados")]


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
            piezas.append(f'<a href="{prof}articulos/{a["slug"]}.html">{_e(p["local"])}'
                          f'<b>{p["goles_local"]} - {p["goles_visitante"]}</b>{_e(p["visitante"])}</a>')
    return f'<div class="ticker"><div class="in">{"".join(piezas)}</div></div>'


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
Datos de resultados y clasificaciones: API-Football. Crónicas elaboradas automáticamente a partir de esos datos y revisadas por la redacción.<br>
¿Ves un error? Escríbenos y lo corregimos.</footer></body></html>"""


def cargar_articulos() -> list[dict]:
    arts = [json.loads(p.read_text()) for p in (CONTENIDO / "articulos").glob("*.json")]
    return sorted(arts, key=lambda a: (a["fecha"], -a.get("prioridad", 3)), reverse=True)


def _img(a: dict, prof: str) -> str:
    return f'<img src="{prof}{a["imagenes"][0]}" alt="" loading="lazy">' if a.get("imagenes") else ""


def _url(a: dict, prof: str) -> str:
    return f'{prof}articulos/{a["slug"]}.html'


def _portada(lista: list[dict], prof: str = "") -> str:
    if not lista:
        return '<div class="vacio">Aún no hay noticias. La próxima edición sale mañana a primera hora.</div>'
    a0, resto = lista[0], lista[1:]
    hero = (f'<a class="big" href="{_url(a0, prof)}">{_img(a0, prof)}<div class="t"><span class="tag">{_e(a0["etiqueta"])}</span>'
            f'<h2 class="tit">{_e(a0["titular"])}</h2><p>{_e(a0["entradilla"])}</p></div></a>')
    mini = "".join(f'<a href="{_url(a, prof)}"><span class="tag">{_e(a["etiqueta"])}</span><h3 class="tit">{_e(a["titular"])}</h3>'
                   f'<p>{_e(a["entradilla"])}</p></a>' for a in resto[:2])
    out = f'<section class="hero">{hero}<div class="mini">{mini}</div></section>' if mini else \
          f'<section class="hero" style="grid-template-columns:1fr">{hero}</section>'
    if resto[2:]:
        out += '<h2 class="sec tit">Más noticias</h2><section class="grid">' + "".join(
            f'<a class="card" href="{_url(a, prof)}">{_img(a, prof)}<div><span class="tag">{_e(a["etiqueta"])}</span>'
            f'<h3 class="tit">{_e(a["titular"])}</h3><span class="fecha">{fecha_larga(a["fecha"])}</span></div></a>'
            for a in resto[2:]) + "</section>"
    return out


def _slug_liga(etiqueta: str) -> str:
    t = unicodedata.normalize("NFKD", etiqueta).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")


def _filas_partidos(partidos: list[dict]) -> str:
    return "".join(f'<div class="partido"><span class="l">{_e(p["local"])}</span>'
                   f'<b>{p["goles_local"]} - {p["goles_visitante"]}</b><span>{_e(p["visitante"])}</span></div>'
                   for p in partidos)


def _tabla(tabla: list[dict]) -> str:
    filas = "".join(f'<tr><td><b class="pos">{t["pos"]}</b></td><td>{_e(t["equipo"])}</td><td>{t.get("pj", "")}</td>'
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
            nota = f'Última jornada: {fecha_larga(max(a["fecha"] for a in suyas))}' if suyas else "Próximamente"
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
        f'<small>Última jornada: {fecha_larga(l[0]["fecha"])}</small></a>'
        for e, l in sorted(grupos.items(), key=lambda x: [int(n) if n.isdigit() else n for n in re.split(r"(\d+)", x[0])])) + "</div>"
    noticias = sorted((a for l in grupos.values() for a in l), key=lambda a: a["fecha"], reverse=True)[:9]
    out += '<h2 class="sec tit">Últimas noticias</h2><section class="grid">' + "".join(
        f'<a class="card" href="{_url(a, prof)}">{_img(a, prof)}<div><span class="tag">{_e(a["etiqueta"])}</span>'
        f'<h3 class="tit">{_e(a["titular"])}</h3><span class="fecha">{fecha_larga(a["fecha"])}</span></div></a>'
        for a in noticias) + "</section>"
    return out


def _pagina_liga(etiqueta: str, lista: list[dict]) -> str:
    prof = "../"
    out = f'<span class="tag">{"España" if lista[0]["grupo"] == "espana" else "Internacional"}</span>' \
          f'<h1 class="tit" style="font-size:clamp(30px,5vw,46px);margin:12px 0 4px">{_e(etiqueta)}</h1>'
    out += '<div class="liga">'
    # Resultados: las 3 últimas jornadas con partidos
    res = "".join(f'<div class="comp"><h3 class="tit">{fecha_larga(a["fecha"])}</h3>{_filas_partidos(a["partidos"])}</div>'
                  for a in [a for a in lista if a.get("partidos")][:3])
    out += f'<section><h2 class="sec tit">Resultados</h2>{res or "<div class=vacio>Sin resultados todavía.</div>"}</section>'
    tabla = next((a["clasificacion"] for a in lista if a.get("clasificacion")), None)
    out += '<section><h2 class="sec tit">Clasificación</h2>' + (_tabla(tabla) if tabla else
           '<div class="vacio">La clasificación aparecerá aquí en cuanto la fuente de datos la publique.</div>') + "</section>"
    out += "</div>"
    out += '<h2 class="sec tit">Últimas noticias</h2><section class="grid">' + "".join(
        f'<a class="card" href="{_url(a, prof)}">{_img(a, prof)}<div><span class="fecha">{fecha_larga(a["fecha"])}</span>'
        f'<h3 class="tit">{_e(a["titular"])}</h3></div></a>' for a in lista[:9]) + "</section>"
    return out


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


def construir(cfg: dict) -> Path:
    arts = cargar_articulos()
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

    for archivo, filtro, titulo in [("index.html", None, nombre),
                                    ("espana.html", "espana", f"España · {nombre}"),
                                    ("internacional.html", "internacional", f"Internacional · {nombre}")]:
        lista = [a for a in arts if filtro is None or a["grupo"] == filtro][:60]
        (SALIDA / archivo).write_text(_pagina(cfg, titulo, _portada(lista), activa=archivo, ticker=_ticker(arts, "")))
    (SALIDA / "resultados.html").write_text(
        _pagina(cfg, f"Resultados · {nombre}", _resultados(arts), activa="resultados.html", ticker=_ticker(arts, "")))

    ligas = _ligas(arts)
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
        fotos = "".join(f'<img src="../{i}" alt="{_e(a["etiqueta"])}">' for i in a.get("imagenes", []))
        cuerpo = (f'<article><a class="tag" href="../ligas/{_slug_liga(a["etiqueta"])}.html">{_e(a["etiqueta"])} →</a><h1 class="tit">{_e(a["titular"])}</h1>'
                  f'<p class="fecha">{fecha_larga(a["fecha"])}</p><p class="entradilla">{_e(a["entradilla"])}</p>'
                  + (f'<div class="fotos">{fotos}</div>' if fotos else "")
                  + markdown.markdown(a["cuerpo_markdown"], extensions=["tables"])
                  + '<a class="volver" href="../index.html">← Volver a la portada</a></article>')
        (SALIDA / "articulos" / f"{a['slug']}.html").write_text(
            _pagina(cfg, f"{a['titular']} · {nombre}", cuerpo, "../", a["entradilla"], ticker=_ticker(arts, "../")))

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
