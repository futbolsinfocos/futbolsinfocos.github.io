"""Datos inventados para probar el pipeline sin claves. Equipos ficticios a propósito."""
import random


def paquetes_demo(fecha: str) -> list[dict]:
    random.seed(fecha)
    grupos = [
        ({"id": 1, "etiqueta": "Primera Federación · Grupo 1", "competicion": "Primera Federación",
          "grupo": "espana", "prioridad": 1, "pais": "Spain"},
         ["CD Ribera", "UD Montaña", "Atlético Puerto", "SD Valleverde", "Racing Costa",
          "CF Sierra Alta", "Real Llanura", "CD Faro"]),
        ({"id": 2, "etiqueta": "Tercera Federación · Grupo 7", "competicion": "Tercera Federación",
          "grupo": "espana", "prioridad": 3, "pais": "Spain"},
         ["CD Olivar", "AD Meseta", "UD Pinar", "CF Molinos", "Deportivo Arroyo", "SD Encina"]),
        ({"id": 3, "etiqueta": "League One", "competicion": "League One", "grupo": "internacional",
          "prioridad": 2, "pais": "England"},
         ["Northbridge Town", "Eastmoor United", "Kingsford Rovers", "Harbourside City"]),
    ]
    paquetes = []
    for liga, equipos in grupos:
        random.shuffle(equipos)
        partidos = []
        for i in range(0, len(equipos), 2):
            gl, gv = random.randint(0, 4), random.randint(0, 3)
            goles = ([{"min": random.randint(1, 90), "equipo": equipos[i], "jugador": f"Jugador L{n}", "tipo": "Normal Goal"} for n in range(gl)] +
                     [{"min": random.randint(1, 90), "equipo": equipos[i + 1], "jugador": f"Jugador V{n}", "tipo": "Normal Goal"} for n in range(gv)])
            partidos.append({"id": liga["id"] * 100 + i, "fecha": f"{fecha}T17:00:00+01:00",
                             "estadio": f"Estadio de {equipos[i].split()[-1]}", "jornada": "Regular Season - 14",
                             "liga_id": liga["id"], "local": equipos[i], "visitante": equipos[i + 1],
                             "goles_local": gl, "goles_visitante": gv,
                             "goleadores": sorted(goles, key=lambda g: g["min"]) if liga["prioridad"] == 1 else []})
        tabla = [{"pos": n + 1, "equipo": e, "pts": 30 - n * 3, "pj": 14, "dg": 10 - n * 3}
                 for n, e in enumerate(sorted(equipos))]
        paquetes.append({"liga": liga, "fecha": fecha, "partidos": partidos, "clasificacion": tabla})
    return paquetes
