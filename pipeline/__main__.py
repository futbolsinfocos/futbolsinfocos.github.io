"""Punto de entrada.

  python -m pipeline generar [--fecha AAAA-MM-DD] [--demo]   → datos + crónicas + imágenes
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
        carpeta = CONTENIDO / "img" / fecha
        imgs = [tarjetas.tarjeta_resultados(paq, cfg["medio"]["nombre"], carpeta / f"{s}-1.jpg")]
        clas = tarjetas.tarjeta_clasificacion(paq, cfg["medio"]["nombre"], carpeta / f"{s}-2.jpg")
        if clas:
            imgs.append(clas)
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
        try:
            texto = redactor.redactar_previa(paq, cfg, demo=demo)
        except Exception as e:
            print(f"ERROR en la previa de {liga['etiqueta']}: {e}", file=sys.stderr)
            continue
        img = tarjetas.tarjeta_previa(paq, cfg["medio"]["nombre"], CONTENIDO / "img" / fecha / f"{s}.jpg")
        articulo = {
            "slug": s, "tipo": "previa", "fecha": fecha, "etiqueta": liga["etiqueta"],
            "competicion": liga["competicion"], "grupo": liga["grupo"], "prioridad": liga["prioridad"],
            **{k: texto[k] for k in ("titular", "entradilla", "cuerpo_markdown", "texto_instagram", "hashtags")},
            # Solo web: sin "imagenes", Instagram no la recoge (las crónicas mandan en Instagram)
            "imagenes_web": [str(img.relative_to(CONTENIDO))],
            "proximos": [{k: p[k] for k in ("id", "fecha", "estadio", "jornada", "local", "visitante")}
                         for p in paq["partidos"]],
        }
        destino.write_text(json.dumps(articulo, ensure_ascii=False, indent=2))
        creados.append(s)
        print(f"✔ Previa {liga['etiqueta']}: {texto['titular']}")
    return creados


def main():
    ap = argparse.ArgumentParser(prog="pipeline")
    sub = ap.add_subparsers(dest="orden", required=True)
    g = sub.add_parser("generar")
    g.add_argument("--fecha", default=(date.today() - timedelta(days=1)).isoformat())
    g.add_argument("--demo", action="store_true")
    g.add_argument("--sin-previas", action="store_true", help="no escribir las previas del día siguiente")
    sub.add_parser("web")
    i = sub.add_parser("instagram")
    i.add_argument("--simular", action="store_true")
    args = ap.parse_args()
    cfg = yaml.safe_load((RAIZ / "config.yaml").read_text())

    if args.orden == "generar":
        creados = generar(cfg, args.fecha, args.demo)
        if not args.sin_previas:  # previas de los partidos del día siguiente a --fecha (por defecto, hoy)
            dia_previa = (date.fromisoformat(args.fecha) + timedelta(days=1)).isoformat()
            creados += generar_previas(cfg, dia_previa, args.demo)
        Path(RAIZ / "data").mkdir(exist_ok=True)
        (RAIZ / "data" / "ultimo_resumen.txt").write_text("\n".join(creados))
    elif args.orden == "web":
        print("Web generada en", web.construir(cfg))
    elif args.orden == "instagram":
        from .instagram import publicar_pendientes
        print("Publicados:", publicar_pendientes(cfg, simular=args.simular))


if __name__ == "__main__":
    main()
