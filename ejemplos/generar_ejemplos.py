"""TEMPORAL (se borra antes de fusionar): genera una crónica y una previa de ejemplo con el código nuevo."""
import json, sys
from pathlib import Path
import yaml
from pipeline import fuentes, redactor
from pipeline.__main__ import CONTENIDO  # noqa

cfg = yaml.safe_load(open("config.yaml"))
api = fuentes.ApiFootball()
out = Path("ejemplos")
ligas = api.resolver_ligas(cfg["competiciones"])
quiero = {"Primera Federación · Grupo 1", "Tercera Federación · Grupo 7"}

# Crónicas del 15 de noviembre
cfg2 = {**cfg, "competiciones": cfg["competiciones"]}
paqs = [p for p in fuentes.recopilar("2026-11-15", cfg, api) if p["liga"]["etiqueta"] in quiero]
for paq in paqs:
    texto = redactor.redactar(paq, cfg)
    (out / f"cronica-{paq['liga']['etiqueta'].split(' · ')[0][:7]}-{paq['liga']['etiqueta'][-1]}.json").write_text(
        json.dumps({"paquete": paq, "texto": texto}, ensure_ascii=False, indent=2))
    print("✔ crónica", paq["liga"]["etiqueta"], texto["titular"])

# Previas de la próxima jornada de 1ª Federación Grupo 1
for fecha in ("2026-11-21", "2026-11-22"):
    paqs = [p for p in fuentes.recopilar_previas(fecha, cfg, api) if p["liga"]["etiqueta"] == "Primera Federación · Grupo 1"]
    if paqs:
        paq = paqs[0]
        texto = redactor.redactar_previa(paq, cfg)
        (out / f"previa-{fecha}.json").write_text(json.dumps({"paquete": paq, "texto": texto}, ensure_ascii=False, indent=2))
        print("✔ previa", fecha, texto["titular"])
        break
print("Llamadas API:", api.llamadas)
