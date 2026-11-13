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


def main():
    ap = argparse.ArgumentParser(prog="pipeline")
    sub = ap.add_subparsers(dest="orden", required=True)
    g = sub.add_parser("generar")
    g.add_argument("--fecha", default=(date.today() - timedelta(days=1)).isoformat())
    g.add_argument("--demo", action="store_true")
    sub.add_parser("web")
    i = sub.add_parser("instagram")
    i.add_argument("--simular", action="store_true")
    args = ap.parse_args()
    cfg = yaml.safe_load((RAIZ / "config.yaml").read_text())

    if args.orden == "generar":
        creados = generar(cfg, args.fecha, args.demo)
        Path(RAIZ / "data").mkdir(exist_ok=True)
        (RAIZ / "data" / "ultimo_resumen.txt").write_text("\n".join(creados))
    elif args.orden == "web":
        print("Web generada en", web.construir(cfg))
    elif args.orden == "instagram":
        from .instagram import publicar_pendientes
        print("Publicados:", publicar_pendientes(cfg, simular=args.simular))


if __name__ == "__main__":
    main()
