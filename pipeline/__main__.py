"""Punto de entrada.

  python -m pipeline generar [--fecha AAAA-MM-DD] [--demo]   → datos + crónicas + imágenes
  python -m pipeline rehacer-tarjetas                        → redibuja imágenes no publicadas (nuevo diseño)
  python -m pipeline noticias [--fecha F] [--prueba]         → solo las noticias (A: datos, B: otros medios)
  python -m pipeline regionales                              → partidos de Regional del formulario de corresponsales
  python -m pipeline web                                     → construye _site/
  python -m pipeline instagram [--simular]                   → publica lo pendiente en Instagram
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from datetime import date, timedelta
from pathlib import Path

import yaml

from . import redactor, tarjetas, web
from .previas import historial
from .web import CONTENIDO, RAIZ


def slug(txt: str) -> str:
    txt = unicodedata.normalize("NFKD", txt).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", txt.lower()).strip("-")[:70]


def generar(cfg: dict, fecha: str, demo: bool):
    if demo:
        from .demo import paquetes_demo
        paquetes = paquetes_demo(fecha)
    else:
        from .fuentes import ApiFootball, recopilar
        api = ApiFootball()
        paquetes = recopilar(fecha, cfg, api)
        print(f"API-Football: {api.llamadas} llamadas")
    if not paquetes:
        print(f"Sin partidos terminados el {fecha} en las competiciones configuradas.")
        return []
    (CONTENIDO / "articulos").mkdir(parents=True, exist_ok=True)
    creados = []
    for paq in paquetes:
        liga = paq["liga"]
        s = slug(f"{fecha}-{liga['etiqueta']}")
        destino = CONTENIDO / "articulos" / f"{s}.json"
        if destino.exists():
            print(f"Ya existe {s}, se salta")
            continue
        try:
            texto = redactor.redactar(paq, cfg, demo=demo)
        except Exception as e:  # una competición fallida no tumba el resto
            print(f"ERROR redactando {liga['etiqueta']}: {e}", file=sys.stderr)
            continue
        imgs = imagenes_cronica(paq, texto["titular"], cfg, s)
        articulo = {
            "slug": s, "fecha": fecha, "etiqueta": liga["etiqueta"], "competicion": liga["competicion"],
            "grupo": liga["grupo"], "prioridad": liga["prioridad"],
            **{k: texto[k] for k in ("titular", "entradilla", "cuerpo_markdown", "texto_instagram", "hashtags")},
            "imagenes": [str(i.relative_to(CONTENIDO)) for i in imgs],
            "partidos": paq["partidos"], "clasificacion": paq["clasificacion"],
        }
        destino.write_text(json.dumps(articulo, ensure_ascii=False, indent=2))
        creados.append(s)
        print(f"✔ {liga['etiqueta']}: {texto['titular']}")
    return creados


def imagenes_cronica(paq: dict, titular: str, cfg: dict, s: str) -> list[Path]:
    """Carrusel de Instagram: portada con el titular + marcadores (+ clasificación si la hay)."""
    cuenta, carpeta = cfg["medio"]["instagram"], CONTENIDO / "img" / paq["fecha"]
    imgs = [tarjetas.tarjeta_portada(paq, titular, cuenta, carpeta / f"{s}-1.jpg",
                                     dato=tarjetas.dato_resultados(paq))]
    imgs += tarjetas.tarjetas_resultados(paq, cuenta, carpeta, s)
    clas = tarjetas.tarjeta_clasificacion(paq, cuenta, carpeta / f"{s}-clasificacion.jpg")
    return imgs + ([clas] if clas else [])


def rehacer_tarjetas(cfg: dict) -> None:
    """Vuelve a dibujar las imágenes de lo aún no publicado en Instagram (tras cambiar el diseño)."""
    for ruta in sorted((CONTENIDO / "articulos").glob("*.json")):
        a = json.loads(ruta.read_text())
        if a.get("ig_media_id"):
            continue
        paq = {"liga": {"etiqueta": a["etiqueta"]}, "fecha": a["fecha"]}
        if a.get("tipo") == "previa":
            web_img = CONTENIDO / a["imagenes_web"][0]
            imgs = tarjetas.tarjetas_previa({**paq, "partidos": a["proximos"]}, cfg["medio"]["instagram"],
                                            web_img.parent, web_img.stem)
            if "imagenes" in a:  # solo las previas nuevas van a Instagram; las antiguas, solo web
                a["imagenes"] = [str(i.relative_to(CONTENIDO)) for i in imgs]
                ruta.write_text(json.dumps(a, ensure_ascii=False, indent=2))
            print("✔", web_img.name, len(imgs), "imágenes")
            continue
        for viejo in a.get("imagenes", []):
            (CONTENIDO / viejo).unlink(missing_ok=True)
        paq.update(partidos=a["partidos"], clasificacion=a.get("clasificacion") or [])
        a["imagenes"] = [str(i.relative_to(CONTENIDO)) for i in imagenes_cronica(paq, a["titular"], cfg, a["slug"])]
        ruta.write_text(json.dumps(a, ensure_ascii=False, indent=2))
        print("✔", a["slug"], len(a["imagenes"]), "imágenes")


def forma_equipos(equipos: set[str], antes_de: str, n: int = 5) -> dict:
    """Últimos resultados publicados de cada equipo (de las crónicas ya guardadas), del más reciente al más antiguo."""
    forma: dict[str, list[dict]] = {e: [] for e in equipos}
    arts = sorted((json.loads(p.read_text()) for p in (CONTENIDO / "articulos").glob("*.json")),
                  key=lambda a: a["fecha"], reverse=True)
    for a in arts:
        if a.get("tipo") == "previa" or a["fecha"] >= antes_de:
            continue
        for p in a.get("partidos", []):
            for eq, gf, gc, rival, campo in [(p["local"], p["goles_local"], p["goles_visitante"], p["visitante"], "casa"),
                                             (p["visitante"], p["goles_visitante"], p["goles_local"], p["local"], "fuera")]:
                if eq in forma and len(forma[eq]) < n and gf is not None:
                    forma[eq].append({"fecha": a["fecha"], "rival": rival, "campo": campo, "marcador": f"{gf}-{gc}",
                                      "resultado": "G" if gf > gc else "E" if gf == gc else "P"})
    return {e: f for e, f in forma.items() if f}


def generar_previas(cfg: dict, fecha: str, demo: bool) -> list[str]:
    """Una previa por competición/grupo con partidos por jugar en `fecha` (normalmente, hoy)."""
    if demo:
        from .demo import paquetes_demo
        paquetes = [{"liga": p["liga"], "fecha": fecha,
                     "partidos": [{**x, "fecha": f"{fecha}T{17 + i % 4}:{'00' if i % 2 else '30'}:00+01:00",
                                   "goles_local": None, "goles_visitante": None, "goleadores": []}
                                  for i, x in enumerate(p["partidos"])]}
                    for p in paquetes_demo(fecha)]
    else:
        from .fuentes import ApiFootball, recopilar_previas
        try:
            paquetes = recopilar_previas(fecha, cfg, ApiFootball())
        except Exception as e:  # p. ej. fecha fuera del rango del plan gratuito: las previas no tumban la edición
            print(f"Sin previas para el {fecha}: {e}", file=sys.stderr)
            return []
    (CONTENIDO / "articulos").mkdir(parents=True, exist_ok=True)
    creados = []
    for paq in paquetes:
        liga = paq["liga"]
        s = slug(f"{fecha}-previa-{liga['etiqueta']}")
        destino = CONTENIDO / "articulos" / f"{s}.json"
        if destino.exists():
            continue
        equipos = {p["local"] for p in paq["partidos"]} | {p["visitante"] for p in paq["partidos"]}
        paq["forma"] = forma_equipos(equipos, fecha)
        guardados = [json.loads(x.read_text()) for x in (CONTENIDO / "articulos").glob("*.json")]
        for p in paq["partidos"]:
            h = historial([g for g in guardados if g["fecha"] < fecha], p["local"], p["visitante"])
            if h:
                p["historial"] = h
        try:
            texto = redactor.redactar_previa(paq, cfg, demo=demo)
        except Exception as e:
            print(f"ERROR en la previa de {liga['etiqueta']}: {e}", file=sys.stderr)
            continue
        imgs = tarjetas.tarjetas_previa(paq, cfg["medio"]["instagram"], CONTENIDO / "img" / fecha, s)
        articulo = {
            "slug": s, "tipo": "previa", "fecha": fecha, "etiqueta": liga["etiqueta"],
            "competicion": liga["competicion"], "grupo": liga["grupo"], "prioridad": liga["prioridad"],
            **{k: texto[k] for k in ("titular", "entradilla", "cuerpo_markdown", "texto_instagram", "hashtags")},
            "imagenes_web": [str(imgs[0].relative_to(CONTENIDO))],
            "imagenes": [str(i.relative_to(CONTENIDO)) for i in imgs],  # carrusel de Instagram
            "proximos": [{k: p.get(k) for k in ("id", "fecha", "estadio", "ciudad", "jornada", "arbitro",
                                                 "local", "visitante", "escudo_local", "escudo_visitante")}
                         for p in paq["partidos"]],
            "forma": paq["forma"],
            # Previa completa de cada partido, con página propia en previas/<slug>.html
            "previas_partido": texto.get("previas_partido", []),
        }
        destino.write_text(json.dumps(articulo, ensure_ascii=False, indent=2))
        creados.append(s)
        print(f"✔ Previa {liga['etiqueta']}: {texto['titular']}")
    return creados


def generar_agenda(cfg: dict, fechas: list[str], demo: bool) -> None:
    """Guarda en contenido/agenda.json los partidos de hoy y mañana para la página 'Partidos'."""
    if demo:
        from .demo import paquetes_demo
        agenda = {}
        for fecha in fechas:
            agenda[fecha] = [{"etiqueta": p["liga"]["etiqueta"], "competicion": p["liga"]["competicion"],
                              "grupo": p["liga"]["grupo"], "prioridad": p["liga"]["prioridad"],
                              "partidos": [{**x, "fecha": f"{fecha}T{17 + i % 4}:{'00' if i % 2 else '30'}:00+01:00",
                                            "goles_local": None, "goles_visitante": None}
                                           for i, x in enumerate(p["partidos"])]}
                             for p in paquetes_demo(fecha)]
    else:
        from .fuentes import ApiFootball, recopilar_agenda
        try:
            agenda = recopilar_agenda(fechas, cfg, ApiFootball())
        except Exception as e:  # la agenda no tumba la edición
            print(f"Sin agenda: {e}", file=sys.stderr)
            return
    campos = ("id", "fecha", "estadio", "jornada", "local", "visitante", "goles_local", "goles_visitante")
    for dia in agenda.values():
        for comp in dia:
            comp["partidos"] = [{k: p.get(k) for k in campos} for p in comp["partidos"]]
    CONTENIDO.mkdir(parents=True, exist_ok=True)
    (CONTENIDO / "agenda.json").write_text(json.dumps(agenda, ensure_ascii=False, indent=2))
    print("Agenda: " + ", ".join(f"{d} ({sum(len(c['partidos']) for c in v)} partidos)" for d, v in agenda.items()))


def main():
    ap = argparse.ArgumentParser(prog="pipeline")
    sub = ap.add_subparsers(dest="orden", required=True)
    g = sub.add_parser("generar")
    g.add_argument("--fecha", default=(date.today() - timedelta(days=1)).isoformat())
    g.add_argument("--demo", action="store_true")
    g.add_argument("--sin-previas", action="store_true", help="no escribir las previas del día siguiente")
    sub.add_parser("web")
    n = sub.add_parser("noticias", help="genera solo las noticias de un día")
    n.add_argument("--fecha", default=(date.today() - timedelta(days=1)).isoformat())
    n.add_argument("--prueba", action="store_true", help="solo comprueba las fuentes, sin IA ni guardar nada")
    r = sub.add_parser("redes", help="genera las 4 publicaciones de Instagram de un día")
    r.add_argument("--fecha", required=True, help="día de publicación (los destacados son del día anterior)")
    sub.add_parser("regionales", help="lee las respuestas nuevas del formulario de corresponsales")
    sub.add_parser("rehacer-tarjetas", help="redibuja las imágenes aún no publicadas con el diseño actual")
    i = sub.add_parser("instagram")
    i.add_argument("--simular", action="store_true")
    i.add_argument("--prueba-make", action="store_true", help="manda un post de ejemplo al webhook de Make")
    args = ap.parse_args()
    cfg = yaml.safe_load((RAIZ / "config.yaml").read_text())

    if args.orden == "generar":
        creados = generar(cfg, args.fecha, args.demo)
        if not args.sin_previas:  # previas de los partidos del día siguiente a --fecha (por defecto, hoy)
            dia_previa = (date.fromisoformat(args.fecha) + timedelta(days=1)).isoformat()
            creados += generar_previas(cfg, dia_previa, args.demo)
        hoy = date.fromisoformat(args.fecha) + timedelta(days=1)
        generar_agenda(cfg, [hoy.isoformat(), (hoy + timedelta(days=1)).isoformat()], args.demo)
        from .noticias import generar_noticias  # noticias (solo web): de nuestros datos y de otros medios
        creados += generar_noticias(cfg, args.fecha)
        from .regionales import generar_regionales  # partidos de Regional que mandan los corresponsales
        try:
            creados += generar_regionales(cfg)
        except Exception as e:  # los regionales nunca tumban la edición
            print(f"ERROR en regionales: {e}", file=sys.stderr)
        from .redes import generar_redes  # plan diario de Instagram: 2 destacados + previa + horarios
        creados += generar_redes(cfg, args.fecha, hoy.isoformat())
        Path(RAIZ / "data").mkdir(exist_ok=True)
        (RAIZ / "data" / "ultimo_resumen.txt").write_text("\n".join(creados))
    elif args.orden == "noticias":
        from . import noticias
        if args.prueba:
            noticias.generar_fuentes(cfg, args.fecha, prueba=True)
        else:
            noticias.generar_noticias(cfg, args.fecha)
    elif args.orden == "regionales":
        from .regionales import generar_regionales
        print("Nuevos:", generar_regionales(cfg))
    elif args.orden == "rehacer-tarjetas":
        rehacer_tarjetas(cfg)
    elif args.orden == "redes":
        from .redes import generar_redes
        generar_redes(cfg, (date.fromisoformat(args.fecha) - timedelta(days=1)).isoformat(), args.fecha)
    elif args.orden == "web":
        print("Web generada en", web.construir(cfg))
    elif args.orden == "instagram":
        from .instagram import prueba_make, publicar_pendientes
        if args.prueba_make:
            prueba_make(cfg)
        else:
            print("Publicados:", publicar_pendientes(cfg, simular=args.simular))


if __name__ == "__main__":
    main()
