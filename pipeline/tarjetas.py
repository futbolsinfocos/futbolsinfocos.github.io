"""Genera las imágenes para Instagram (1080x1350, formato vertical 4:5).

Gráficos propios: sin fotos de agencias ni escudos, para no tener problemas de derechos.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ANCHO, ALTO = 1080, 1350
FONDO, TINTA, ACENTO, SUAVE = (17, 17, 17), (255, 255, 255), (255, 212, 0), (160, 160, 160)
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre"]

_RUTAS = {
    True: ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/usr/share/fonts/opentype/inter/Inter-Bold.otf",
           "/System/Library/Fonts/Supplemental/Arial Bold.ttf", "C:/Windows/Fonts/arialbd.ttf"],
    False: ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/opentype/inter/Inter-Regular.otf",
            "/System/Library/Fonts/Supplemental/Arial.ttf", "C:/Windows/Fonts/arial.ttf"],
}


def fuente(tam: int, negrita: bool = False):
    for r in _RUTAS[negrita]:
        if Path(r).exists():
            return ImageFont.truetype(r, tam)
    return ImageFont.load_default(tam)


def recortar(d: ImageDraw.ImageDraw, txt: str, f, ancho_max: int) -> str:
    while d.textlength(txt, font=f) > ancho_max and len(txt) > 4:
        txt = txt[:-2].rstrip() + "…" if not txt.endswith("…") else txt[:-2] + "…"
    return txt


def fecha_larga(iso: str) -> str:
    d = date.fromisoformat(iso[:10])
    return f"{d.day} de {MESES[d.month - 1]} de {d.year}"


def _partes(paquete: dict) -> tuple[str, str]:
    """'Primera Federación · Grupo 1' → ('Primera Federación', 'Grupo 1 · ')"""
    etiqueta = paquete["liga"]["etiqueta"]
    if " · " in etiqueta:
        a, b = etiqueta.split(" · ", 1)
        return a, b + " · "
    return etiqueta, ""


def _base(nombre_medio: str, titulo: str, subtitulo: str):
    img = Image.new("RGB", (ANCHO, ALTO), FONDO)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, ANCHO, 14], fill=ACENTO)
    d.text((70, 70), nombre_medio.upper(), font=fuente(30, True), fill=ACENTO)
    f = fuente(64, True)
    d.text((70, 130), recortar(d, titulo, f, ANCHO - 140), font=f, fill=TINTA)
    d.text((70, 215), subtitulo, font=fuente(32), fill=SUAVE)
    d.line([70, 285, ANCHO - 70, 285], fill=SUAVE, width=2)
    return img, d


def tarjeta_resultados(paquete: dict, nombre_medio: str, destino: Path) -> Path:
    titulo, grupo = _partes(paquete)
    img, d = _base(nombre_medio, titulo, grupo + "Resultados · " + fecha_larga(paquete["fecha"]))
    partidos = paquete["partidos"][:9]
    alto_fila = min(110, (ALTO - 420) // max(len(partidos), 1))
    fe, fm = fuente(38, True), fuente(52, True)
    y = 320
    for p in partidos:
        marcador = f"{p['goles_local']} - {p['goles_visitante']}"
        mw = d.textlength(marcador, font=fm)
        cx = ANCHO // 2
        d.rounded_rectangle([cx - mw / 2 - 22, y, cx + mw / 2 + 22, y + 72], 14, fill=ACENTO)
        d.text((cx - mw / 2, y + 6), marcador, font=fm, fill=FONDO)
        izq = recortar(d, p["local"], fe, cx - mw / 2 - 110)
        d.text((cx - mw / 2 - 45 - d.textlength(izq, font=fe), y + 14), izq, font=fe, fill=TINTA)
        d.text((cx + mw / 2 + 45, y + 14), recortar(d, p["visitante"], fe, cx - mw / 2 - 110), font=fe, fill=TINTA)
        y += alto_fila
    if len(paquete["partidos"]) > 9:
        d.text((70, ALTO - 150), f"+{len(paquete['partidos']) - 9} partidos más en la web",
               font=fuente(30), fill=SUAVE)
    if paquete.get("clasificacion"):
        d.text((70, ALTO - 90), "Desliza para ver la clasificación →", font=fuente(30), fill=ACENTO)
    destino.parent.mkdir(parents=True, exist_ok=True)
    img.save(destino, "JPEG", quality=92)
    return destino


def tarjeta_clasificacion(paquete: dict, nombre_medio: str, destino: Path) -> Path | None:
    tabla = paquete["clasificacion"]
    if not tabla:
        return None
    titulo, grupo = _partes(paquete)
    img, d = _base(nombre_medio, titulo, grupo + "Clasificación")
    filas = tabla if len(tabla) <= 12 else tabla[:8] + tabla[-4:]
    f, fb = fuente(36), fuente(36, True)
    d.text((ANCHO - 330, 305), "PJ", font=fuente(26), fill=SUAVE)
    d.text((ANCHO - 190, 305), "PTS", font=fuente(26), fill=SUAVE)
    y, prev = 350, 0
    for t in filas:
        if t["pos"] - prev > 1:
            d.text((70, y - 10), "···", font=f, fill=SUAVE)
            y += 40
        prev = t["pos"]
        if t["pos"] == 1:
            d.rounded_rectangle([55, y - 8, ANCHO - 55, y + 52], 10, outline=ACENTO, width=3)
        d.text((80, y), f"{t['pos']:>2}", font=fb, fill=ACENTO)
        d.text((160, y), recortar(d, t["equipo"], f, ANCHO - 560), font=f, fill=TINTA)
        d.text((ANCHO - 325, y), str(t["pj"]), font=f, fill=SUAVE)
        d.text((ANCHO - 190, y), str(t["pts"]), font=fb, fill=TINTA)
        y += 72
    destino.parent.mkdir(parents=True, exist_ok=True)
    img.save(destino, "JPEG", quality=92)
    return destino


def tarjeta_previa(paquete: dict, nombre_medio: str, destino: Path) -> Path:
    """Partidos del día con su hora: 'Local  18:30  Visitante'."""
    titulo, grupo = _partes(paquete)
    img, d = _base(nombre_medio, titulo, grupo + "Previa · " + fecha_larga(paquete["fecha"]))
    partidos = paquete["partidos"][:9]
    alto_fila = min(110, (ALTO - 420) // max(len(partidos), 1))
    fe, fm = fuente(38, True), fuente(44, True)
    y = 320
    for p in partidos:
        h = p["fecha"][11:16] or "--:--"
        mw = d.textlength(h, font=fm)
        cx = ANCHO // 2
        d.rounded_rectangle([cx - mw / 2 - 22, y, cx + mw / 2 + 22, y + 72], 14, outline=ACENTO, width=4)
        d.text((cx - mw / 2, y + 12), h, font=fm, fill=ACENTO)
        izq = recortar(d, p["local"], fe, cx - mw / 2 - 110)
        d.text((cx - mw / 2 - 45 - d.textlength(izq, font=fe), y + 14), izq, font=fe, fill=TINTA)
        d.text((cx + mw / 2 + 45, y + 14), recortar(d, p["visitante"], fe, cx - mw / 2 - 110), font=fe, fill=TINTA)
        y += alto_fila
    if len(paquete["partidos"]) > 9:
        d.text((70, ALTO - 150), f"+{len(paquete['partidos']) - 9} partidos más en la web", font=fuente(30), fill=SUAVE)
    d.text((70, ALTO - 90), "Previa completa en la web", font=fuente(30), fill=ACENTO)
    destino.parent.mkdir(parents=True, exist_ok=True)
    img.save(destino, "JPEG", quality=92)
    return destino
