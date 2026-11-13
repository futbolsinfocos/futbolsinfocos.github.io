"""Genera las imágenes para Instagram (1080x1350, formato vertical 4:5).

Estilo "rótulo de tele": negro y amarillo, letra Inter Black cursiva estrechada, bandas inclinadas.
Gráficos propios: sin fotos de agencias ni escudos, para no tener problemas de derechos.
Las fuentes van dentro del repositorio (marca/fuentes) para que salgan igual en GitHub Actions.
"""
from __future__ import annotations

import re
from datetime import date
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ANCHO, ALTO = 1080, 1350
NEGRO, BLANCO, AMARILLO, GRIS = (14, 14, 14), (255, 255, 255), (255, 212, 0), (160, 160, 160)
BARRA, BARRA_GANA = (34, 34, 34), (48, 48, 48)
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre"]
MESES_CORTOS = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]

RAIZ = Path(__file__).resolve().parent.parent
FUENTES = RAIZ / "marca" / "fuentes"
LOGO = RAIZ / "marca" / "logo-sinfocos-SF.png"
TITULAR = "InterDisplay-BlackItalic.otf"
ROTULO = "Inter-ExtraBoldItalic.otf"
TEXTO = "Inter-SemiBoldItalic.otf"
NEGRITA = "Inter-Bold.otf"
POR_TARJETA = 3          # partidos por imagen de resultados
POR_PREVIA = 7           # partidos por imagen de previa


@lru_cache(maxsize=None)
def fuente(nombre: str, tam: int):
    for r in [FUENTES / nombre, Path("/usr/share/fonts/opentype/inter") / nombre,
              Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")]:
        if r.exists():
            return ImageFont.truetype(str(r), tam)
    return ImageFont.load_default(tam)


def fecha_larga(iso: str) -> str:
    d = date.fromisoformat(iso[:10])
    return f"{d.day} de {MESES[d.month - 1]} de {d.year}"


def fecha_corta(iso: str) -> str:
    d = date.fromisoformat(iso[:10])
    return f"{d.day} {MESES_CORTOS[d.month - 1]} {d.year}"


def dia_semana(iso: str) -> str:
    return DIAS[date.fromisoformat(iso[:10]).weekday()]


def ronda(jornada: str | None) -> str:
    """'Regular Season - 14' → 'Jornada 14'; 'Round of 128' → 'Ronda de 128'."""
    if not jornada:
        return ""
    if m := re.search(r"Regular Season\s*-\s*(\d+)", jornada):
        return f"Jornada {m.group(1)}"
    if m := re.search(r"Round of (\d+)", jornada):
        return f"Ronda de {m.group(1)}"
    if m := re.search(r"\s-\s*(\d+)$", jornada):  # 'Group 15 - 11', 'Girone A - 14', 'League A - 5'
        return f"Jornada {m.group(1)}"
    for en, es in [("Quarter-finals", "Cuartos de final"), ("Semi-finals", "Semifinales"), ("Final", "Final"),
                   ("Group Stage", "Fase de grupos"), ("League Stage", "Fase de liga"), ("Play-offs", "Play-off")]:
        if en in jornada:
            return jornada.replace(en, es).replace(" - ", " · ")
    return jornada


# ---------- dibujo ----------

_medidor = ImageDraw.Draw(Image.new("L", (1, 1)))


def ancho_texto(txt: str, tam: int, nombre: str = TITULAR, estrecho: float = 0.80) -> int:
    return int(_medidor.textlength(txt, font=fuente(nombre, tam)) * estrecho)


def texto(img: Image.Image, xy, txt: str, tam: int, color, ancla: str = "l", estrecho: float = 0.80,
          nombre: str = TITULAR, ancho_max: int | None = None) -> int:
    """Texto estrechado en horizontal (look deportivo). Encoge el tamaño si no cabe en ancho_max."""
    while ancho_max and tam > 20 and ancho_texto(txt, tam, nombre, estrecho) > ancho_max:
        tam -= 4
    f = fuente(nombre, tam)
    bb = _medidor.textbbox((0, 0), txt, font=f)
    w, h = bb[2] - bb[0] + 24, bb[3] - bb[1] + 24
    m = Image.new("L", (w, h), 0)
    ImageDraw.Draw(m).text((12 - bb[0], 12 - bb[1]), txt, font=f, fill=255)
    nw = max(1, int(w * estrecho))
    m = m.resize((nw, h), Image.LANCZOS)
    x, y = xy
    x -= {"l": 0, "m": nw // 2, "r": nw}[ancla]
    img.paste(Image.new("RGB", m.size, color), (int(x), int(y - h // 2)), m)
    return nw


def partir(txt: str, tam: int, ancho_max: int, nombre: str = TITULAR, estrecho: float = 0.80) -> list[str]:
    lineas, cur = [], ""
    for p in txt.split():
        t = f"{cur} {p}".strip()
        if ancho_texto(t, tam, nombre, estrecho) <= ancho_max or not cur:
            cur = t
        else:
            lineas.append(cur)
            cur = p
    return lineas + [cur] if cur else lineas


def fondo() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", (ANCHO, ALTO), NEGRO)
    d = ImageDraw.Draw(img)
    for y in range(ALTO):  # degradado sutil hacia abajo
        c = 14 + int(y / ALTO * 10)
        d.line([(0, y), (ANCHO, y)], fill=(c, c, c))
    rayas = Image.new("L", (ANCHO, ALTO), 0)
    dr = ImageDraw.Draw(rayas)
    for x in range(-ALTO, ANCHO, 28):
        dr.line([(x, 0), (x + ALTO, ALTO)], fill=10, width=2)
    img.paste((40, 40, 40), (0, 0), rayas)
    marca = Image.new("L", (ANCHO, ALTO), 0)
    ImageDraw.Draw(marca).text((560, 780), "SF.", font=fuente(TITULAR, 520), fill=14)
    img.paste((60, 60, 60), (0, 0), marca)
    return img, ImageDraw.Draw(img)


def cabecera(img, d, titulo: str, subtitulo: str):
    d.polygon([(0, 60), (760, 60), (720, 150), (0, 150)], fill=AMARILLO)
    texto(img, (70, 105), titulo.upper(), 58, NEGRO, estrecho=0.85, ancho_max=620)
    if subtitulo:
        sub = subtitulo.upper()
        w = min(ancho_texto(sub, 32, ROTULO, 0.9) + 130, ANCHO - 40)
        d.polygon([(0, 150), (w, 150), (w - 20, 200), (0, 200)], fill=BLANCO)
        texto(img, (70, 175), sub, 32, NEGRO, estrecho=0.9, nombre=ROTULO, ancho_max=w - 110)


def pie(img, d, cuenta: str, llamada: str):
    d.polygon([(0, 1240), (ANCHO, 1200), (ANCHO, ALTO), (0, ALTO)], fill=AMARILLO)
    d.rounded_rectangle([60, 1252, 138, 1330], radius=10, fill=NEGRO)
    if LOGO.exists():
        logo = Image.open(LOGO).convert("RGBA").resize((78, 78))
        img.paste(logo, (60, 1252), logo)
    texto(img, (160, 1278), "SIN FOCOS", 40, NEGRO, estrecho=0.85)
    d.text((160, 1302), cuenta, font=fuente(NEGRITA, 24), fill=NEGRO)
    texto(img, (1020, 1290), llamada.upper(), 40, NEGRO, ancla="r", estrecho=0.85)


def guardar(img: Image.Image, destino: Path) -> Path:
    destino.parent.mkdir(parents=True, exist_ok=True)
    img.save(destino, "JPEG", quality=92)
    return destino


def _partes(paquete: dict) -> tuple[str, str]:
    """'Primera Federación · Grupo 1' → ('Primera Federación', 'Grupo 1')"""
    etiqueta = paquete["liga"]["etiqueta"]
    if " · " in etiqueta:
        a, b = etiqueta.split(" · ", 1)
        return a, b
    return etiqueta, ""


def _junta(*partes: str) -> str:
    return " · ".join(p for p in partes if p)


def _ronda(paquete: dict) -> str:
    return ronda(next((p.get("jornada") for p in paquete["partidos"] if p.get("jornada")), None))


def division(p: dict) -> str:
    """'League A - 5' → 'Liga A' (Nations League). Vacío si la competición no tiene divisiones."""
    m = re.match(r"^League ([A-D])\b", p.get("jornada") or "")
    return f"Liga {m.group(1)}" if m else ""


def por_division(partidos: list[dict]) -> list[tuple[str, list[dict]]]:
    """Agrupa los partidos por división (A, B, C, D) manteniendo el orden dentro de cada una."""
    grupos: dict[str, list[dict]] = {}
    for p in partidos:
        grupos.setdefault(division(p), []).append(p)
    return sorted(grupos.items())


# ---------- tarjetas ----------

def dato_resultados(paquete: dict) -> str:
    ps = paquete["partidos"]
    goles = sum((p["goles_local"] or 0) + (p["goles_visitante"] or 0) for p in ps)
    return f"{len(ps)} partido{'s' if len(ps) != 1 else ''} · {goles} gol{'es' if goles != 1 else ''}"


def tarjeta_portada(paquete: dict, titular: str, cuenta: str, destino: Path, dato: str = "",
                    llamada: str = "Desliza ›") -> Path:
    """Primera imagen del carrusel: el titular en grande."""
    titulo, grupo = _partes(paquete)
    img, d = fondo()
    cabecera(img, d, titulo, _junta(grupo, _ronda(paquete), fecha_corta(paquete["fecha"])))
    # quita el prefijo "Competición: " si el titular lo trae
    tit = re.sub(rf"^{re.escape(titulo)}\s*[:·-]\s*", "", titular).upper()
    tam = 128
    while tam > 70:
        lineas = partir(tit, tam, 950)
        if len(lineas) * tam <= 760:
            break
        tam -= 8
    y = 300 + tam // 2
    corte = max(1, len(lineas) // 2)  # primera mitad en blanco, el resto en amarillo
    for i, l in enumerate(lineas):
        texto(img, (66, y), l, tam, AMARILLO if i >= corte else BLANCO, ancho_max=960)
        y += tam
    if dato:
        y += 30
        w = ancho_texto(dato.upper(), 44, TITULAR, 0.85) + 90
        d.polygon([(70, y), (70 + w, y), (50 + w, y + 80), (70, y + 80)], fill=BARRA)
        d.rectangle([70, y, 82, y + 80], fill=AMARILLO)
        texto(img, (105, y + 40), dato.upper(), 44, BLANCO, estrecho=0.85)
    pie(img, d, cuenta, llamada)
    return guardar(img, destino)


def _goleadores(d, p: dict, y: int) -> int:
    items = [f"{g['jugador']} {g['min']}'" + (" (p)" if "Penalty" in (g.get("tipo") or "") else "")
             for g in p.get("goleadores", [])]
    f = fuente(TEXTO, 25)
    lineas, cur = [], ""
    for it in items:
        t = f"{cur}  ·  {it}" if cur else it
        if d.textlength(t, font=f) <= 940 or not cur:
            cur = t
        else:
            lineas.append(cur)
            cur = it
    if cur:
        lineas.append(cur)
    for l in lineas[:2]:
        d.text((60, y), l, font=f, fill=GRIS)
        y += 32
    return y


def tarjetas_resultados(paquete: dict, cuenta: str, carpeta: Path, base: str) -> list[Path]:
    """Marcadores estilo tele, POR_TARJETA partidos por imagen. Primero los de más goles."""
    titulo, grupo = _partes(paquete)
    partidos = sorted(paquete["partidos"], key=lambda p: -((p["goles_local"] or 0) + (p["goles_visitante"] or 0)))
    # cada imagen lleva partidos de una sola división (Nations League: Liga A, B, C, D por separado)
    trozos = [(div, ps[i:i + POR_TARJETA]) for div, ps in por_division(partidos)
              for i in range(0, len(ps), POR_TARJETA)][:7]
    hay_clasif = bool(paquete.get("clasificacion"))
    salida = []
    for n, (div, trozo) in enumerate(trozos, 1):
        img, d = fondo()
        sub = _junta(titulo, grupo, div, _ronda(paquete))
        if len(trozos) > 1:
            sub = _junta(sub, f"{n}/{len(trozos)}")
        cabecera(img, d, "Resultados", sub)
        y = 270
        for p in trozo:
            gl, gv = p["goles_local"], p["goles_visitante"]
            for k, (eq, g, gana) in enumerate([(p["local"], gl, gl > gv), (p["visitante"], gv, gv > gl)]):
                yy = y + k * 92
                d.polygon([(60, yy), (860, yy), (850, yy + 84), (50, yy + 84)], fill=BARRA_GANA if gana else BARRA)
                if gana:
                    d.polygon([(50, yy), (64, yy), (54, yy + 84), (40, yy + 84)], fill=AMARILLO)
                texto(img, (90, yy + 42), eq.upper(), 62, BLANCO if gana or gl == gv else GRIS,
                      estrecho=0.82, ancho_max=740)
                d.polygon([(870, yy), (1030, yy), (1020, yy + 84), (860, yy + 84)], fill=AMARILLO if gana else BLANCO)
                texto(img, (945, yy + 42), str(g), 76, NEGRO, ancla="m", estrecho=0.9)
            y = _goleadores(d, p, y + 196) + 40
        ultima = n == len(trozos)
        llamada = "Desliza ›" if not ultima or hay_clasif else "Crónica en la web"
        pie(img, d, cuenta, llamada)
        salida.append(guardar(img, carpeta / f"{base}-{n + 1}.jpg"))
    return salida


def tarjeta_clasificacion(paquete: dict, cuenta: str, destino: Path) -> Path | None:
    tabla = paquete.get("clasificacion")
    if not tabla:
        return None
    titulo, grupo = _partes(paquete)
    img, d = fondo()
    cabecera(img, d, "Clasificación", _junta(titulo, grupo))
    filas = tabla if len(tabla) <= 12 else tabla[:8] + tabla[-4:]
    alto = min(74, (1180 - 300) // (len(filas) + 1))
    d.text((860, 250), "PJ", font=fuente(ROTULO, 26), fill=GRIS, anchor="mm")
    d.text((965, 250), "PTS", font=fuente(ROTULO, 26), fill=GRIS, anchor="mm")
    y, prev = 280, 0
    for t in filas:
        if t["pos"] - prev > 1:
            d.text((540, y + alto // 3), "· · ·", font=fuente(ROTULO, 30), fill=GRIS, anchor="mm")
            y += alto * 2 // 3
        prev = t["pos"]
        lider = t["pos"] == 1
        d.polygon([(60, y), (1030, y), (1022, y + alto - 8), (52, y + alto - 8)], fill=BARRA_GANA if lider else BARRA)
        d.polygon([(60, y), (140, y), (132, y + alto - 8), (52, y + alto - 8)], fill=AMARILLO if lider else BLANCO)
        texto(img, (96, y + alto // 2 - 4), str(t["pos"]), 44, NEGRO, ancla="m", estrecho=0.9)
        texto(img, (170, y + alto // 2 - 4), t["equipo"].upper(), 44, BLANCO, estrecho=0.82, ancho_max=600)
        d.text((860, y + alto // 2 - 4), str(t["pj"]), font=fuente(ROTULO, 32), fill=GRIS, anchor="mm")
        texto(img, (965, y + alto // 2 - 4), str(t["pts"]), 50, AMARILLO if lider else BLANCO, ancla="m", estrecho=0.9)
        y += alto
    pie(img, d, cuenta, "Crónica en la web")
    return guardar(img, destino)


def _hora(p: dict) -> str:
    return (p.get("fecha") or "")[11:16] or "--:--"


def _paginas_previa(partidos: list[dict]) -> list[list]:
    """Reparte los partidos en imágenes de hasta POR_PREVIA filas, con el rótulo de división delante."""
    paginas, actual = [], []
    for div, ps in por_division(partidos):
        for p in ps:
            if len(actual) >= POR_PREVIA + (1 if div else 0):
                paginas.append(actual)
                actual = []
            if div and (not actual or div not in actual):
                actual.append(div)
            actual.append(p)
    return paginas + [actual] if actual else paginas


def tarjetas_previa(paquete: dict, cuenta: str, carpeta: Path, base: str) -> list[Path]:
    """Previa para Instagram. Un partido: cara a cara. Varios: lista con horas, en tantas imágenes como haga falta.
    La primera imagen se guarda como <base>.jpg (es también la de la web); las siguientes, <base>-2.jpg…"""
    titulo, grupo = _partes(paquete)
    partidos = paquete["partidos"]
    if len(partidos) == 1:
        return [_previa_cara_a_cara(paquete, partidos[0], cuenta, carpeta / f"{base}.jpg")]
    paginas = _paginas_previa(partidos)[:9]
    salida = []
    for n, filas in enumerate(paginas, 1):
        img, d = fondo()
        sub = _junta(titulo, grupo, _ronda(paquete), f"{n}/{len(paginas)}" if len(paginas) > 1 else "")
        cabecera(img, d, "Previa", sub)
        d.text((70, 250), f"{dia_semana(paquete['fecha']).upper()} {fecha_corta(paquete['fecha']).upper()}",
               font=fuente(ROTULO, 30), fill=GRIS)
        alto = min(150, (1180 - 310) // len(filas))
        y = 310 + max(0, (1180 - 310 - alto * len(filas)) // 2)
        for p in filas:
            if isinstance(p, str):  # rótulo de división
                w = ancho_texto(p.upper(), 40, TITULAR, 0.85) + 70
                d.polygon([(60, y + alto - 62), (60 + w, y + alto - 62), (40 + w, y + alto - 14), (60, y + alto - 14)],
                          fill=AMARILLO)
                texto(img, (84, y + alto - 38), p.upper(), 40, NEGRO, estrecho=0.85)
                y += alto
                continue
            h = alto - 14
            d.polygon([(60, y), (1030, y), (1022, y + h), (52, y + h)], fill=BARRA)
            d.polygon([(445, y), (635, y), (627, y + h), (437, y + h)], fill=AMARILLO)
            tam = min(56, h - 30)
            texto(img, (536, y + h // 2), _hora(p), tam + 6, NEGRO, ancla="m", estrecho=0.9)
            texto(img, (415, y + h // 2), p["local"].upper(), tam, BLANCO, ancla="r", estrecho=0.82, ancho_max=340)
            texto(img, (665, y + h // 2), p["visitante"].upper(), tam, BLANCO, estrecho=0.82, ancho_max=340)
            y += alto
        pie(img, d, cuenta, "Desliza ›" if n < len(paginas) else "Previa en la web")
        salida.append(guardar(img, carpeta / (f"{base}.jpg" if n == 1 else f"{base}-{n}.jpg")))
    return salida


def _previa_cara_a_cara(paquete: dict, p: dict, cuenta: str, destino: Path) -> Path:
    titulo, grupo = _partes(paquete)
    img, d = fondo()
    cabecera(img, d, "Previa", _junta(titulo, grupo, division(p), _ronda(paquete)))
    d.polygon([(0, 300), (ANCHO, 260), (ANCHO, 1000), (0, 1040)], fill=(26, 26, 26))
    d.line([(0, 300), (ANCHO, 260)], fill=AMARILLO, width=8)
    d.line([(0, 1040), (ANCHO, 1000)], fill=AMARILLO, width=8)
    texto(img, (540, 450), p["local"].upper(), 210, BLANCO, ancla="m", estrecho=0.78, ancho_max=980)
    d.polygon([(470, 590), (640, 590), (610, 690), (440, 690)], fill=AMARILLO)
    texto(img, (540, 640), "VS", 80, NEGRO, ancla="m", estrecho=0.9)
    texto(img, (540, 830), p["visitante"].upper(), 210, BLANCO, ancla="m", estrecho=0.78, ancho_max=980)
    rotulo = f"{dia_semana(p.get('fecha') or paquete['fecha']).upper()} · {_hora(p)}"
    w = ancho_texto(rotulo, 70, TITULAR, 0.85) + 140
    x0 = 540 - w // 2
    d.polygon([(x0 + 20, 1060), (x0 + w + 20, 1060), (x0 + w, 1160), (x0, 1160)], fill=BLANCO)
    texto(img, (530, 1110), rotulo, 70, NEGRO, ancla="m", estrecho=0.85)
    if p.get("estadio"):
        d.text((540, 1190), p["estadio"].upper(), font=fuente(TEXTO, 28), fill=GRIS, anchor="mm")
    pie(img, d, cuenta, "Previa en la web")
    return guardar(img, destino)


def tarjeta_cierre(cuenta: str, url_web: str, destino: Path) -> Path:
    """Última imagen fija para los posts de una sola imagen (Instagram por Make solo publica carruseles)."""
    img, d = fondo()
    d.polygon([(0, 380), (ANCHO, 330), (ANCHO, 900), (0, 950)], fill=(26, 26, 26))
    d.line([(0, 380), (ANCHO, 330)], fill=AMARILLO, width=8)
    d.line([(0, 950), (ANCHO, 900)], fill=AMARILLO, width=8)
    texto(img, (540, 520), "EL FÚTBOL QUE", 120, BLANCO, ancla="m", estrecho=0.8)
    texto(img, (540, 650), "NO SALE EN LA TELE", 120, AMARILLO, ancla="m", estrecho=0.8, ancho_max=980)
    d.text((540, 800), url_web.replace("https://", "").upper(), font=fuente(ROTULO, 40), fill=BLANCO, anchor="mm")
    texto(img, (540, 1060), "SÍGUENOS · ACTIVA LAS NOTIFICACIONES", 48, GRIS, ancla="m", estrecho=0.85)
    pie(img, d, cuenta, "Enlace en la bio")
    return guardar(img, destino)
