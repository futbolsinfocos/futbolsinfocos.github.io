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

from .nombres import es

BASE = "https://v3.football.api-sports.io"
RAIZ = Path(__file__).resolve().parent.parent
CACHE_LIGAS = RAIZ / "data" / "ligas_resueltas.json"
_FIXTURES: dict[tuple, list] = {}


class ApiFootball:
    def __init__(self, clave: str | None = None):
        self.clave = clave or os.environ.get("API_FOOTBALL_KEY")
        if not self.clave:
            raise RuntimeError("Falta API_FOOTBALL_KEY (o usa --demo)")
        self.llamadas = 0
        # Las peticiones salen por nuestro servidor (IP fija y solo nuestra): API-Football bloquea las IP compartidas de GitHub
        proxy = (os.environ.get("API_FOOTBALL_PROXY") or "").strip()
        self.proxies = {"https": proxy, "http": proxy} if proxy else None

    # Plan Pro: 300 llamadas por minuto (el gratuito eran 10): una pausa corta entre llamadas basta
    PAUSA = float(os.environ.get("API_FOOTBALL_PAUSA", "0.3"))
    _ultima = 0.0

    def _get(self, ruta: str, **params) -> list:
        for intento in range(3):
            espera = self.PAUSA - (time.monotonic() - self._ultima)
            if espera > 0:
                time.sleep(espera)
            r = requests.get(f"{BASE}/{ruta}", params=params,
                             headers={"x-apisports-key": self.clave}, timeout=30, proxies=self.proxies)
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
        return datos.get("response", [])  # lista casi siempre; teams/statistics devuelve un objeto

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
        clave = (fecha, zona)  # previas y agenda piden el mismo día: una sola llamada
        if clave not in _FIXTURES:
            _FIXTURES[clave] = self._get("fixtures", date=fecha, timezone=zona)
        todos = _FIXTURES[clave]
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
        return [{"pos": t["rank"], "equipo": es(t["team"]["name"]), "pts": t["points"],
                 "pj": t["all"]["played"], "dg": t["goalsDiff"],
                 "pg": t["all"]["win"], "pe": t["all"]["draw"], "pp": t["all"]["lose"],
                 "gf": t["all"]["goals"]["for"], "gc": t["all"]["goals"]["against"],
                 "forma": (t.get("form") or "")[-5:], "zona": zona(t.get("description")),
                 "escudo": t["team"].get("logo"), "equipo_id": t["team"]["id"],
                 "casa": _registro(t.get("home")), "fuera": _registro(t.get("away"))} for t in tabla]

    def estadisticas_partido(self, partido_id: int) -> dict | None:
        """Posesión, tiros, córners… de un partido. None si la API no las tiene (pasa mucho en 2ª/3ª RFEF)."""
        resp = self._get("fixtures/statistics", fixture=partido_id)
        if len(resp) != 2:
            return None
        lados = []
        for equipo in resp:
            v = {t["type"]: t["value"] for t in equipo.get("statistics", [])}
            lados.append({k: v.get(tipo) for k, tipo in ESTADISTICAS.items()})
        if not any(x is not None for lado in lados for x in lado.values()):
            return None
        return {"local": lados[0], "visitante": lados[1]}

    def goleadores_liga(self, liga_id: int, temporada: int) -> list[dict]:
        """Máximos goleadores de la competición (hasta 20)."""
        salida = []
        for r in self._get("players/topscorers", league=liga_id, season=temporada)[:20]:
            st = (r.get("statistics") or [{}])[0]
            salida.append({"jugador": r["player"]["name"], "equipo": es(st.get("team", {}).get("name")),
                           "escudo": st.get("team", {}).get("logo"),
                           "goles": (st.get("goals") or {}).get("total") or 0,
                           "penaltis": (st.get("penalty") or {}).get("scored") or 0,
                           "pj": (st.get("games") or {}).get("appearences") or 0})
        return salida

    def tarjetas_equipo(self, liga_id: int, temporada: int, equipo_id: int) -> tuple[int, int]:
        """Amarillas y rojas de un equipo en la competición."""
        r = self._get("teams/statistics", league=liga_id, season=temporada, team=equipo_id)
        cards = (r or {}).get("cards", {}) if isinstance(r, dict) else {}
        suma = lambda color: sum((v or {}).get("total") or 0 for v in (cards.get(color) or {}).values())
        return suma("yellow"), suma("red")

    def eventos(self, partido_id: int) -> dict:
        """Goles, expulsiones y penaltis fallados de un partido (una sola llamada)."""
        ev = self._get("fixtures/events", fixture=partido_id)
        fila = lambda e: {"min": e["time"]["elapsed"], "equipo": es(e["team"]["name"]), "jugador": e["player"]["name"]}
        return {
            "goleadores": [{**fila(e), "tipo": e["detail"]} for e in ev
                           if e["type"] == "Goal" and e["detail"] != "Missed Penalty"],
            "rojas": [fila(e) for e in ev if e["type"] == "Card" and e["detail"] in ("Red Card", "Second Yellow card")],
            "penaltis_fallados": [fila(e) for e in ev if e["type"] == "Goal" and e["detail"] == "Missed Penalty"],
        }

    def ultimos(self, equipo_id: int, n: int = 5) -> list[dict]:
        """Últimos n partidos terminados del equipo (cualquier competición), del más reciente al más antiguo."""
        salida = []
        for f in self._get("fixtures", team=equipo_id, last=n):
            casa = f["teams"]["home"]["id"] == equipo_id
            gf, gc = (f["goals"]["home"], f["goals"]["away"]) if casa else (f["goals"]["away"], f["goals"]["home"])
            if gf is None or gc is None:
                continue
            rival = f["teams"]["away" if casa else "home"]["name"]
            salida.append({"fecha": f["fixture"]["date"][:10], "rival": es(rival), "campo": "casa" if casa else "fuera",
                           "marcador": f"{gf}-{gc}", "resultado": "G" if gf > gc else "E" if gf == gc else "P",
                           "competicion": f["league"]["name"]})
        return salida

    def historial(self, id_a: int, id_b: int, n: int = 5) -> list[dict]:
        """Últimos enfrentamientos entre dos equipos (más reciente primero)."""
        salida = []
        for f in self._get("fixtures/headtohead", h2h=f"{id_a}-{id_b}", last=n):
            if f["goals"]["home"] is None:
                continue
            salida.append({"fecha": f["fixture"]["date"][:10], "competicion": f["league"]["name"],
                           "resultado": f'{es(f["teams"]["home"]["name"])} {f["goals"]["home"]}-{f["goals"]["away"]} '
                                        f'{es(f["teams"]["away"]["name"])}'})
        return salida

    def goleadores(self, partido_id: int) -> list[dict]:
        eventos = self._get("fixtures/events", fixture=partido_id)
        return [{"min": e["time"]["elapsed"], "equipo": es(e["team"]["name"]),
                 "jugador": e["player"]["name"], "tipo": e["detail"]}
                for e in eventos if e["type"] == "Goal" and e["detail"] != "Missed Penalty"]


def _registro(r: dict | None) -> dict:
    """Partidos en casa o fuera de la clasificación: {'pj','pg','pe','pp','gf','gc'}."""
    if not r:
        return {}
    return {"pj": r.get("played"), "pg": r.get("win"), "pe": r.get("draw"), "pp": r.get("lose"),
            "gf": (r.get("goals") or {}).get("for"), "gc": (r.get("goals") or {}).get("against")}


def posiciones_antes(tabla: list[dict], partidos: list[dict]) -> dict:
    """Puesto de cada equipo antes de la jornada (quitando el resultado de estos partidos): equipo → puesto."""
    if not tabla:
        return {}
    quita = {}
    for p in partidos:
        gl, gv = p.get("goles_local"), p.get("goles_visitante")
        if gl is None or gv is None:
            continue
        for eq, a, b in ((p["local"], gl, gv), (p["visitante"], gv, gl)):
            quita[eq] = (3 if a > b else 1 if a == b else 0, a - b, a)
    filas = []
    for t in tabla:
        q = quita.get(t["equipo"], (0, 0, 0))
        filas.append((t["pts"] - q[0], (t.get("dg") or 0) - q[1], (t.get("gf") or 0) - q[2], t["equipo"]))
    filas.sort(key=lambda x: (-x[0], -x[1], -x[2]))
    return {f[3]: i for i, f in enumerate(filas, 1)}


ESTADISTICAS = {"posesion": "Ball Possession", "tiros": "Total Shots", "a_puerta": "Shots on Goal",
                "corners": "Corner Kicks", "faltas": "Fouls", "fueras_juego": "Offsides",
                "amarillas": "Yellow Cards", "rojas": "Red Cards"}


def zona(desc: str | None) -> str:
    """'Promotion - Primera Federación (Play Offs)' → 'playoff'; 'Relegation...' → 'descenso'."""
    d = (desc or "").lower()
    if not d:
        return ""
    if "releg" in d:
        return "descenso"
    if "play" in d:
        return "playoff"
    if "promot" in d or "champions" in d:
        return "ascenso"
    return "otra"


def traducir_grupo(txt: str) -> str:
    return re.sub(r"Group\s*", "Grupo ", txt)


def normalizar_partido(f: dict, liga: dict) -> dict:
    return {
        "id": f["fixture"]["id"],
        "fecha": f["fixture"]["date"],
        "estadio": (f["fixture"].get("venue") or {}).get("name"),
        "ciudad": (f["fixture"].get("venue") or {}).get("city"),
        "arbitro": f["fixture"].get("referee"),
        "jornada": f["league"].get("round"),
        "liga_id": liga["id"],
        "id_local": f["teams"]["home"]["id"],
        "id_visitante": f["teams"]["away"]["id"],
        "local": es(f["teams"]["home"]["name"]),
        "visitante": es(f["teams"]["away"]["name"]),
        "escudo_local": f["teams"]["home"].get("logo"),
        "escudo_visitante": f["teams"]["away"].get("logo"),
        "goles_local": f["goals"]["home"],
        "goles_visitante": f["goals"]["away"],
        "goleadores": [],
    }


def recopilar(fecha: str, config: dict, api: ApiFootball, conocidos: dict | None = None,
              stats_conocidas: dict | None = None) -> list[dict]:
    """Devuelve un 'paquete' por competición/grupo con partidos, clasificación, goleadores y estadísticas.
    conocidos: {id_partido: goleadores} de partidos ya descargados en otra pasada del día (no se repiten llamadas).
    stats_conocidas: {id_partido: estadísticas} igual, para las estadísticas del partido."""
    conocidos = conocidos or {}
    stats_conocidas = stats_conocidas or {}
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
        for p in suyos:  # con el plan Pro: goleadores y estadísticas de todos los partidos
            if p["id"] in conocidos:
                previo = conocidos[p["id"]]
                p.update(previo if isinstance(previo, dict) else {"goleadores": previo})
            elif presupuesto > 0:
                try:
                    p.update(api.eventos(p["id"]))
                except Exception as e:  # sin goleadores la crónica sale igual
                    print(f"Sin goleadores para {p['local']}-{p['visitante']}: {e}")
                presupuesto -= 1
            if p["id"] in stats_conocidas:
                p["estadisticas"] = stats_conocidas[p["id"]]
            elif presupuesto > 0:
                try:
                    p["estadisticas"] = api.estadisticas_partido(p["id"])
                except Exception as e:
                    print(f"Sin estadísticas para {p['local']}-{p['visitante']}: {e}")
                presupuesto -= 1
        try:
            tabla = api.clasificacion(liga["id"], liga["temporada"])
        except Exception as e:  # el plan gratuito no da clasificaciones de la temporada actual
            print(f"Sin clasificación para {liga['etiqueta']}: {e}")
            tabla = []
        antes = posiciones_antes(tabla, suyos)
        movimientos = {t["equipo"]: {"antes": antes.get(t["equipo"]), "ahora": t["pos"]} for t in tabla
                       if any(t["equipo"] in (p["local"], p["visitante"]) for p in suyos)}
        paquetes.append({"liga": liga, "fecha": fecha, "partidos": suyos, "clasificacion": tabla,
                         "movimientos": movimientos})
    return paquetes[: config["limites"]["max_articulos_dia"]]


def estadisticas_liga(liga: dict, tabla: list[dict], api: ApiFootball) -> dict:
    """Máximos goleadores y tarjetas por equipo de una competición (una vez por jornada)."""
    salida = {"etiqueta": liga["etiqueta"], "competicion": liga["competicion"], "goleadores": [], "tarjetas": []}
    try:
        salida["goleadores"] = api.goleadores_liga(liga["id"], liga["temporada"])
    except Exception as e:
        print(f"Sin goleadores de {liga['etiqueta']}: {e}")
    for t in tabla:
        if not t.get("equipo_id"):
            continue
        try:
            am, ro = api.tarjetas_equipo(liga["id"], liga["temporada"], t["equipo_id"])
        except Exception as e:
            print(f"Sin tarjetas de {t['equipo']}: {e}")
            continue
        salida["tarjetas"].append({"equipo": t["equipo"], "escudo": t.get("escudo"), "amarillas": am, "rojas": ro})
    salida["tarjetas"].sort(key=lambda x: (-x["amarillas"] - 3 * x["rojas"], x["equipo"]))
    return salida


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
    paquetes = paquetes[: config["limites"].get("max_previas_dia", 12)]
    for paq in paquetes:
        contexto_previa(paq, api)
    return paquetes


def contexto_previa(paq: dict, api: ApiFootball) -> None:
    """Añade a cada partido cómo llega cada equipo: puesto, puntos, casa/fuera, racha, máximo goleador e historial."""
    liga = paq["liga"]
    try:
        tabla = api.clasificacion(liga["id"], liga["temporada"])
    except Exception as e:
        print(f"Sin clasificación para la previa de {liga['etiqueta']}: {e}")
        tabla = []
    paq["clasificacion"] = tabla
    try:
        pichichis = api.goleadores_liga(liga["id"], liga["temporada"])
    except Exception as e:
        print(f"Sin goleadores para la previa de {liga['etiqueta']}: {e}")
        pichichis = []
    por_equipo = {}
    for g in pichichis:
        por_equipo.setdefault(g["equipo"], {"jugador": g["jugador"], "goles": g["goles"]})
    filas = {t["equipo"]: t for t in tabla}
    paq["forma"] = paq.get("forma") or {}
    for p in paq["partidos"]:
        ctx = {}
        for lado, eq, eid, sitio in (("local", p["local"], p.get("id_local"), "casa"),
                                     ("visitante", p["visitante"], p.get("id_visitante"), "fuera")):
            t = filas.get(eq, {})
            c = {k: t.get(k) for k in ("pos", "pts", "pj", "pg", "pe", "pp", "gf", "gc", "dg", "zona") if t.get(k) is not None}
            if t.get(sitio):
                c[sitio] = t[sitio]
            if eq in por_equipo:
                c["goleador"] = por_equipo[eq]
            if eid:
                try:
                    racha = api.ultimos(eid)
                    if racha:
                        c["racha"] = racha
                        paq["forma"][eq] = racha
                except Exception as e:
                    print(f"Sin racha de {eq}: {e}")
            ctx[lado] = c
        p["contexto"] = ctx
        if p.get("id_local") and p.get("id_visitante"):
            try:
                h = api.historial(p["id_local"], p["id_visitante"])
                if h:
                    p["historial"] = h
            except Exception as e:
                print(f"Sin historial {p['local']}-{p['visitante']}: {e}")


def recopilar_agenda(fechas: list[str], config: dict, api: ApiFootball) -> dict:
    """Todos los partidos (jugados o no) de cada fecha, agrupados por competición/grupo."""
    ligas = api.resolver_ligas(config["competiciones"])
    agenda = {}
    for fecha in fechas:
        partidos = api.partidos_del_dia(fecha, ligas, config["medio"]["zona_horaria"],
                                        estados=("NS", "TBD", "1H", "HT", "2H", "ET", "P", "BT", "LIVE",
                                                 "FT", "AET", "PEN", "PST", "SUSP", "INT"))
        agenda[fecha] = [{"etiqueta": l["etiqueta"], "competicion": l["competicion"], "grupo": l["grupo"],
                          "prioridad": l["prioridad"],
                          "partidos": sorted((p for p in partidos if p["liga_id"] == l["id"]), key=lambda p: p["fecha"])}
                         for l in sorted(ligas, key=lambda l: (l["prioridad"], l["etiqueta"]))
                         if any(p["liga_id"] == l["id"] for p in partidos)]
    return agenda
