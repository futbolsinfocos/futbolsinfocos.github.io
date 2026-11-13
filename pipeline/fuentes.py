"""Obtención de datos: resultados, clasificaciones y goleadores desde API-Football.

Una sola llamada `fixtures?date=` devuelve TODOS los partidos del mundo de ese día,
así que el consumo diario es muy bajo: 1 llamada + 1 por clasificación + detalles opcionales.
"""
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path

import requests

BASE = "https://v3.football.api-sports.io"
RAIZ = Path(__file__).resolve().parent.parent
CACHE_LIGAS = RAIZ / "data" / "ligas_resueltas.json"


class ApiFootball:
    def __init__(self, clave: str | None = None):
        self.clave = clave or os.environ.get("API_FOOTBALL_KEY")
        if not self.clave:
            raise RuntimeError("Falta API_FOOTBALL_KEY (o usa --demo)")
        self.llamadas = 0

    # El plan gratuito permite 10 llamadas por minuto: dejamos una pausa entre llamadas
    PAUSA = float(os.environ.get("API_FOOTBALL_PAUSA", "6.5"))
    _ultima = 0.0

    def _get(self, ruta: str, **params) -> list:
        for intento in range(3):
            espera = self.PAUSA - (time.monotonic() - self._ultima)
            if espera > 0:
                time.sleep(espera)
            r = requests.get(f"{BASE}/{ruta}", params=params,
                             headers={"x-apisports-key": self.clave}, timeout=30)
            self._ultima = time.monotonic()
            if r.status_code == 429 and intento < 2:
                print("Límite por minuto de API-Football alcanzado; esperando 60 s…")
                time.sleep(60)
                continue
            break
        r.raise_for_status()
        self.llamadas += 1
        datos = r.json()
        if datos.get("errors"):
            raise RuntimeError(f"API-Football {ruta}: {datos['errors']}")
        return datos.get("response", [])

    # ── Competiciones ──
    def resolver_ligas(self, competiciones: list[dict]) -> list[dict]:
        """Convierte país+patrón en IDs de liga y temporada actual. Se cachea en data/."""
        # La caché se rehace sola si cambia la lista de competiciones de config.yaml
        clave = json.dumps(competiciones, sort_keys=True, ensure_ascii=False)
        if CACHE_LIGAS.exists():
            cache = json.loads(CACHE_LIGAS.read_text())
            if isinstance(cache, dict) and cache.get("clave") == clave:
                return cache["ligas"]
        resueltas, por_pais = [], {}
        for c in competiciones:
            pais = c["pais"]
            if pais not in por_pais:
                por_pais[pais] = self._get("leagues", country=pais, current="true")
            for item in por_pais[pais]:
                liga = item["league"]
                if c.get("id") and liga["id"] != c["id"]:
                    continue
                if not c.get("id") and not re.search(c["patron"], liga["name"]):
                    continue
                temporada = next((s["year"] for s in item["seasons"] if s.get("current")), None)
                grupo_txt = liga["name"].split(" - ")[1] if " - " in liga["name"] else ""
                resueltas.append({
                    "id": liga["id"], "nombre_api": liga["name"], "temporada": temporada,
                    "etiqueta": c["etiqueta"] + (f" · {traducir_grupo(grupo_txt)}" if grupo_txt else ""),
                    "competicion": c["etiqueta"], "grupo": c["grupo"],
                    "prioridad": c.get("prioridad", 3), "pais": pais,
                })
        # Fuera competiciones de temporadas pasadas (play-offs antiguos, grupos extinguidos)
        ultima = {}
        for l in resueltas:
            ultima[l["pais"]] = max(ultima.get(l["pais"], 0), l["temporada"] or 0)
        resueltas = [l for l in resueltas if l["temporada"] == ultima[l["pais"]]]
        CACHE_LIGAS.parent.mkdir(parents=True, exist_ok=True)
        CACHE_LIGAS.write_text(json.dumps({"clave": clave, "ligas": resueltas}, ensure_ascii=False, indent=2))
        return resueltas

    # ── Datos del día ──
    def partidos_del_dia(self, fecha: str, ligas: list[dict], zona: str,
                         estados: tuple = ("FT", "AET", "PEN")) -> list[dict]:
        ids = {l["id"]: l for l in ligas}
        todos = self._get("fixtures", date=fecha, timezone=zona)
        salida = []
        for f in todos:
            liga = ids.get(f["league"]["id"])
            if not liga or f["fixture"]["status"]["short"] not in estados:
                continue
            salida.append(normalizar_partido(f, liga))
        return salida

    def clasificacion(self, liga_id: int, temporada: int) -> list[dict]:
        resp = self._get("standings", league=liga_id, season=temporada)
        if not resp:
            return []
        tabla = resp[0]["league"]["standings"][0]
        return [{"pos": t["rank"], "equipo": t["team"]["name"], "pts": t["points"],
                 "pj": t["all"]["played"], "dg": t["goalsDiff"]} for t in tabla]

    def goleadores(self, partido_id: int) -> list[dict]:
        eventos = self._get("fixtures/events", fixture=partido_id)
        return [{"min": e["time"]["elapsed"], "equipo": e["team"]["name"],
                 "jugador": e["player"]["name"], "tipo": e["detail"]}
                for e in eventos if e["type"] == "Goal" and e["detail"] != "Missed Penalty"]


def traducir_grupo(txt: str) -> str:
    return re.sub(r"Group\s*", "Grupo ", txt)


def normalizar_partido(f: dict, liga: dict) -> dict:
    return {
        "id": f["fixture"]["id"],
        "fecha": f["fixture"]["date"],
        "estadio": (f["fixture"].get("venue") or {}).get("name"),
        "jornada": f["league"].get("round"),
        "liga_id": liga["id"],
        "local": f["teams"]["home"]["name"],
        "visitante": f["teams"]["away"]["name"],
        "goles_local": f["goals"]["home"],
        "goles_visitante": f["goals"]["away"],
        "goleadores": [],
    }


def recopilar(fecha: str, config: dict, api: ApiFootball) -> list[dict]:
    """Devuelve un 'paquete' por competición/grupo con partidos, clasificación y goleadores."""
    ligas = api.resolver_ligas(config["competiciones"])
    print(f"Competiciones encontradas en API-Football: {len(ligas)}")
    for l in ligas:
        print(f"  - [{l['id']}] {l['etiqueta']} (temporada {l['temporada']})")
    partidos = api.partidos_del_dia(fecha, ligas, config["medio"]["zona_horaria"])
    print(f"Partidos terminados el {fecha} en estas competiciones: {len(partidos)}")
    paquetes = []
    presupuesto = config["limites"]["max_llamadas_detalle"]
    for liga in sorted(ligas, key=lambda l: l["prioridad"]):
        suyos = [p for p in partidos if p["liga_id"] == liga["id"]]
        if not suyos:
            continue
        if liga["prioridad"] == 1:
            for p in suyos:
                if presupuesto <= 0:
                    break
                try:
                    p["goleadores"] = api.goleadores(p["id"])
                except Exception as e:  # sin goleadores la crónica sale igual
                    print(f"Sin goleadores para {p['local']}-{p['visitante']}: {e}")
                presupuesto -= 1
        try:
            tabla = api.clasificacion(liga["id"], liga["temporada"])
        except Exception as e:  # el plan gratuito no da clasificaciones de la temporada actual
            print(f"Sin clasificación para {liga['etiqueta']}: {e}")
            tabla = []
        paquetes.append({"liga": liga, "fecha": fecha, "partidos": suyos, "clasificacion": tabla})
    return paquetes[: config["limites"]["max_articulos_dia"]]


def recopilar_previas(fecha: str, config: dict, api: ApiFootball) -> list[dict]:
    """Partidos aún por jugar en `fecha`, un paquete por competición/grupo (para las previas)."""
    ligas = api.resolver_ligas(config["competiciones"])
    partidos = api.partidos_del_dia(fecha, ligas, config["medio"]["zona_horaria"], estados=("NS", "TBD"))
    print(f"Partidos por jugar el {fecha} en estas competiciones: {len(partidos)}")
    paquetes = []
    for liga in sorted(ligas, key=lambda l: l["prioridad"]):
        suyos = sorted((p for p in partidos if p["liga_id"] == liga["id"]), key=lambda p: p["fecha"])
        if suyos:
            paquetes.append({"liga": liga, "fecha": fecha, "partidos": suyos})
    return paquetes[: config["limites"].get("max_previas_dia", 12)]
