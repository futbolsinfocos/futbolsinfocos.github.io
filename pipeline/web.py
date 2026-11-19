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
import zipfile
from datetime import date, datetime, timedelta, timezone
from email.utils import format_datetime
from pathlib import Path

import markdown

from urllib.parse import quote

from .nombres import es
from .previas import dia_partido, jornada_es
from .tarjetas import fecha_larga

RAIZ = Path(__file__).resolve().parent.parent
CONTENIDO = RAIZ / "contenido"
SALIDA = RAIZ / "_site"

FUENTES = ('<link rel="preconnect" href="https://fonts.googleapis.com">'
           '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
           '<link href="https://fonts.googleapis.com/css2?family=Oswald:wght@500;600;700'
           '&family=Inter:wght@400;600;700&family=Source+Serif+4:wght@400;600&display=swap" rel="stylesheet">')

CSS = """
:root{--fondo:#f6f5f1;--panel:#fff;--linea:#e3e1da;--tinta:#151515;--suave:#5f5f5f;--amarillo:#FFD400;--acento:#8a6a00;--negro:#111}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--fondo);color:var(--tinta);font:16px/1.6 Inter,system-ui,sans-serif}
a{color:inherit;text-decoration:none}img{display:block;max-width:100%}
.tit{font-family:Oswald,'Arial Narrow',Impact,sans-serif;text-transform:uppercase;letter-spacing:.01em}
/* Cabecera: barra negra + menú amarillo + tira de resultados */
.top{background:var(--negro);color:#fff}
header{display:flex;align-items:center;gap:14px;max-width:1200px;margin:0 auto;padding:14px 16px}
header .logo{width:44px;height:44px;border-radius:8px;flex:none}
header .n{font-size:30px;line-height:1;font-weight:700}header .l{font-size:12px;color:#aaa;margin-top:3px}
header .hoy{margin-left:auto;font-size:13px;color:#aaa;text-align:right}
nav{background:var(--amarillo);color:var(--negro);overflow-x:auto}
nav .in{max-width:1200px;margin:0 auto;display:flex;gap:24px;padding:10px 16px;white-space:nowrap;
 font:600 15px Oswald,sans-serif;text-transform:uppercase;letter-spacing:.05em}
nav a.on,nav a:hover{text-decoration:underline 3px;text-underline-offset:6px}
.ticker{background:#1d1d1d;color:#eee;overflow:hidden;white-space:nowrap;border-bottom:1px solid #000}
.ticker .in{display:inline-flex;width:max-content;animation:rueda var(--dur,40s) linear infinite}
.ticker:hover .in,.ticker:focus-within .in{animation-play-state:paused}
.ticker .tira{display:inline-flex;gap:26px;padding:7px 13px;font:600 13px Inter,sans-serif}
.ticker .tira>a{display:inline-flex;align-items:center}
@keyframes rueda{from{transform:translateX(0)}to{transform:translateX(-50%)}}
@media (prefers-reduced-motion:reduce){.ticker{overflow-x:auto}.ticker .in{animation:none}.ticker .tira[aria-hidden]{display:none}}
.ticker b{background:var(--amarillo);color:var(--negro);padding:1px 7px;border-radius:3px;margin:0 7px;font-variant-numeric:tabular-nums}
.ticker .lt{font-size:11px;text-transform:uppercase;letter-spacing:.08em;color:var(--amarillo)}
main{max-width:1200px;margin:0 auto;padding:8px 16px 40px}
/* Publicidad */
.ad{display:block;margin:22px auto;text-align:center;overflow:hidden}
.ad .rot{display:block;font:600 10px Inter,sans-serif;text-transform:uppercase;letter-spacing:.14em;color:#9a978c;margin-bottom:4px}
.ad.sup{max-width:970px;min-height:110px}.ad.lat{width:300px;min-height:270px}.ad.alto{width:300px;min-height:620px;position:sticky;top:16px}
.ad.txt{max-width:336px;min-height:270px}.ad.feed{grid-column:1/-1;min-height:140px;margin:0}
.ad.demo ins{text-decoration:none;display:flex!important;flex-direction:column;align-items:center;justify-content:center;height:100%;min-height:inherit;
 background:repeating-linear-gradient(45deg,#ecebe6,#ecebe6 10px,#e4e2db 10px,#e4e2db 20px);border:1px dashed #b9b6ab;color:#8a877c;font-size:12px}
.ad.sup.demo ins{min-height:90px}.ad.lat.demo ins,.ad.txt.demo ins{min-height:250px}.ad.alto.demo ins{min-height:600px}.ad.feed.demo ins{min-height:120px}
/* Etiquetas, secciones, tarjetas */
.tag{display:inline-block;background:var(--amarillo);color:var(--negro);font:700 11px Inter,sans-serif;text-transform:uppercase;letter-spacing:.08em;padding:3px 8px;border-radius:3px}
.sec{font-size:20px;margin:34px 0 16px;display:flex;align-items:center;gap:10px;font-weight:700;border-bottom:3px solid var(--negro);padding-bottom:6px}
h1.sec{font-size:28px}
.cols{display:grid;grid-template-columns:minmax(0,1fr) 300px;gap:36px;align-items:start}
.cols>aside{padding-top:8px}
.hero{display:grid;grid-template-columns:1.25fr 1fr;background:var(--panel);border:1px solid var(--linea);border-radius:6px;overflow:hidden;margin-top:8px}
.hero .foto{background:#111;min-height:300px}.hero .foto img{width:100%;height:100%;object-fit:cover;object-position:top}
.hero .t{padding:24px}.hero h2{font-size:34px;line-height:1.08;margin:12px 0}.hero p{color:var(--suave);margin:0}
.mini{display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-top:20px}
.mini a,.card{background:var(--panel);border:1px solid var(--linea);border-top:4px solid var(--amarillo);border-radius:6px;padding:16px 18px;display:block}
.mini h3{font:600 21px/1.25 'Source Serif 4',Georgia,serif;margin:8px 0 6px}.mini p{color:var(--suave);margin:0;font-size:14px}
a:hover h2,a:hover h3,a:hover strong{text-decoration:underline}
.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:20px}
.card img{display:none}.card div{padding:0}
.card h3{font:600 18px/1.3 'Source Serif 4',Georgia,serif;margin:8px 0 6px;text-transform:none;letter-spacing:0}
.fecha{font-size:13px;color:var(--suave)}
.vacio{background:var(--panel);border:1px solid var(--linea);border-radius:6px;padding:36px 24px;text-align:center;color:var(--suave)}
.bloque{background:var(--panel);border:1px solid var(--linea);border-radius:6px;padding:16px 18px;margin-bottom:22px}
.bloque h3{font:700 16px Oswald,sans-serif;text-transform:uppercase;margin:0 0 4px;border-bottom:3px solid var(--amarillo);padding-bottom:6px}
.lista a{display:block;padding:11px 0;border-bottom:1px solid var(--linea)}.lista a:last-child{border:0}
.lista small{color:var(--suave);font-size:11px;text-transform:uppercase;letter-spacing:.07em}
.lista strong{display:block;font:600 16px/1.3 'Source Serif 4',Georgia,serif;margin-top:3px}
.bloque.negro{background:var(--negro);color:#fff;border:0}.bloque.negro h3{color:#fff}.bloque.negro p{color:#ccc;font-size:14px}
.bloque.negro a{display:inline-block;background:var(--amarillo);color:#000;font-weight:700;padding:8px 14px;border-radius:4px;font-size:14px}
/* Artículo */
article{background:var(--panel);border:1px solid var(--linea);border-radius:6px;padding:30px 36px;margin-top:8px}
article h1{font-size:clamp(28px,4.5vw,44px);line-height:1.06;margin:14px 0 10px}
article .entradilla{font:400 21px/1.5 'Source Serif 4',Georgia,serif;color:#333;margin:10px 0 16px}
article .firma-art{font-size:13px;color:var(--suave);border-top:1px solid var(--linea);border-bottom:1px solid var(--linea);padding:9px 0;margin-bottom:22px}
article .firma-art b{color:var(--tinta)}
article .fotos{display:flex;gap:12px;overflow-x:auto;margin:0 0 22px}
article .fotos img{width:min(100%,460px);flex:none;border-radius:4px}
article>p,article .cuerpo p,article li{font:400 19px/1.75 'Source Serif 4',Georgia,serif;margin:0 0 16px}
article h2{font:700 22px Oswald,sans-serif;text-transform:uppercase;margin:32px 0 10px;border-left:5px solid var(--amarillo);padding-left:10px;scroll-margin-top:16px}
article strong{color:var(--negro)}
.volver{display:inline-block;margin-top:26px;color:var(--acento);font-weight:700}
.migas{font-size:13px;color:var(--suave);margin:16px 0 4px}.migas a:hover{text-decoration:underline}
table{border-collapse:collapse;width:100%;font-size:15px;margin:10px 0 20px}
td,th{border-bottom:1px solid var(--linea);padding:7px 8px;text-align:left}th{color:var(--suave);font-weight:600}
/* Partidos y resultados */
.dia{margin-bottom:30px}.dia>h2{font-size:20px;color:var(--negro);margin:26px 0 12px}
.comp{margin:0 0 18px;background:var(--panel);border:1px solid var(--linea);border-radius:6px;padding:14px 18px}
.comp h3{font-size:17px;margin:0 0 8px}.comp h3 a{color:var(--acento)}.comp h3 a:hover{text-decoration:underline}
.partido{display:grid;grid-template-columns:1fr auto 1fr;gap:12px;align-items:center;padding:8px 0;border-top:1px solid var(--linea)}
.partido .l{text-align:right}
.partido b{background:var(--negro);color:var(--amarillo);border-radius:4px;padding:2px 9px;font-variant-numeric:tabular-nums;white-space:nowrap}
.partido b.hora{background:none;color:var(--negro);border:2px solid var(--negro)}
.ligas{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:14px}
.ligas a{background:var(--panel);border:1px solid var(--linea);border-left:4px solid var(--amarillo);border-radius:6px;padding:14px 18px;display:block}
.ligas a span{font-size:19px;font-weight:600;display:block}.ligas a:hover span{text-decoration:underline}.ligas small{color:var(--suave)}
.pais{font-size:20px;margin:26px 0 12px}
.liga{display:grid;grid-template-columns:1fr 1fr;gap:24px}.res3{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:0 18px}.pos{color:var(--acento)}
/* Escudos pequeños junto a los nombres */
.esc{width:20px;height:20px;object-fit:contain;vertical-align:middle;flex:none}
.partido .l,.partido>span:last-child{display:flex;align-items:center;gap:8px}.partido .l{justify-content:flex-end}
.ticker .esc{width:16px;height:16px;margin:0 6px;background:#fff;border-radius:50%;padding:1px}
/* Clasificación */
.tabla-wrap{overflow-x:auto;background:var(--panel);border:1px solid var(--linea);border-radius:6px;padding:6px 10px;margin:0 0 18px}
table.clas{margin:0;font-size:14px;font-variant-numeric:tabular-nums}
table.clas th,table.clas td{text-align:center;padding:7px 6px;white-space:nowrap;vertical-align:middle}
table.clas th.eq,table.clas td.eq{text-align:left;width:100%}
table.clas td.eq span{display:inline-flex;align-items:center;gap:8px;vertical-align:middle;line-height:1.2}
table.clas td.pts{font-weight:800;font-size:15px}
table.clas td.p{border-left:4px solid transparent;font-weight:700}
table.clas tr.ascenso td.p{border-left-color:#1f9d55}table.clas tr.playoff td.p{border-left-color:#2b6cb0}
table.clas tr.descenso td.p{border-left-color:#c53030}
table.clas tr.resalta td{background:#fff6c7}
.forma{display:inline-flex;gap:3px}.forma i{font:700 10px Inter,sans-serif;font-style:normal;width:17px;height:17px;line-height:17px;border-radius:3px;color:#fff;text-align:center}
.forma .W{background:#1f9d55}.forma .D{background:#8a8a8a}.forma .L{background:#c53030}
.leyenda{display:flex;flex-wrap:wrap;gap:14px;font-size:12px;color:var(--suave);margin:-8px 0 18px}
.leyenda span:before{content:"";display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:5px;vertical-align:-1px}
.leyenda .ascenso:before{background:#1f9d55}.leyenda .playoff:before{background:#2b6cb0}.leyenda .descenso:before{background:#c53030}
.est-liga{display:grid;grid-template-columns:1fr 1fr;gap:24px}
table.clas td.jug{text-align:left;width:100%}table.clas td.jug small{display:inline-flex;align-items:center;gap:5px;color:var(--suave);font-size:12px;margin-left:6px}
table.clas .am:before,table.clas .ro:before{content:"";display:inline-block;width:10px;height:14px;border-radius:2px;margin-right:5px;vertical-align:-2px}
table.clas .am:before{background:#f4c400}table.clas .ro:before{background:#d22}
.stats{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:14px;margin:6px 0 10px}
.stat{background:var(--panel);border:1px solid var(--linea);border-radius:6px;padding:12px 14px;font:500 13px Inter,sans-serif}
.stat h3{display:flex;align-items:center;justify-content:center;gap:8px;font:700 15px Inter,sans-serif;margin:0 0 10px;text-transform:none;border:0;padding:0}
.stat h3 b{background:var(--negro);color:var(--amarillo);border-radius:4px;padding:1px 8px}
.st{display:grid;grid-template-columns:34px 1fr 34px;align-items:center;gap:8px;margin:7px 0}
.st span:first-child{text-align:right;font-weight:700}.st span:last-child{font-weight:700}
.st div{position:relative}.st div small{display:block;text-align:center;color:var(--suave);font-size:11px;margin-bottom:3px}
.st div i{display:flex;height:6px;border-radius:3px;overflow:hidden;background:#e4e4e4}
.st div i b{background:var(--negro)}.st div i b+b{background:var(--amarillo)}
.mini-clas{margin:30px 0 10px}.mini-clas h2{margin-top:0}.mini-clas a.todo{display:inline-block;margin-top:8px;color:var(--acento);font-weight:700;font-size:15px}
.lt-p{display:block;font:700 11px Inter,sans-serif;text-transform:uppercase;letter-spacing:.08em;color:var(--acento);margin:12px 0 4px}
.lt-p:first-child{margin-top:0}
.partido .centro{display:flex;flex-direction:column;align-items:center;gap:5px}
.btn-previa{display:inline-block;font:700 11px Inter,sans-serif;text-transform:uppercase;letter-spacing:.06em;
 color:var(--negro);background:var(--amarillo);padding:3px 9px;border-radius:99px}.btn-previa:hover{background:var(--negro);color:var(--amarillo)}
.fG{background:#3ec46d}.fE{background:#bdbdbd}.fP{background:#e5534b}
/* Previa de un partido */
.pp{background:var(--panel);border:1px solid var(--linea);border-radius:6px;padding:26px 32px;margin-top:8px}
.pp .miga{font:500 13px Oswald,sans-serif;text-transform:uppercase;letter-spacing:.08em;color:var(--acento)}
.pp .miga span{color:var(--suave)}
.pp h1{font-size:clamp(28px,4.6vw,46px);line-height:1.06;margin:12px 0 14px}
.pp .entr{font:400 clamp(18px,2.4vw,21px)/1.5 'Source Serif 4',Georgia,serif;color:#333;margin:0 0 18px}
.pp .firma{display:flex;flex-wrap:wrap;gap:8px 14px;align-items:center;justify-content:space-between;font-size:13px;color:var(--suave);
 border-top:1px solid var(--linea);border-bottom:1px solid var(--linea);padding:10px 0;margin-bottom:24px}
.pp .firma b{color:var(--tinta)}
.comparte{display:flex;gap:8px}.comparte a,.comparte button{font:700 12px Inter,sans-serif;border-radius:99px;padding:6px 12px;
 border:1px solid var(--linea);background:var(--fondo);color:var(--tinta);cursor:pointer}
.comparte a:hover,.comparte button:hover{border-color:var(--negro)}
.marcador{display:grid;grid-template-columns:1fr auto 1fr;align-items:center;gap:10px;background:var(--negro);color:#fff;border-radius:8px;padding:20px 26px;margin-bottom:28px}
.marcador .eq{display:flex;align-items:center;gap:14px;font:700 clamp(17px,2.6vw,26px)/1.1 Oswald,sans-serif;text-transform:uppercase}
.marcador .eq.v{flex-direction:row-reverse;text-align:right}
.escudo{position:relative;flex:none;width:58px;height:58px;border-radius:50%;background:#2a2a2a;color:var(--amarillo);
 display:flex;align-items:center;justify-content:center;font:700 18px Oswald,sans-serif}
.escudo img{position:absolute;inset:0;width:100%;height:100%;object-fit:contain;background:#fff;border-radius:50%;padding:4px}
.marcador .hora{text-align:center;padding:0 10px}.marcador .hora b{display:block;font:700 clamp(28px,4vw,40px)/1 Oswald,sans-serif;color:var(--amarillo)}
.marcador .hora span{font-size:12px;color:#bbb;text-transform:uppercase;letter-spacing:.08em}
.pp .cols{grid-template-columns:minmax(0,1fr) 300px;gap:36px}
.pp .texto p{font:400 19px/1.75 'Source Serif 4',Georgia,serif;color:#222;margin:0 0 20px}
.pp .texto .cap{float:left;font:700 60px/.85 Oswald,sans-serif;color:var(--negro);margin:6px 8px 0 0;border-bottom:5px solid var(--amarillo)}
.pp .texto h2{font:700 22px Oswald,sans-serif;text-transform:uppercase;margin:30px 0 12px;border-left:5px solid var(--amarillo);padding-left:10px}
.claves{list-style:none;padding:0;margin:0}.claves li{border-left:4px solid var(--amarillo);padding:10px 16px;margin-bottom:12px;
 background:var(--fondo);font-size:16px;line-height:1.5}.claves b{color:var(--negro)}
.eldato{background:var(--negro);color:#fff;border-radius:6px;padding:16px 20px;margin:6px 0 24px;font:600 17px/1.45 Inter,sans-serif}
.eldato b{display:block;font:700 13px Oswald,sans-serif;letter-spacing:.1em;text-transform:uppercase;color:var(--amarillo);margin-bottom:4px}
.cara{width:100%;border-collapse:collapse;font:500 14px Inter,sans-serif;font-variant-numeric:tabular-nums;margin:0}
.cara td{padding:7px 4px;border-bottom:1px solid var(--linea);text-align:center;width:30%}
.cara td.k{width:40%;color:var(--suave);font-size:12px;text-transform:uppercase;letter-spacing:.04em}
.cara tr.cab td{font-weight:700;border-bottom:2px solid var(--negro)}.cara tr.cab img{width:30px;height:30px;object-fit:contain;display:block;margin:0 auto 4px}
.cara td.mejor{font-weight:800;background:#fff6c7}
.cara .forma i{width:15px;height:15px;line-height:15px;font-size:9px}
.h2h{list-style:none;padding:0;margin:0;font-size:14px}.h2h li{padding:7px 0;border-bottom:1px solid var(--linea)}.h2h small{display:block;color:var(--suave);font-size:12px}
.goles{display:grid;grid-template-columns:1fr 1fr;gap:4px 24px;font-size:14px;color:#ddd;margin:-14px 0 26px;background:var(--negro);border-radius:0 0 8px 8px;padding:0 26px 16px}
.goles div:last-child{text-align:right}
.estrella{display:block;background:var(--negro);color:#fff;border-radius:6px;padding:16px 20px;margin:0 0 24px;border-left:6px solid var(--amarillo)}
.estrella small{font:700 12px Oswald,sans-serif;letter-spacing:.1em;text-transform:uppercase;color:var(--amarillo)}
.estrella strong{display:block;font:700 21px/1.2 Oswald,sans-serif;margin:4px 0}.estrella span{color:#ccc;font-size:14px}
.estrella:hover strong{text-decoration:underline}
.pp aside .caja{background:var(--fondo);border:1px solid var(--linea);border-radius:6px;padding:16px 18px;margin-bottom:18px}
.pp aside h3{font:700 16px Oswald,sans-serif;text-transform:uppercase;letter-spacing:.06em;margin:0 0 8px;border-bottom:3px solid var(--amarillo);padding-bottom:6px}
.dato{display:flex;justify-content:space-between;gap:12px;font-size:14px;padding:8px 0;border-bottom:1px solid var(--linea);text-align:right}
.dato:last-child{border:0}.dato span{color:var(--suave);text-align:left}
.racha{display:flex;justify-content:space-between;align-items:center;gap:10px;font-size:14px;margin:10px 0}
.racha i{display:inline-block;width:24px;height:24px;line-height:24px;text-align:center;border-radius:4px;font:700 12px Inter,sans-serif;
 font-style:normal;color:#111;margin-left:3px}
.pp .nota{font-size:12px;color:var(--suave);margin:6px 0 0}
.mas{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:14px}
.mas a{background:var(--fondo);border:1px solid var(--linea);border-left:4px solid var(--amarillo);border-radius:6px;padding:12px 16px;display:block}
.mas small{color:var(--acento);font-weight:700}.mas strong{display:block;font:600 17px/1.2 Oswald,sans-serif;text-transform:uppercase;margin:4px 0}
.mas span{font-size:14px;color:var(--suave)}
/* Noticias */
.notis{display:grid;grid-template-columns:repeat(3,1fr);gap:20px}
.notis a{background:var(--panel);border:1px solid var(--linea);border-top:4px solid var(--negro);border-radius:6px;padding:16px 18px;display:block}
.notis small{color:var(--acento);font:700 11px Inter,sans-serif;text-transform:uppercase;letter-spacing:.08em}
.notis strong{display:block;font:600 18px/1.3 'Source Serif 4',Georgia,serif;margin:6px 0}
.notis span{font-size:14px;color:var(--suave)}
.fuente{background:var(--fondo);border-left:4px solid var(--amarillo);border-radius:4px;padding:12px 16px;font-size:14px;color:var(--suave);margin:26px 0 0}
.fuente a{color:var(--acento);font-weight:600}
/* Regionales */
.regs{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}
.rg{background:var(--panel);border:1px solid var(--linea);border-radius:6px;padding:16px 18px;display:block}
a.rg:hover{border-color:var(--negro)}
.rgt{display:flex;justify-content:space-between;align-items:center;gap:8px;margin-bottom:12px}
.rgt small{color:var(--suave);font-size:12px;text-align:right}
.rgm{display:grid;grid-template-columns:1fr auto 1fr;gap:10px;align-items:center;font:600 17px/1.15 Oswald,sans-serif;text-transform:uppercase}
.rgm span:first-child{text-align:right}
.rgm b{background:var(--negro);color:var(--amarillo);border-radius:4px;padding:2px 8px;font-size:14px;white-space:nowrap}
.rgm b.hora{background:none;border:2px solid var(--negro);color:var(--negro)}
.rg p{color:var(--suave);font-size:14px;margin:12px 0 0;text-align:center}
.regcab{display:flex;justify-content:space-between;align-items:end;gap:12px;flex-wrap:wrap;margin:-6px 0 14px;color:var(--suave);font-size:14px}
.regcab a{color:var(--acento);font-weight:700}
.rgart{background:var(--panel);border:1px solid var(--linea);border-radius:6px;padding:20px 22px;margin-bottom:16px;scroll-margin-top:16px}
.rgart h3{font-size:24px;line-height:1.15;margin:10px 0 6px}.rgart .rgm{margin:14px 0}
.rgart .txt{font:400 18px/1.7 'Source Serif 4',Georgia,serif;color:#222;margin:10px 0 0}
.rgart .firma{font-size:13px;color:var(--suave);margin-top:10px}.rgart .firma b{color:var(--tinta)}
.llamada{background:var(--negro);color:#fff;border-radius:6px;padding:22px 24px;margin:8px 0 26px}
.llamada h2{font:700 24px/1.1 Oswald,sans-serif;text-transform:uppercase;margin:0 0 6px;color:var(--amarillo)}.llamada p{margin:0 0 12px;color:#ddd}
.llamada a{display:inline-block;background:var(--amarillo);color:var(--negro);font-weight:700;padding:8px 16px;border-radius:4px}
/* Más fútbol (segundo plano) */
.sec.peq{font-size:17px;color:var(--suave);border-bottom-width:2px;border-color:var(--linea)}
.franja{display:flex;gap:10px;overflow-x:auto;padding-bottom:6px}
.franja a{flex:none;background:var(--panel);border:1px solid var(--linea);border-radius:6px;padding:10px 14px;min-width:170px}
.franja small{display:block;color:var(--suave);font-size:11px;text-transform:uppercase;letter-spacing:.06em}
.franja span{font-weight:600;font-size:14px}.franja a:hover{border-color:var(--negro)}
/* Páginas legales */
.legal{background:var(--panel);border:1px solid var(--linea);border-radius:6px;padding:30px 36px;max-width:820px;margin:16px auto}
.legal h1{font:700 34px Oswald,sans-serif;text-transform:uppercase;margin:0 0 6px}
.legal h2{font:700 20px Oswald,sans-serif;text-transform:uppercase;margin:28px 0 6px}
.legal .act{color:var(--suave);font-size:14px}.legal a{color:var(--acento);text-decoration:underline}
.legal table td,.legal table th{border:1px solid var(--linea);vertical-align:top}
.pendiente{background:#fff3a3;padding:0 4px;border-radius:3px}
/* Pie */
footer{background:var(--negro);color:#bbb;font-size:14px;margin-top:30px}
footer .in{max-width:1200px;margin:0 auto;padding:34px 16px;display:grid;grid-template-columns:1.5fr 1fr 1fr;gap:30px}
footer h4{color:#fff;font:700 15px Oswald,sans-serif;text-transform:uppercase;margin:0 0 10px}
footer .in a{display:block;margin:5px 0}footer a:hover{color:var(--amarillo)}footer .ig{color:var(--amarillo);font-weight:600}
footer .bajo{border-top:1px solid #2a2a2a;text-align:center;padding:14px 16px;font-size:12px;color:#888;line-height:1.6}
@media(max-width:900px){.cols,.pp .cols{grid-template-columns:minmax(0,1fr)}.cols>*{min-width:0}.cols>aside .ad.alto{display:none}.grid,.notis,.regs{grid-template-columns:1fr 1fr}
 .hero{grid-template-columns:1fr!important}.hero .foto{display:none}footer .in{grid-template-columns:1fr 1fr}
 .pp aside{order:-1}}
@media(max-width:640px){.grid,.notis,.regs,.mini,.liga{grid-template-columns:1fr}header .hoy{display:none}
 .hero h2{font-size:27px}.hero .t{padding:18px}article,.pp,.legal{padding:20px 18px}article>p,article .cuerpo p,.pp .texto p{font-size:18px}
 table.clas .sm{display:none}.est-liga{grid-template-columns:1fr}
 .marcador{padding:16px 12px;gap:6px}.escudo{width:42px;height:42px;font-size:14px}.marcador .eq,.marcador .eq.v{flex-direction:column;text-align:center;gap:8px}
 footer .in{grid-template-columns:1fr}}
"""

NAV = [("index.html", "Portada"), ("ligas/primera-federacion.html", "1ª Federación"),
       ("ligas/segunda-federacion.html", "2ª Federación"), ("ligas/tercera-federacion.html", "3ª Federación"),
       ("regionales.html", "Regionales"), ("partidos.html", "Partidos"), ("resultados.html", "Resultados"),
       ("mas-futbol.html", "Más fútbol"), ("ligas.html", "Ligas")]


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
            piezas.append(f'<a href="{prof}articulos/{a["slug"]}.html">{_esc(p["local"], p.get("escudo_local"))}{_e(es(p["local"]))}'
                          f'<b>{p["goles_local"]} - {p["goles_visitante"]}</b>{_e(es(p["visitante"]))}'
                          f'{_esc(p["visitante"], p.get("escudo_visitante"))}</a>')
    # La tira se repite dos veces y se desplaza en bucle: al llegar a la mitad vuelve al principio
    # sin que se note. Velocidad constante: ~3 s por elemento.
    tira = "".join(piezas)
    segundos = max(20, round(len(piezas) * 3.2))
    return (f'<div class="ticker" style="--dur:{segundos}s"><div class="in">'
            f'<div class="tira">{tira}</div><div class="tira" aria-hidden="true">{tira}</div></div></div>')


def _hoy_largo() -> str:
    d = datetime.now(timezone(timedelta(hours=1))).date()
    return f"{DIAS[d.weekday()].capitalize()}, {fecha_larga(d.isoformat())}"


def _pagina(cfg: dict, titulo: str, cuerpo: str, prof: str = "", descripcion: str = "",
            activa: str = "", ticker: str = "", lateral: str | None = None) -> str:
    """Plantilla común. Si se pasa `lateral`, el contenido va a dos columnas con la barra lateral a la derecha."""
    m = cfg["medio"]
    usuario, url_ig = _instagram(cfg)
    nav = "".join(f'<a href="{prof}{h}"{" class=on" if h == activa else ""}>{t}</a>' for h, t in NAV)
    ig = f'<a class="ig" href="{url_ig}" rel="noopener">Instagram @{_e(usuario)}</a>' if usuario else ""
    corr = (cfg.get("regionales") or {}).get("formulario_url")
    if lateral is not None:
        cuerpo = f'<div class="cols"><div>{cuerpo}</div><aside>{lateral}</aside></div>'
    sup = _anuncio(cfg, "superior", "sup")
    return f"""<!doctype html><html lang="{m['idioma']}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{_e(titulo)}</title><meta name="description" content="{_e(descripcion or m['lema'])}">
<meta name="theme-color" content="#111111"><link rel="icon" href="{prof}img/logo.png">
<meta property="og:title" content="{_e(titulo)}"><meta property="og:description" content="{_e(descripcion or m['lema'])}">
<meta property="og:site_name" content="{_e(m['nombre'])}"><meta property="og:image" content="{_e(m['url_web'].rstrip('/'))}/img/logo.png">
<link rel="alternate" type="application/rss+xml" href="{prof}rss.xml">{FUENTES}{_script_analitica()}{_script_adsense(cfg)}<style>{CSS}</style></head><body>
<div class="top"><header><a href="{prof}index.html"><img class="logo" src="{prof}img/logo.png" alt="{_e(m['nombre'])}"></a>
<a href="{prof}index.html"><div class="n tit">{_e(m['nombre'])}</div><div class="l">{_e(m['lema'])}</div></a>
<div class="hoy">{_hoy_largo()}</div></header></div>
<nav><div class="in">{nav}</div></nav>
{ticker}
<main>{sup}{cuerpo}</main>
<footer><div class="in"><div><h4>{_e(m['nombre'])}</h4>Periódico digital de fútbol de Primera, Segunda y Tercera Federación y del fútbol
regional, con Hypermotion y las grandes ligas en segundo plano. Crónicas, previas y resultados cada día.<br><br>{ig}</div>
<div><h4>El periódico</h4><a href="{prof}quienes-somos.html">Quiénes somos</a>
{f'<a href="{_e(corr)}" rel="noopener">Hazte corresponsal</a>' if corr else ""}
<a href="{prof}contacto.html">Contacto</a><a href="{prof}rss.xml">RSS</a></div>
<div><h4>Legal</h4><a href="{prof}aviso-legal.html">Aviso legal</a><a href="{prof}privacidad.html">Política de privacidad</a>
<a href="{prof}cookies.html">Política de cookies</a>
<a href="#" onclick="return sfCookies()">Configurar cookies</a></div></div>
<div class="bajo">© {date.today().year} {_e(m['nombre'])} · Datos de partidos: API-Football. Crónicas elaboradas a partir de esos datos y revisadas
por la redacción. Las noticias de otros medios enlazan siempre a su fuente. ¿Ves un error? Escríbenos y lo corregimos.</div></footer>
{_aviso_cookies(prof)}</body></html>"""


# ── Contador de visitas (Google Analytics 4) ─────────────────────────────────
# Sale de config.yaml → analitica.id (G-…). Vacío = no se cuenta nada.
# Modo de consentimiento de Google: por defecto todo DENEGADO en todas las visitas; solo se
# guardan cookies de Analytics si la persona acepta. Mientras no haya AdSense (y por tanto no
# haya aviso de Google), la web enseña su propio aviso sencillo (_aviso_cookies). Cuando
# haya AdSense, el aviso de Google se encarga y el nuestro desaparece solo.
ANALITICA: dict = {}


def _script_analitica() -> str:
    gid = (ANALITICA.get("id") or "").strip()
    if not gid:
        return ""
    return (f'<script async src="https://www.googletagmanager.com/gtag/js?id={_e(gid)}"></script><script>'
            'window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments)}'
            "gtag('consent','default',{ad_storage:'denied',ad_user_data:'denied',ad_personalization:'denied',"
            "analytics_storage:'denied',wait_for_update:500});"
            "try{if(localStorage.getItem('sf_cookies')==='si')gtag('consent','update',{analytics_storage:'granted'})}catch(e){}"
            f"gtag('js',new Date());gtag('config','{_e(gid)}');</script>")


def _aviso_cookies(prof: str = "") -> str:
    """Función «Configurar cookies» y, si no está activo el aviso de Google (CMP) pero sí Analytics, un aviso propio Aceptar/Rechazar."""
    # Mientras el aviso de Google (CMP) no esté publicado en AdSense, seguimos con el aviso propio.
    cmp_google = bool(PUBLI.get("cliente")) and bool(PUBLI.get("cmp_activo"))
    propio = bool((ANALITICA.get("id") or "").strip()) and not cmp_google
    js = ("<script>function sfCookies(){if(window.googlefc&&googlefc.callbackQueue){"
          "googlefc.callbackQueue.push(googlefc.showRevocationMessage)}else{var a=document.getElementById('sfck');"
          "if(a)a.style.display='flex'}return false}")
    if not propio:
        return js + "</script>"
    return ('<div id="sfck" style="display:none;position:fixed;left:0;right:0;bottom:0;z-index:99;background:#111;color:#fff;'
            'padding:14px 16px;gap:12px;align-items:center;justify-content:center;flex-wrap:wrap;font:15px/1.4 system-ui,sans-serif">'
            f'<span style="max-width:640px">Usamos cookies de Google Analytics para contar las visitas, solo si nos dejas. '
            f'<a href="{prof}cookies.html" style="color:#ffd400">Más información</a></span>'
            '<span style="display:flex;gap:8px"><button onclick="sfElige(0)" style="padding:9px 16px;border:1px solid #fff;'
            'background:none;color:#fff;font-weight:700;cursor:pointer">Rechazar</button>'
            '<button onclick="sfElige(1)" style="padding:9px 16px;border:0;background:#ffd400;color:#111;font-weight:700;'
            'cursor:pointer">Aceptar</button></span></div>'
            + js +
            "function sfElige(s){try{localStorage.setItem('sf_cookies',s?'si':'no')}catch(e){}"
            "if(window.gtag)gtag('consent','update',{analytics_storage:s?'granted':'denied'});"
            "document.getElementById('sfck').style.display='none'}"
            "var sfv=null;try{sfv=localStorage.getItem('sf_cookies')}catch(e){}"
            "if(!sfv)document.getElementById('sfck').style.display='flex'</script>")


# ── Publicidad (Google AdSense) ──────────────────────────────────────────────
# Todo sale de config.yaml → publicidad. Sin `cliente` (ca-pub-…) no se pinta nada:
# la web queda igual que sin anuncios. Con `muestra: true` se ven los huecos en gris (para revisar).
PUBLI: dict = {}


def _script_adsense(cfg: dict) -> str:
    cli = PUBLI.get("cliente")
    if not cli:
        return ""
    return (f'<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client={_e(cli)}" '
            'crossorigin="anonymous"></script>')


def _anuncio(cfg: dict, hueco: str, clase: str) -> str:
    """Un hueco de anuncio. Solo aparece si hay cliente de AdSense y código para ese hueco (o en modo muestra)."""
    cli, slot = PUBLI.get("cliente"), (PUBLI.get("huecos") or {}).get(hueco)
    if PUBLI.get("muestra") and not (cli and slot):
        return (f'<div class="ad {clase} demo"><span class="rot">Publicidad</span>'
                f'<ins>Hueco «{_e(hueco)}»</ins></div>')
    if not (cli and slot):
        return ""
    return (f'<div class="ad {clase}"><span class="rot">Publicidad</span><ins class="adsbygoogle" style="display:block" '
            f'data-ad-client="{_e(cli)}" data-ad-slot="{_e(str(slot))}" data-ad-format="auto" data-full-width-responsive="true"></ins>'
            '<script>(adsbygoogle=window.adsbygoogle||[]).push({});</script></div>')


def _lateral(cfg: dict, arts: list[dict], prof: str = "", titulo: str = "Previas", con_alto: bool = True) -> str:
    """Barra lateral: anuncio, lista de artículos, anuncio alto fijo y llamada a corresponsales."""
    lista = "".join(f'<a href="{_url(a, prof)}"><small>{_e(_etiqueta(a))}</small><strong>{_e(a["titular"])}</strong></a>'
                    for a in arts[:6])
    out = _anuncio(cfg, "lateral", "lat")
    if lista:
        out += f'<div class="bloque"><h3>{_e(titulo)}</h3><div class="lista">{lista}</div></div>'
    if con_alto:
        out += _anuncio(cfg, "lateral_alto", "alto")
    url = (cfg.get("regionales") or {}).get("formulario_url")
    if url:
        out += ('<div class="bloque negro"><h3>Hazte corresponsal</h3><p>¿Sigues a tu equipo de Regional cada domingo? '
                f'Cuéntanos el partido y lo publicamos con tu firma.</p><a href="{_e(url)}" rel="noopener">Quiero escribir</a></div>')
    return out


NOTICIAS: list[dict] = []  # se rellena en construir()
LIGAS: set[str] = set()  # etiquetas con página propia en ligas/


def cargar_noticias() -> list[dict]:
    carpeta = CONTENIDO / "noticias"
    ns = [json.loads(p.read_text()) for p in carpeta.glob("*.json")] if carpeta.exists() else []
    # las de fin de semana y las de datos delante dentro del mismo día; luego las de otros medios
    return sorted(ns, key=lambda n: (n["fecha"], n.get("origen") == "datos", n["slug"]), reverse=True)


def _noticias_de(etiqueta: str | None = None, competicion: str | None = None, grupo: str | None = None) -> list[dict]:
    return [n for n in NOTICIAS if (etiqueta is None or n["etiqueta"] == etiqueta)
            and (competicion is None or n.get("competicion") == competicion)
            and (grupo is None or n.get("grupo") == grupo)]


def _bloque_noticias(lista: list[dict], prof: str = "", titulo: str = "Últimas noticias") -> str:
    if not lista:
        return ""
    return (f'<h2 class="sec tit">{titulo}</h2><section class="notis">' + "".join(
        f'<a href="{_url(n, prof)}"><small>{_e(_etiqueta(n))}</small><strong>{_e(n["titular"])}</strong>'
        f'<span>{_e(n["entradilla"])}</span></a>' for n in lista) + "</section>")


def _tarjeta(a: dict, prof: str, cabecera: str) -> str:
    return (f'<a class="card" href="{_url(a, prof)}"><div>{cabecera}'
            f'<h3>{_e(a["titular"])}</h3><span class="fecha">{fecha_larga(a["fecha"])}</span></div></a>')


def cargar_articulos() -> list[dict]:
    arts = [json.loads(p.read_text()) for p in (CONTENIDO / "articulos").glob("*.json")]
    return sorted(arts, key=_orden, reverse=True)


def _orden(a: dict) -> tuple:
    """Más nuevo primero. Cada edición trae las crónicas de ayer y las previas de hoy:
    las crónicas van delante y las previas justo detrás, dentro de la misma edición."""
    previa = a.get("tipo") == "previa"
    d = date.fromisoformat(a["fecha"]) - timedelta(days=1 if previa else 0)
    return (d.isoformat(), 0 if previa else 1, -a.get("prioridad", 3))


def _etiqueta(a: dict) -> str:
    if a.get("tipo") == "noticia":
        return f'{a["categoria"]} · {a["etiqueta"]}'
    return ("Previa · " if a.get("tipo") == "previa" else "") + a["etiqueta"]


def _imagenes(a: dict) -> list[str]:
    return a.get("imagenes") or a.get("imagenes_web") or []


def _img(a: dict, prof: str) -> str:
    imgs = _imagenes(a)
    return f'<img src="{prof}{imgs[0]}" alt="" loading="lazy">' if imgs else ""


def _url(a: dict, prof: str) -> str:
    if a.get("tipo") == "noticia":
        return f'{prof}noticias/{a["slug"]}.html'
    return f'{prof}articulos/{a["slug"]}.html'


def _portada(lista: list[dict], prof: str = "", extra: str = "", cfg: dict | None = None) -> str:
    if not lista:
        return '<div class="vacio">Aún no hay noticias. La próxima edición sale mañana a primera hora.</div>'
    a0, resto = lista[0], lista[1:]
    foto = _img(a0, prof)
    hero = (f'<a class="hero" href="{_url(a0, prof)}"' + ("" if foto else ' style="grid-template-columns:1fr"') + '>'
            + (f'<div class="foto">{foto}</div>' if foto else "")
            + f'<div class="t"><span class="tag">{_e(_etiqueta(a0))}</span>'
            f'<h2 class="tit">{_e(a0["titular"])}</h2><p>{_e(a0["entradilla"])}</p></div></a>')
    mini = "".join(f'<a href="{_url(a, prof)}"><span class="tag">{_e(_etiqueta(a))}</span><h3>{_e(a["titular"])}</h3>'
                   f'<p>{_e(a["entradilla"])}</p></a>' for a in resto[:2])
    out = hero + (f'<section class="mini">{mini}</section>' if mini else "")
    out += extra
    if resto[2:]:
        tarjetas = [_tarjeta(a, prof, f'<span class="tag">{_e(_etiqueta(a))}</span>') for a in resto[2:]]
        if cfg is not None:  # un anuncio entre noticias cada 9 tarjetas
            for k in reversed(range(6, len(tarjetas), 9)):
                tarjetas.insert(k, _anuncio(cfg, "entre_noticias", "feed"))
        out += '<h2 class="sec tit">Más noticias</h2><section class="grid">' + "".join(tarjetas) + "</section>"
    return out


def _slug_liga(etiqueta: str) -> str:
    t = unicodedata.normalize("NFKD", etiqueta).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")


def _filas_partidos(partidos: list[dict]) -> str:
    return "".join(f'<div class="partido"><span class="l">{_e(es(p["local"]))}{_esc(p["local"], p.get("escudo_local"))}</span>'
                   f'<b>{p["goles_local"]} - {p["goles_visitante"]}</b>'
                   f'<span>{_esc(p["visitante"], p.get("escudo_visitante"))}{_e(es(p["visitante"]))}</span></div>'
                   for p in partidos)


ZONAS = {"ascenso": "Ascenso", "playoff": "Play-off de ascenso", "descenso": "Descenso"}


def _forma(f: str) -> str:
    letra = {"W": "G", "D": "E", "L": "P"}
    return '<span class="forma">' + "".join(f'<i class="{c}">{letra[c]}</i>' for c in (f or "") if c in letra) + "</span>"


def _tabla(tabla: list[dict], resalta: set[str] | None = None, filas_max: int | None = None) -> str:
    """Clasificación completa (o las primeras filas_max), con escudos, zonas de ascenso/descenso y racha."""
    resalta = resalta or set()
    completa = "pg" in tabla[0]
    filas = ""
    for t in tabla[:filas_max] if filas_max else tabla:
        nombre = es(t["equipo"])
        clase = " ".join(c for c in (t.get("zona", ""), "resalta" if nombre in resalta else "") if c)
        filas += (f'<tr class="{clase}"><td class="p">{t["pos"]}</td>'
                  f'<td class="eq"><span>{_esc(nombre, t.get("escudo"))}{_e(nombre)}</span></td><td>{t.get("pj", "")}</td>')
        if completa and not filas_max:
            filas += "".join(f'<td class="sm">{t.get(k, "")}</td>' for k in ("pg", "pe", "pp", "gf", "gc"))
        filas += f'<td>{t.get("dg", "")}</td><td class="pts">{t["pts"]}</td>'
        if completa and not filas_max:
            filas += f'<td class="sm">{_forma(t.get("forma"))}</td>'
        filas += "</tr>"
    cab = '<th>#</th><th class="eq">Equipo</th><th>PJ</th>'
    if completa and not filas_max:
        cab += "".join(f'<th class="sm">{k}</th>' for k in ("G", "E", "P", "GF", "GC"))
    cab += "<th>DG</th><th>Pts</th>" + ('<th class="sm">Racha</th>' if completa and not filas_max else "")
    zonas = [z for z in ZONAS if any(t.get("zona") == z for t in tabla[:filas_max])]
    leyenda = ('<div class="leyenda">' + "".join(f'<span class="{z}">{ZONAS[z]}</span>' for z in zonas) + "</div>") if zonas else ""
    return f'<div class="tabla-wrap"><table class="clas"><tr>{cab}</tr>{filas}</table></div>{leyenda}'


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
        out += f'<h2 class="tit pais">{_e(pais)}</h2><div class="ligas">'
        for c in comps:
            suyas = [a for e, l in ligas.items() for a in l if a.get("competicion", a["etiqueta"]) == c["etiqueta"]]
            jugadas = [a["fecha"] for a in suyas if a.get("partidos")]
            proximas = [a["fecha"] for a in suyas if a.get("proximos")]
            nota = (f'Última jornada: {fecha_larga(max(jugadas))}' if jugadas else
                    f'Próximo partido: {fecha_larga(max(proximas))}' if proximas else "Próximamente")
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
        f'<small>{fecha_larga(l[0]["fecha"])}</small></a>'
        for e, l in sorted(grupos.items(), key=lambda x: [int(n) if n.isdigit() else n for n in re.split(r"(\d+)", x[0])])) + "</div>"
    noticias = sorted([a for l in grupos.values() for a in l] + _noticias_de(competicion=c["etiqueta"]),
                      key=lambda a: a["fecha"], reverse=True)[:12]
    out += '<h2 class="sec tit">Últimas noticias</h2><section class="grid">' + "".join(
        _tarjeta(a, prof, f'<span class="tag">{_e(_etiqueta(a))}</span>') for a in noticias) + "</section>"
    return out


def _pagina_liga(etiqueta: str, lista: list[dict]) -> str:
    prof = "../"
    out = f'<span class="tag">{"España" if lista[0]["grupo"] == "espana" else "Internacional"}</span>' \
          f'<h1 class="tit" style="font-size:clamp(30px,5vw,46px);margin:12px 0 4px">{_e(etiqueta)}</h1>'
    previa = next((a for a in lista if a.get("proximos")), None)
    ultima_jugada = next((a["fecha"] for a in lista if a.get("partidos")), "")
    if previa and previa["fecha"] > ultima_jugada:
        filas = "".join(f'<div class="partido"><span class="l">{_e(es(p["local"]))}{_esc(p["local"], p.get("escudo_local"))}</span>'
                        f'<b class="hora">{_e(p["fecha"][11:16] or "--:--")}</b>'
                        f'<span>{_esc(p["visitante"], p.get("escudo_visitante"))}{_e(es(p["visitante"]))}</span></div>'
                        for p in previa["proximos"])
        out += (f'<h2 class="sec tit">Próximos partidos</h2><div class="comp"><h3 class="tit">'
                f'<a href="{_url(previa, prof)}">{fecha_larga(previa["fecha"])} · Leer la previa →</a></h3>{filas}</div>')
    out += '<div class="liga">'
    # Resultados: las 3 últimas jornadas con partidos
    res = "".join(f'<div class="comp"><h3 class="tit">{fecha_larga(a["fecha"])}</h3>{_filas_partidos(a["partidos"])}</div>'
                  for a in [a for a in lista if a.get("partidos")][:3])
    out += f'<section style="grid-column:1/-1"><h2 class="sec tit">Resultados</h2><div class="res3">{res or "<div class=vacio>Sin resultados todavía.</div>"}</div></section>'
    out += "</div>"
    tabla = next((a["clasificacion"] for a in lista if a.get("clasificacion")), None)
    out += '<section id="clasificacion"><h2 class="sec tit">Clasificación</h2>' + (_tabla(tabla) if tabla else
           '<div class="vacio">La clasificación aparecerá aquí en cuanto la fuente de datos la publique.</div>') + "</section>"
    out += _estadisticas_liga(ESTADS.get(etiqueta))
    noticias = sorted(lista + _noticias_de(etiqueta=etiqueta), key=lambda a: a["fecha"], reverse=True)[:12]
    out += '<h2 class="sec tit">Últimas noticias</h2><section class="grid">' + "".join(
        _tarjeta(a, prof, f'<span class="tag">{_e(_etiqueta(a))}</span>') for a in noticias) + "</section>"
    return out


DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]

# Cambia "viernes, 13 de noviembre" por "Hoy"/"Mañana" según el día en que se mire la web
SCRIPT_DIAS = """<script>(function(){function iso(d){return d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0')+'-'+String(d.getDate()).padStart(2,'0')}
var h=new Date(),m=new Date();m.setDate(h.getDate()+1);var n={};n[iso(h)]='Hoy · ';n[iso(m)]='Mañana · ';
document.querySelectorAll('[data-dia]').forEach(function(e){var p=n[e.getAttribute('data-dia')];if(p)e.textContent=p+e.textContent;});
document.querySelectorAll('[data-pasado]').forEach(function(e){if(e.getAttribute('data-pasado')<iso(h))e.style.display='none';});})();</script>"""


def cargar_agenda() -> dict:
    f = CONTENIDO / "agenda.json"
    return json.loads(f.read_text()) if f.exists() else {}


def _dia(fecha: str) -> str:
    d = date.fromisoformat(fecha)
    return f"{DIAS[d.weekday()].capitalize()}, {fecha_larga(fecha)}"


def _ancla(texto: str) -> str:
    """Id de un título dentro de un artículo (el mismo que pone el extension 'toc' de markdown)."""
    return _slug_liga(re.sub(r"[*_`]", "", texto))


def _mapa_previas(arts: list[dict]) -> dict:
    """id de partido → enlace a su previa: su página propia o, en previas antiguas, su apartado en la de la jornada."""
    mapa = {}
    for a in arts:
        if a.get("tipo") != "previa":
            continue
        if a.get("previas_partido"):
            mapa.update({pp["id"]: f'previas/{pp["slug"]}.html' for pp in a["previas_partido"]})
            continue
        titulos = [l[3:].strip() for l in a.get("cuerpo_markdown", "").splitlines() if l.startswith("## ")]
        for p in a.get("proximos", []):
            loc, vis = es(p["local"]).lower(), es(p["visitante"]).lower()
            t = next((t for t in titulos if loc in t.lower() and vis in t.lower()), None)
            mapa[p["id"]] = f'articulos/{a["slug"]}.html' + (f"#{_ancla(t)}" if t else "")
    return mapa


ESTADS: dict[str, dict] = {}  # etiqueta de la liga → máximos goleadores y tarjetas (contenido/estadisticas)
ESCUDOS: dict[str, str] = {}  # nombre del equipo (en español) → URL de su escudo; se rellena en construir()


def _recoger_escudos(arts: list[dict], agenda: dict) -> None:
    ESCUDOS.clear()
    def mete(nombre, url):
        if nombre and url:
            ESCUDOS.setdefault(es(nombre), url)
    for a in sorted(arts, key=lambda a: a["fecha"], reverse=True):
        for p in (a.get("partidos") or []) + (a.get("proximos") or []):
            mete(p.get("local"), p.get("escudo_local"))
            mete(p.get("visitante"), p.get("escudo_visitante"))
        for t in a.get("clasificacion") or []:
            mete(t.get("equipo"), t.get("escudo"))
    for comps in agenda.values():
        for c in comps:
            for p in c.get("partidos", []):
                mete(p.get("local"), p.get("escudo_local"))
                mete(p.get("visitante"), p.get("escudo_visitante"))


def _esc(nombre: str | None, url: str | None = None) -> str:
    """Escudo pequeño junto al nombre del equipo (no ocupa nada si no lo tenemos o no carga)."""
    url = url or ESCUDOS.get(es(nombre) or "")
    return f'<img class="esc" src="{_e(url)}" alt="" loading="lazy" onerror="this.remove()">' if url else ""


def _escudo(nombre: str, url: str | None) -> str:
    """Escudo del equipo; si no hay o no carga, sus iniciales."""
    ini = "".join(w[0] for w in re.findall(r"[A-Za-zÀ-ÿ]+", nombre) if w[0].isupper())[:3] or nombre[:2]
    img = f'<img src="{_e(url)}" alt="" loading="lazy" onerror="this.remove()">' if url else ""
    return f'<span class="escudo" aria-hidden="true">{_e(ini)}{img}</span>'


def _parrafo_inicial(t: str) -> str:
    """Primer párrafo con la letra (o palabra corta, p. ej. 'El') grande del principio, como en prensa."""
    m = re.match(r"^(\S+?)(\s.*)$", t, re.S)
    if m and len(m.group(1)) <= 3 and m.group(1).isalpha():
        return f'<p><span class="cap">{_e(m.group(1))}</span>{_e(m.group(2))}</p>'
    return f'<p><span class="cap">{_e(t[:1])}</span>{_e(t[1:])}</p>'


def _pagina_previa(cfg: dict, a: dict, pp: dict, p: dict) -> str:
    """Previa de un partido en su propia página, maquetada como una noticia de periódico."""
    prof = "../"
    loc, vis = es(p["local"]), es(p["visitante"])
    jornada = jornada_es(p.get("jornada"))
    hora = (p.get("fecha") or "")[11:16]
    url = f'{cfg["medio"]["url_web"].rstrip("/")}/previas/{pp["slug"]}.html'
    comparte = (f'<div class="comparte"><a href="https://wa.me/?text={quote(pp["titular"] + " " + url)}" target="_blank" rel="noopener">WhatsApp</a>'
                f'<a href="https://twitter.com/intent/tweet?text={quote(pp["titular"])}&amp;url={quote(url)}" target="_blank" rel="noopener">X</a>'
                f'<button type="button" onclick="navigator.clipboard&&navigator.clipboard.writeText(\'{url}\').then(()=>{{this.textContent=\'¡Copiado!\'}})">'
                'Copiar enlace</button></div>')
    out = (f'<div class="pp"><div class="miga"><a href="{prof}ligas/{_slug_liga(a["etiqueta"])}.html">Previa · {_e(a["etiqueta"])}</a>'
           + (f' <span>· {_e(jornada)}</span>' if jornada else "") + '</div>'
           f'<h1 class="tit">{_e(pp["titular"])}</h1><p class="entr">{_e(pp["entradilla"])}</p>'
           f'<div class="firma"><div><b>Redacción {_e(cfg["medio"]["nombre"])}</b> · Madrid · {fecha_larga(a["fecha"])}</div>{comparte}</div>'
           f'<div class="marcador"><div class="eq">{_escudo(loc, p.get("escudo_local"))}<span>{_e(loc)}</span></div>'
           f'<div class="hora"><b>{_e(hora or "--:--")}</b><span>{_e(dia_partido(p.get("fecha")))}</span></div>'
           f'<div class="eq v">{_escudo(vis, p.get("escudo_visitante"))}<span>{_e(vis)}</span></div></div>')
    # Texto
    parrafos = pp.get("parrafos") or []
    texto = (_parrafo_inicial(parrafos[0]) if parrafos else "") + "".join(f"<p>{_e(t)}</p>" for t in parrafos[1:])
    if pp.get("el_dato"):
        texto += f'<div class="eldato"><b>El dato</b>{_e(pp["el_dato"])}</div>'
    if pp.get("precedente"):
        texto += f'<h2>El último precedente</h2><p>{_e(pp["precedente"])}</p>'
    if pp.get("claves"):
        texto += '<h2>Las claves</h2><ul class="claves">' + "".join(
            f'<li><b>{_e(c["titulo"].rstrip("."))}.</b> {_e(c["texto"])}</li>' for c in pp["claves"]) + "</ul>"
    # Cuadro de datos y racha
    sede = p.get("estadio") or "Por confirmar"
    arbitro = re.sub(r",.*$", "", p.get("arbitro") or "") or "Por confirmar"
    datos = [("Competición", a["etiqueta"]), ("Jornada", jornada.removeprefix("Jornada ")), ("Estadio", sede), ("Ciudad", p.get("ciudad")),
             ("Día", dia_partido(p.get("fecha")).capitalize()), ("Hora", hora), ("Árbitro", arbitro)]
    caja = '<div class="caja"><h3>Ficha del partido</h3>' + "".join(
        f'<div class="dato"><span>{k}</span>{_e(v)}</div>' for k, v in datos if v) + "</div>"
    caja += _comparativo(p, loc, vis)
    if p.get("historial"):
        caja += ('<div class="caja"><h3>Últimos enfrentamientos</h3><ul class="h2h">' + "".join(
            f'<li>{_e(h["resultado"])}<small>{fecha_larga(h["fecha"])} · {_e(h.get("competicion", ""))}</small></li>'
            for h in p["historial"][:5]) + "</ul></div>")
    forma = a.get("forma") or {}
    if (forma.get(p["local"]) or forma.get(p["visitante"])) and not (p.get("contexto") or {}).get("local", {}).get("racha"):
        filas = ""
        for e in (p["local"], p["visitante"]):
            res = "".join(f'<i class="f{r["resultado"]}" title="{_e(r["marcador"] + " vs " + es(r["rival"]))}">{r["resultado"]}</i>'
                          for r in reversed(forma.get(e, [])))
            filas += f'<div class="racha">{_e(es(e))}<span>{res or "<small>Sin datos</small>"}</span></div>'
        caja += (f'<div class="caja"><h3>Cómo llegan</h3>{filas}'
                 '<p class="nota">Últimos partidos publicados; el más reciente, a la derecha.</p></div>')
    out += (f'<div class="cols"><div class="texto">{_con_anuncio(cfg, texto)}</div>'
            f'<aside>{caja}{_anuncio(cfg, "lateral", "lat")}</aside></div>')
    # Más previas de la misma jornada
    partidos = {x["id"]: x for x in a.get("proximos", [])}
    otras = [o for o in a.get("previas_partido", []) if o["id"] != pp["id"] and o["id"] in partidos]
    if otras:
        out += '<h2 class="sec tit">Más previas de la jornada</h2><div class="mas">' + "".join(
            f'<a href="{o["slug"]}.html"><small>{_e((partidos[o["id"]].get("fecha") or "")[11:16])}</small>'
            f'<strong>{_e(es(partidos[o["id"]]["local"]))} - {_e(es(partidos[o["id"]]["visitante"]))}</strong>'
            + ("" if o["titular"].endswith("previa del partido") else f'<span>{_e(o["titular"])}</span>')
            + '</a>' for o in otras) + "</div>"
    out += (f'<a class="volver" href="{_url(a, prof)}">← Previa de toda la jornada de {_e(a["etiqueta"])}</a></div>')
    return out


def _comparativo(p: dict, loc: str, vis: str) -> str:
    """Cuadro 'Cara a cara' de la previa: puesto, puntos, goles, casa/fuera, racha y goleador de cada equipo."""
    ctx = p.get("contexto") or {}
    L, V = ctx.get("local") or {}, ctx.get("visitante") or {}
    if not (L or V):
        return ""
    def reg(r):
        return f'{r.get("pg", 0)}-{r.get("pe", 0)}-{r.get("pp", 0)}' if r else "—"
    def racha(c):
        letras = "".join(x["resultado"] for x in reversed(c.get("racha") or []))
        return _forma(letras.replace("G", "W").replace("E", "D").replace("P", "L")) if letras else "—"
    filas = [("Puesto", L.get("pos"), V.get("pos"), "menos"), ("Puntos", L.get("pts"), V.get("pts"), "mas"),
             ("G-E-P", reg(L), reg(V), None), ("Goles a favor", L.get("gf"), V.get("gf"), "mas"),
             ("Goles en contra", L.get("gc"), V.get("gc"), "menos"),
             ("En casa / Fuera", reg(L.get("casa")), reg(V.get("fuera")), None)]
    html_f = ""
    for k, a_, b_, mejor in filas:
        if a_ is None and b_ is None:
            continue
        ca = cb = ""
        if mejor and isinstance(a_, (int, float)) and isinstance(b_, (int, float)) and a_ != b_:
            gana_a = (a_ > b_) if mejor == "mas" else (a_ < b_)
            ca, cb = (' class="mejor"', "") if gana_a else ("", ' class="mejor"')
        html_f += f'<tr><td{ca}>{_e(a_ if a_ is not None else "—")}</td><td class="k">{k}</td><td{cb}>{_e(b_ if b_ is not None else "—")}</td></tr>'
    if L.get("racha") or V.get("racha"):
        html_f += f'<tr><td>{racha(L)}</td><td class="k">Racha</td><td>{racha(V)}</td></tr>'
    if L.get("goleador") or V.get("goleador"):
        g = lambda c: f'{_e(c["goleador"]["jugador"])} ({c["goleador"]["goles"]})' if c.get("goleador") else "—"
        html_f += f'<tr><td>{g(L)}</td><td class="k">Máximo goleador</td><td>{g(V)}</td></tr>'
    cab = (f'<tr class="cab"><td>{_esc(loc, p.get("escudo_local"))}{_e(loc)}</td><td class="k"></td>'
           f'<td>{_esc(vis, p.get("escudo_visitante"))}{_e(vis)}</td></tr>')
    return f'<div class="caja"><h3>Cara a cara</h3><table class="cara">{cab}{html_f}</table></div>'


def _pagina_cronica_estrella(cfg: dict, a: dict, ce: dict, p: dict) -> str:
    """Crónica del partido estrella en su propia página, maquetada como una noticia."""
    prof = "../"
    loc, vis = es(p["local"]), es(p["visitante"])
    jornada = jornada_es(p.get("jornada"))
    out = (f'<div class="pp"><div class="miga"><a href="{prof}ligas/{_slug_liga(a["etiqueta"])}.html">Crónica · {_e(a["etiqueta"])}</a>'
           + (f' <span>· {_e(jornada)}</span>' if jornada else "") + '</div>'
           f'<h1 class="tit">{_e(ce["titular"])}</h1><p class="entr">{_e(ce["entradilla"])}</p>'
           f'<div class="firma"><div><b>Redacción {_e(cfg["medio"]["nombre"])}</b> · {fecha_larga(a["fecha"])}</div></div>'
           f'<div class="marcador"><div class="eq">{_escudo(loc, p.get("escudo_local"))}<span>{_e(loc)}</span></div>'
           f'<div class="hora"><b>{p["goles_local"]}-{p["goles_visitante"]}</b><span>Final</span></div>'
           f'<div class="eq v">{_escudo(vis, p.get("escudo_visitante"))}<span>{_e(vis)}</span></div></div>')
    gol = lambda g: f'⚽ {_e(g["jugador"])} {g["min"]}\'' + (" (p)" if "Penalty" in (g.get("tipo") or "") else "") + (
        " (pp)" if "Own" in (g.get("tipo") or "") else "")
    izq = [gol(g) for g in p.get("goleadores", []) if g.get("equipo") == p["local"]]
    der = [gol(g) for g in p.get("goleadores", []) if g.get("equipo") == p["visitante"]]
    izq += [f'🟥 {_e(r["jugador"])} {r["min"]}\'' for r in p.get("rojas", []) if r.get("equipo") == p["local"]]
    der += [f'🟥 {_e(r["jugador"])} {r["min"]}\'' for r in p.get("rojas", []) if r.get("equipo") == p["visitante"]]
    if izq or der:
        out += f'<div class="goles"><div>{"<br>".join(izq)}</div><div>{"<br>".join(der)}</div></div>'
    parrafos = ce.get("parrafos") or []
    texto = (_parrafo_inicial(parrafos[0]) if parrafos else "") + "".join(f"<p>{_e(t)}</p>" for t in parrafos[1:])
    if ce.get("el_dato"):
        texto += f'<div class="eldato"><b>El dato</b>{_e(ce["el_dato"])}</div>'
    texto += _estadisticas_partidos({"partidos": [p]})
    sede = p.get("estadio")
    arbitro = re.sub(r",.*$", "", p.get("arbitro") or "")
    datos = [("Competición", a["etiqueta"]), ("Jornada", jornada.removeprefix("Jornada ")), ("Estadio", sede),
             ("Ciudad", p.get("ciudad")), ("Árbitro", arbitro)]
    caja = '<div class="caja"><h3>Ficha del partido</h3>' + "".join(
        f'<div class="dato"><span>{k}</span>{_e(v)}</div>' for k, v in datos if v) + "</div>"
    out += (f'<div class="cols"><div class="texto">{_con_anuncio(cfg, texto)}{_mini_clasificacion(a)}</div>'
            f'<aside>{caja}{_anuncio(cfg, "lateral", "lat")}</aside></div>')
    out += f'<a class="volver" href="{prof}articulos/{a["slug"]}.html">← Crónica de toda la jornada de {_e(a["etiqueta"])}</a></div>'
    return out


PREVIAS: dict = {}  # se rellena en construir()


def _fila_agenda(p: dict, prof: str = "") -> str:
    if p.get("goles_local") is not None and p.get("goles_visitante") is not None:
        centro = f'<b>{p["goles_local"]} - {p["goles_visitante"]}</b>'
    else:
        centro = f'<b class="hora">{_e((p.get("fecha") or "")[11:16] or "--:--")}</b>'
    if p.get("id") in PREVIAS and p.get("goles_local") is None:  # botón debajo de la hora
        centro = (f'<span class="centro">{centro}'
                  f'<a class="btn-previa" href="{prof}{PREVIAS[p["id"]]}">Previa</a></span>')
    return (f'<div class="partido"><span class="l">{_e(es(p["local"]))}{_esc(p["local"], p.get("escudo_local"))}</span>{centro}'
            f'<span>{_esc(p["visitante"], p.get("escudo_visitante"))}{_e(es(p["visitante"]))}</span></div>')


PRIORIDAD: dict[str, int] = {}  # competición → prioridad actual en config.yaml (se rellena en construir())
PRINCIPAL: set[str] = set()     # competiciones que van delante (la RFEF)


def _prio_comp(c: dict) -> tuple:
    return (PRIORIDAD.get(c.get("competicion"), c.get("prioridad", 3)), c["etiqueta"])


def _agenda(agenda: dict, prof: str = "") -> str:
    out = '<h1 class="sec tit">Partidos</h1>'
    if not agenda:
        return out + '<div class="vacio">El calendario se actualiza cada mañana.</div>'
    for fecha in sorted(agenda):
        comps = agenda[fecha]
        total = sum(len(c["partidos"]) for c in comps)
        out += (f'<section class="dia" data-pasado="{fecha}"><h2 class="tit" data-dia="{fecha}">'
                f'{_dia(fecha)}</h2>')
        if not total:
            out += '<div class="vacio">No hay partidos de nuestras ligas este día.</div></section>'
            continue
        for c in sorted(comps, key=_prio_comp):
            out += (f'<div class="comp"><h3 class="tit"><a href="{prof}ligas/{_slug_liga(c["etiqueta"])}.html">'
                    f'{_e(c["etiqueta"])} →</a></h3>{"".join(_fila_agenda(p) for p in c["partidos"])}</div>')
        out += "</section>"
    return out + SCRIPT_DIAS


def _agenda_portada(agenda: dict) -> str:
    """Bloque compacto en la portada con los partidos del primer día de la agenda."""
    for fecha in sorted(agenda):
        comps = sorted((c for c in agenda[fecha] if c["partidos"]), key=_prio_comp)
        if not comps:
            continue
        filas, n = "", 0
        for c in comps:
            if n >= 8:
                break
            filas += (f'<a class="lt-p" href="ligas/{_slug_liga(c["etiqueta"])}.html">{_e(c["etiqueta"])}</a>'
                      + "".join(_fila_agenda(p) for p in c["partidos"][:8 - n]))
            n += len(c["partidos"][:8 - n])
        total = sum(len(c["partidos"]) for c in comps)
        return (f'<div data-pasado="{fecha}"><h2 class="sec tit">Partidos · <span data-dia="{fecha}">{_dia(fecha)}</span></h2>'
                f'<div class="comp">{filas}<h3 class="tit" style="margin:10px 0 0">'
                f'<a href="partidos.html">Ver todos los partidos ({total}) →</a></h3></div></div>')
    return ""


def _resultados(arts: list[dict]) -> str:
    """Todos los resultados de los últimos 7 días con partidos, agrupados por día y competición."""
    dias = sorted({a["fecha"] for a in arts if a.get("partidos")}, reverse=True)[:7]
    if not dias:
        return '<h1 class="sec tit">Resultados</h1><div class="vacio">Aún no hay resultados.</div>'
    out = '<h1 class="sec tit">Resultados</h1>'
    for d in dias:
        out += f'<section class="dia"><h2 class="tit">{fecha_larga(d)}</h2>'
        for a in sorted((a for a in arts if a["fecha"] == d and a.get("partidos")), key=lambda a: a.get("prioridad", 3)):
            out += (f'<div class="comp"><h3 class="tit"><a href="ligas/{_slug_liga(a["etiqueta"])}.html">{_e(a["etiqueta"])} →</a></h3>'
                    f'{_filas_partidos(a["partidos"])}</div>')
        out += "</section>"
    return out


def _marcador_regional(r: dict) -> str:
    if r.get("goles_local") is not None and r.get("goles_visitante") is not None:
        return f'<b>{r["goles_local"]} - {r["goles_visitante"]}</b>'
    return f'<b class="hora">{_e(r.get("hora") or "--:--")}</b>'


def _cuando(r: dict) -> str:
    d = date.fromisoformat(r["fecha"])
    return f'{DIAS[d.weekday()][:3].capitalize()} {d.day}'


def _tarjeta_regional(r: dict, prof: str = "") -> str:
    lugar = " · ".join(x for x in (r.get("categoria"), r.get("comunidad")) if x)
    pie = r["titular"] if r["tipo"] == "resultado" else f'{_cuando(r)} · {r["titular"]}'
    return (f'<a class="rg" href="{prof}regionales.html#{r["slug"]}"><div class="rgt"><span class="tag">{_e(r["motivo"])}</span>'
            f'<small>{_e(lugar)}</small></div><div class="rgm"><span>{_e(r["local"])}</span>{_marcador_regional(r)}'
            f'<span>{_e(r["visitante"])}</span></div><p>{_e(pie)}</p></a>')


def _llamada(rc: dict) -> str:
    url = rc.get("formulario_url")
    boton = f'<a href="{_e(url)}" rel="noopener">Mándanos tu partido →</a>' if url else ""
    return ('<div class="llamada"><h2>¿Juegas, entrenas o eres de un club de Regional?</h2>'
            '<p>Cuéntanos los partidos gordos de tu zona (derbis, duelos por el ascenso, historias de barrio) '
            'y los publicamos con tu firma.</p>' + boton + '</div>')


def _proximos_y_resultados(regs: list[dict]) -> tuple[list[dict], list[dict]]:
    hoy = date.today().isoformat()
    proximos = [r for r in regs if r["tipo"] == "previa" and r["fecha"] >= hoy]
    resultados = sorted((r for r in regs if r["tipo"] == "resultado"), key=lambda r: r["fecha"], reverse=True)
    return proximos, resultados


def _regionales_portada(regs: list[dict], rc: dict) -> str:
    proximos, resultados = _proximos_y_resultados(regs)
    n = rc.get("max_portada", 6)
    elegidos = proximos[:n] or resultados[:n]
    url = rc.get("formulario_url")
    cab = ('<h2 class="sec tit">Regionales · Los partidos de la jornada</h2><div class="regcab">'
           '<span>Los duelos que no te puedes perder en toda España, elegidos cada semana.</span>'
           + (f'<a href="{_e(url)}" rel="noopener">¿Conoces un partido gordo? Cuéntanoslo →</a>' if url else
              '<a href="regionales.html">Ver todos →</a>') + '</div>')
    if not elegidos:
        return cab + _llamada(rc)
    return cab + '<section class="regs">' + "".join(_tarjeta_regional(r) for r in elegidos) + '</section>'


def _articulo_regional(r: dict) -> str:
    lugar = " · ".join(x for x in (r.get("categoria"), r.get("comunidad")) if x)
    firma = f'<div class="firma">Por <b>{_e(r["firma"])}</b>, corresponsal de Sin Focos</div>' if r.get("firma") else ""
    parrafos = "".join(f'<p class="txt">{_e(p)}</p>' for p in r.get("texto", "").split("\n") if p.strip())
    return (f'<div class="rgart" id="{r["slug"]}"><span class="tag">{_e(r["motivo"])}</span> '
            f'<span class="fecha">{_e(lugar)} · {_dia(r["fecha"])}</span><h3 class="tit">{_e(r["titular"])}</h3>'
            f'<div class="rgm"><span>{_e(r["local"])}</span>{_marcador_regional(r)}<span>{_e(r["visitante"])}</span></div>'
            f'{parrafos}{firma}</div>')


def _pagina_regionales(regs: list[dict], rc: dict) -> str:
    proximos, resultados = _proximos_y_resultados(regs)
    out = ('<h1 class="sec tit">Regionales</h1><p style="color:var(--suave);margin:-6px 0 18px">'
           'Los partidos gordos del fútbol regional de toda España, contados por gente de allí.</p>')
    if proximos:
        out += '<h2 class="sec tit">Próximos partidos</h2>' + "".join(_articulo_regional(r) for r in proximos)
    if resultados:
        out += '<h2 class="sec tit">Resultados</h2>' + "".join(_articulo_regional(r) for r in resultados[:30])
    if not proximos and not resultados:
        out += '<div class="vacio" style="margin-bottom:20px">Muy pronto, los primeros partidos de Regional.</div>'
    return out + _llamada(rc)


def _franja_mas(secundario: list[dict]) -> str:
    """Franja pequeña al final de la portada con los últimos resultados de lo que va en segundo plano."""
    con_partidos = [a for a in secundario if a.get("partidos")]
    piezas = []
    if con_partidos:
        ultimo = max(a["fecha"] for a in con_partidos)
        for a in sorted((a for a in con_partidos if a["fecha"] == ultimo), key=lambda a: a.get("prioridad", 3)):
            for p in a["partidos"]:
                piezas.append(f'<a href="articulos/{a["slug"]}.html"><small>{_e(a["etiqueta"])}</small>'
                              f'<span>{_e(es(p["local"]))} {p["goles_local"]}-{p["goles_visitante"]} {_e(es(p["visitante"]))}</span></a>')
    piezas = piezas[:14] + ['<a href="mas-futbol.html"><small>Segunda, copas y Europa</small><span>Ver todo →</span></a>']
    return ('<h2 class="sec tit peq">También · Segunda, copas, selecciones y primeras divisiones</h2>'
            f'<div class="franja">{"".join(piezas)}</div>')


def _nav_de(competicion: str | None) -> str:
    """Qué pestaña del menú se marca en una página de esa competición."""
    if competicion in PRINCIPAL:
        return f"ligas/{_slug_liga(competicion)}.html"
    return "mas-futbol.html" if competicion else ""


def _migas(a: dict, prof: str) -> str:
    comp = a.get("competicion") or a["etiqueta"]
    out = f'<div class="migas"><a href="{prof}index.html">Portada</a> › <a href="{prof}ligas/{_slug_liga(comp)}.html">{_e(comp)}</a>'
    if a["etiqueta"] != comp:
        out += f' › <a href="{prof}ligas/{_slug_liga(a["etiqueta"])}.html">{_e(a["etiqueta"].split(" · ", 1)[-1])}</a>'
    return out + "</div>"


def _con_anuncio(cfg: dict, texto_html: str) -> str:
    """Mete el anuncio «dentro del texto» después del segundo párrafo (solo si el texto es largo)."""
    partes = texto_html.split("</p>")
    if len(partes) < 5:
        return texto_html
    return "</p>".join(partes[:2]) + "</p>" + _anuncio(cfg, "dentro_texto", "txt") + "</p>".join(partes[2:])


def _estadisticas_liga(e: dict | None) -> str:
    """Máximos goleadores y tarjetas por equipo en la página de la liga."""
    if not e or not (e.get("goleadores") or e.get("tarjetas")):
        return ""
    bloques = ""
    if e.get("goleadores"):
        filas, pos, prev = "", 0, None
        for i, g in enumerate(e["goleadores"][:15], 1):
            pos = pos if g["goles"] == prev else i
            prev = g["goles"]
            pen = f' <small>({g["penaltis"]} de penalti)</small>' if g.get("penaltis") else ""
            filas += (f'<tr><td class="p">{pos}</td><td class="jug"><b>{_e(g["jugador"])}</b>'
                      f'<small>{_esc(g["equipo"], g.get("escudo"))}{_e(es(g["equipo"]))}</small></td>'
                      f'<td>{g.get("pj") or ""}</td><td class="pts">{g["goles"]}{pen}</td></tr>')
        bloques += ('<section><h2 class="sec tit">Máximos goleadores</h2><div class="tabla-wrap"><table class="clas">'
                    f'<tr><th>#</th><th class="eq">Jugador</th><th>PJ</th><th>Goles</th></tr>{filas}</table></div></section>')
    if e.get("tarjetas"):
        filas = "".join(f'<tr><td class="eq"><span>{_esc(t["equipo"], t.get("escudo"))}{_e(es(t["equipo"]))}</span></td>'
                        f'<td><span class="am">{t["amarillas"]}</span></td><td><span class="ro">{t["rojas"]}</span></td></tr>'
                        for t in e["tarjetas"])
        bloques += ('<section><h2 class="sec tit">Tarjetas por equipo</h2><div class="tabla-wrap"><table class="clas">'
                    f'<tr><th class="eq">Equipo</th><th>Amarillas</th><th>Rojas</th></tr>{filas}</table></div></section>')
    return f'<div class="est-liga">{bloques}</div>'


ETIQ_STATS = [("posesion", "Posesión"), ("tiros", "Tiros"), ("a_puerta", "Tiros a puerta"), ("corners", "Córners"),
              ("faltas", "Faltas"), ("fueras_juego", "Fueras de juego"), ("amarillas", "Amarillas"), ("rojas", "Rojas")]


def _num(v) -> float:
    try:
        return float(str(v).rstrip("%"))
    except (TypeError, ValueError):
        return 0.0


def _estadisticas_partidos(a: dict) -> str:
    """En la crónica: estadísticas de cada partido que las tenga (posesión, tiros, córners…)."""
    cajas = ""
    for p in a.get("partidos") or []:
        st = p.get("estadisticas")
        if not st:
            continue
        filas = ""
        for k, nombre in ETIQ_STATS:
            l, v = st["local"].get(k), st["visitante"].get(k)
            if l is None and v is None:
                continue
            nl, nv = _num(l), _num(v)
            barra = "" if nl + nv == 0 else (f'<b style="width:{round(nl * 100 / (nl + nv))}%"></b>'
                                             f'<b style="width:{100 - round(nl * 100 / (nl + nv))}%"></b>')
            filas += (f'<div class="st"><span>{_e(l if l is not None else 0)}</span><div><small>{nombre}</small>'
                      f'<i>{barra}</i></div>'
                      f'<span>{_e(v if v is not None else 0)}</span></div>')
        if filas:
            cajas += (f'<div class="stat"><h3>{_esc(p["local"], p.get("escudo_local"))}{_e(es(p["local"]))} '
                      f'<b>{p["goles_local"]}-{p["goles_visitante"]}</b> {_e(es(p["visitante"]))}'
                      f'{_esc(p["visitante"], p.get("escudo_visitante"))}</h3>{filas}</div>')
    return f'<section class="mini-clas"><h2>Estadísticas de los partidos</h2><div class="stats">{cajas}</div></section>' if cajas else ""


def _enlace_estrella(a: dict) -> str:
    ce = a.get("cronica_estrella")
    if not ce or not ce.get("slug"):
        return ""
    return (f'<a class="estrella" href="../cronicas/{ce["slug"]}.html"><small>La crónica del partido</small>'
            f'<strong>{_e(ce["titular"])}</strong><span>{_e(ce["entradilla"])}</span></a>')


def _mini_clasificacion(a: dict) -> str:
    """En la crónica: los 6 primeros de la tabla (y resaltados los equipos de la jornada) + enlace a la completa."""
    tabla = a.get("clasificacion")
    if not tabla or a.get("tipo") == "previa":
        return ""
    return ('<section class="mini-clas"><h2>Así va la clasificación</h2>' + _tabla(tabla, filas_max=6)
            + f'<a class="todo" href="../ligas/{_slug_liga(a["etiqueta"])}.html#clasificacion">Ver la clasificación completa →</a></section>')


def _relacionados(a: dict, arts: list[dict], prof: str) -> str:
    otros = [x for x in arts if x["slug"] != a["slug"] and x.get("tipo") == a.get("tipo")][:3]
    if not otros:
        return ""
    return ('<h2 class="sec tit" style="border-left:0;padding-left:0">Te puede interesar</h2><div class="grid">'
            + "".join(_tarjeta(x, prof, f'<span class="tag">{_e(_etiqueta(x))}</span>') for x in otros) + "</div>")


def construir(cfg: dict) -> Path:
    PUBLI.clear()
    PUBLI.update(cfg.get("publicidad") or {})
    ANALITICA.clear()
    ANALITICA.update(cfg.get("analitica") or {})
    PRIORIDAD.clear()
    PRIORIDAD.update({c["etiqueta"]: c.get("prioridad", 3) for c in cfg.get("competiciones", [])})
    PRINCIPAL.clear()
    PRINCIPAL.update(cfg.get("principal") or [])
    arts = cargar_articulos()
    for a in arts:  # la prioridad que manda es la de config.yaml de hoy, no la del día en que se escribió
        a["prioridad"] = PRIORIDAD.get(a.get("competicion"), 3)
    arts.sort(key=_orden, reverse=True)
    agenda = cargar_agenda()
    NOTICIAS.clear()
    NOTICIAS.extend(cargar_noticias())
    PREVIAS.clear()
    PREVIAS.update(_mapa_previas(arts))
    _recoger_escudos(arts, agenda)
    ESTADS.clear()
    for f in sorted((CONTENIDO / "estadisticas").glob("*.json")) if (CONTENIDO / "estadisticas").exists() else []:
        e = json.loads(f.read_text())
        ESTADS[e["etiqueta"]] = e
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

    from .regionales import cargar as cargar_regionales
    regs = cargar_regionales()
    rc = cfg.get("regionales") or {}
    principal = [a for a in arts if a.get("competicion") in PRINCIPAL]
    secundario = [a for a in arts if a.get("competicion") not in PRINCIPAL]
    noticias_rfef = [n for n in NOTICIAS if n.get("competicion") in PRINCIPAL]
    noticias_mas = [n for n in NOTICIAS if n.get("competicion") not in PRINCIPAL]

    extra = _regionales_portada(regs, rc) + _bloque_noticias(noticias_rfef[:6])
    extra += (_agenda_portada(agenda) + SCRIPT_DIAS) if agenda else ""
    cronicas = [a for a in principal if a.get("tipo") != "previa"]
    previas = [a for a in principal if a.get("tipo") == "previa"]
    previas_mas = [a for a in secundario if a.get("tipo") == "previa"]
    (SALIDA / "index.html").write_text(_pagina(
        cfg, f"{nombre} · {cfg['medio']['lema']}", _portada(principal[:60], extra=extra, cfg=cfg) + _franja_mas(secundario),
        activa="index.html", ticker=_ticker(arts, ""),
        descripcion="Crónicas, previas y resultados de Primera, Segunda y Tercera Federación y del fútbol regional",
        lateral=_lateral(cfg, previas or cronicas)))
    (SALIDA / "rfef.html").write_text(_pagina(
        cfg, f"RFEF · {nombre}", '<h1 class="sec tit">Primera, Segunda y Tercera Federación</h1>'
        + _portada(principal[:60], extra=_bloque_noticias(noticias_rfef[:6]), cfg=cfg), activa="rfef.html",
        descripcion="Crónicas, previas y noticias de Primera, Segunda y Tercera Federación", ticker=_ticker(arts, ""),
        lateral=_lateral(cfg, previas or cronicas)))
    (SALIDA / "mas-futbol.html").write_text(_pagina(
        cfg, f"Más fútbol · {nombre}", '<h1 class="sec tit">Más fútbol</h1>'
        + _portada(secundario[:60], extra=_bloque_noticias(noticias_mas[:6]), cfg=cfg), activa="mas-futbol.html",
        descripcion="Segunda División, copas, selecciones y primeras divisiones", ticker=_ticker(arts, ""),
        lateral=_lateral(cfg, previas_mas or secundario)))
    (SALIDA / "regionales.html").write_text(_pagina(
        cfg, f"Regionales · {nombre}", _pagina_regionales(regs, rc), activa="regionales.html",
        descripcion="Los partidos gordos del fútbol regional de toda España", ticker=_ticker(arts, ""),
        lateral=_lateral(cfg, cronicas, titulo="Lo último de la RFEF")))
    for viejo, nuevo in [("espana.html", "rfef.html"), ("internacional.html", "mas-futbol.html")]:  # enlaces antiguos
        (SALIDA / viejo).write_text(f'<!doctype html><meta charset="utf-8"><meta http-equiv="refresh" content="0;url={nuevo}">'
                                    f'<link rel="canonical" href="{nuevo}"><a href="{nuevo}">{nuevo}</a>')
    (SALIDA / "partidos.html").write_text(
        _pagina(cfg, f"Partidos de hoy y mañana · {nombre}", _agenda(agenda), activa="partidos.html",
                descripcion="Horarios de los partidos de hoy y mañana", ticker=_ticker(arts, "")))
    (SALIDA / "resultados.html").write_text(
        _pagina(cfg, f"Resultados · {nombre}", _resultados(arts), activa="resultados.html", ticker=_ticker(arts, "")))

    ligas = _ligas(arts)
    LIGAS.clear()
    LIGAS.update(ligas, (c["etiqueta"] for c in cfg.get("competiciones", [])))
    (SALIDA / "ligas.html").write_text(
        _pagina(cfg, f"Ligas · {nombre}", _indice_ligas(cfg, ligas), activa="ligas.html", ticker=_ticker(arts, "")))
    for etiqueta, lista in ligas.items():
        (SALIDA / "ligas" / f"{_slug_liga(etiqueta)}.html").write_text(
            _pagina(cfg, f"{etiqueta} · {nombre}", _pagina_liga(etiqueta, lista), "../",
                    f"Resultados, clasificación y noticias de {etiqueta}", ticker=_ticker(arts, "../"),
                    activa=_nav_de(lista[0].get("competicion", etiqueta))))
    for c in cfg.get("competiciones", []):  # competiciones con grupos o sin partidos todavía
        if c["etiqueta"] in ligas:
            continue
        (SALIDA / "ligas" / f"{_slug_liga(c['etiqueta'])}.html").write_text(
            _pagina(cfg, f"{c['etiqueta']} · {nombre}", _pagina_competicion(c, ligas), "../",
                    f"Resultados, clasificación y noticias de {c['etiqueta']}", ticker=_ticker(arts, "../"),
                    activa=_nav_de(c["etiqueta"])))

    for a in arts:
        fotos = "".join(f'<img src="../{i}" alt="{_e(a["etiqueta"])}" loading="lazy">' for i in _imagenes(a))
        texto = markdown.markdown(a["cuerpo_markdown"], extensions=["tables", "toc"],
                                  extension_configs={"toc": {"slugify": lambda t, sep: _ancla(t)}})
        cuerpo = (_migas(a, "../") + f'<article><span class="tag">{_e(_etiqueta(a))}</span><h1 class="tit">{_e(a["titular"])}</h1>'
                  f'<p class="entradilla">{_e(a["entradilla"])}</p>'
                  f'<div class="firma-art">Por <b>Redacción {_e(nombre)}</b> · {fecha_larga(a["fecha"])}</div>'
                  + _enlace_estrella(a)
                  + (f'<div class="fotos">{fotos}</div>' if fotos else "")
                  + f'<div class="cuerpo">{_con_anuncio(cfg, texto)}</div>' + _estadisticas_partidos(a) + _mini_clasificacion(a)
                  + _anuncio(cfg, "final_articulo", "txt")
                  + _relacionados(a, arts, "../")
                  + '<a class="volver" href="../index.html">← Volver a la portada</a></article>')
        mismos = [x for x in arts if x.get("competicion") == a.get("competicion") and x["slug"] != a["slug"]]
        (SALIDA / "articulos" / f"{a['slug']}.html").write_text(
            _pagina(cfg, f"{a['titular']} · {nombre}", cuerpo, "../", a["entradilla"], ticker=_ticker(arts, "../"),
                    activa=_nav_de(a.get("competicion")),
                    lateral=_lateral(cfg, mismos, "../", f'Más de {a.get("competicion") or a["etiqueta"]}')))

    (SALIDA / "previas").mkdir()
    for a in arts:  # una página por partido con su previa completa
        partidos = {p["id"]: p for p in a.get("proximos", [])}
        for pp in a.get("previas_partido", []):
            if pp["id"] in partidos:
                (SALIDA / "previas" / f'{pp["slug"]}.html').write_text(
                    _pagina(cfg, f'{pp["titular"]} · {nombre}', _pagina_previa(cfg, a, pp, partidos[pp["id"]]), "../",
                            pp["entradilla"], ticker=_ticker(arts, "../"), activa=_nav_de(a.get("competicion"))))

    (SALIDA / "cronicas").mkdir()
    for a in arts:  # crónica propia del partido estrella de cada grupo de 1ª y 2ª RFEF
        ce = a.get("cronica_estrella")
        pe = next((p for p in a.get("partidos", []) if ce and p["id"] == ce.get("partido_id")), None)
        if pe:
            (SALIDA / "cronicas" / f'{ce["slug"]}.html').write_text(
                _pagina(cfg, f'{ce["titular"]} · {nombre}', _pagina_cronica_estrella(cfg, a, ce, pe), "../",
                        ce["entradilla"], ticker=_ticker(arts, "../"), activa=_nav_de(a.get("competicion"))))

    (SALIDA / "noticias").mkdir()
    for n in NOTICIAS:  # una página por noticia
        (SALIDA / "noticias" / f'{n["slug"]}.html').write_text(
            _pagina(cfg, f'{n["titular"]} · {nombre}', _pagina_noticia(n, cfg), "../", n["entradilla"],
                    ticker=_ticker(arts, "../"), activa=_nav_de(n.get("competicion")),
                    lateral=_lateral(cfg, [x for x in NOTICIAS if x["slug"] != n["slug"]], "../", "Más noticias")))

    _historias(cfg)
    _paginas_legales(cfg)
    _rss(cfg, sorted(arts[:40] + NOTICIAS[:20], key=lambda a: a["fecha"], reverse=True))
    (SALIDA / ".nojekyll").write_text("")
    return SALIDA


def _pagina_noticia(n: dict, cfg: dict) -> str:
    prof = "../"
    f = n.get("fuente")
    fuente = (f'<p class="fuente">Fuente: <a href="{_e(f["url"])}" rel="noopener nofollow" target="_blank">{_e(f["medio"])}</a>'
              f' · «{_e(f["titular"])}». Noticia redactada por nuestra redacción a partir de esa información.</p>') if f else ""
    relacionadas = [x for x in NOTICIAS if x["slug"] != n["slug"] and x.get("competicion") == n.get("competicion")][:3]
    pagina = n["etiqueta"] if n["etiqueta"] in LIGAS else n.get("competicion", n["etiqueta"])
    return (f'<article><a class="tag" href="{prof}ligas/{_slug_liga(pagina)}.html">{_e(_etiqueta(n))} →</a>'
            f'<h1 class="tit">{_e(n["titular"])}</h1><p class="entradilla">{_e(n["entradilla"])}</p>'
            f'<div class="firma-art">Por <b>Redacción {_e(cfg["medio"]["nombre"])}</b> · {fecha_larga(n["fecha"])}</div>'
            f'<div class="cuerpo">{_con_anuncio(cfg, markdown.markdown(n["cuerpo_markdown"]))}</div>' + fuente
            + _anuncio(cfg, "final_articulo", "txt")
            + _bloque_noticias(relacionadas, prof, "Más noticias")
            + f'<a class="volver" href="{prof}index.html">← Volver a la portada</a></article>')


def _historias(cfg: dict):
    """historias.html (sin enlace en el menú): las historias del día para guardarlas y subirlas desde el móvil."""
    archivos = sorted((CONTENIDO / "instagram").glob("*-historias.json"), reverse=True)[:3]
    bloques = []
    for n, f in enumerate(archivos):
        h = json.loads(f.read_text())
        fotos = "".join(f'<a href="{i}" download><img src="{i}" alt="Historia" loading="lazy" '
                        f'style="width:100%;max-width:360px;border-radius:12px;margin:8px 0"></a>' for i in h["imagenes"])
        lista = html.escape(json.dumps(h["imagenes"]))
        zip_nombre = f"historias-{h['fecha']}.zip"  # por si el móvil no deja compartir varias fotos a la vez
        with zipfile.ZipFile(SALIDA / zip_nombre, "w") as z:
            for k, i in enumerate(h["imagenes"], 1):
                if (CONTENIDO / i).exists():
                    z.write(CONTENIDO / i, f"{k}-{Path(i).name}")
        boton = ('<button class="btn-historias" data-imgs="{l}" data-zip="{z}" '
                 'style="background:#FFD400;color:#111;border:0;border-radius:10px;padding:14px 22px;'
                 'font-weight:800;font-size:17px;margin:8px 0 14px;cursor:pointer">'
                 '⬇ Guardar todas ({k})</button>').format(l=lista, z=zip_nombre, k=len(h["imagenes"]))
        bloques.append(f'<h2>Historias del {fecha_larga(h["fecha"])}</h2>{boton}'
                       f'<p>En el móvil se abre el menú de compartir: elige "Guardar imágenes" (o "Guardar en Fotos") '
                       f'y se guardan todas de golpe. También puedes mantener pulsada cada una.</p>'
                       f'<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:10px">{fotos}</div>')
    bloques.append('''<script>
document.querySelectorAll(".btn-historias").forEach(b => b.addEventListener("click", async () => {
  const urls = JSON.parse(b.dataset.imgs), texto = b.textContent;
  b.textContent = "Preparando…";
  try {
    const files = await Promise.all(urls.map(async (u, i) =>
      new File([await (await fetch(u)).blob()], (i + 1) + "-" + u.split("/").pop(), {type: "image/jpeg"})));
    if (navigator.canShare && navigator.canShare({files})) await navigator.share({files});
    else location.href = b.dataset.zip;
  } catch (e) { if (e.name !== "AbortError") location.href = b.dataset.zip; }
  b.textContent = texto;
}));
</script>''')
    cuerpo = "<article>" + ("".join(bloques) or "<p>Todavía no hay historias.</p>") + "</article>"
    (SALIDA / "historias.html").write_text(
        _pagina(cfg, f"Historias · {cfg['medio']['nombre']}", cuerpo, descripcion="Historias de Instagram del día"))


LEGALES = [("aviso-legal", "Aviso legal"), ("privacidad", "Política de privacidad"), ("cookies", "Política de cookies"),
           ("quienes-somos", "Quiénes somos"), ("contacto", "Contacto")]


def _paginas_legales(cfg: dict):
    """Aviso legal, privacidad, cookies, quiénes somos y contacto (textos en legal/*.md) + ads.txt para AdSense.
    Los huecos {titular}, {nif}, {ciudad}, {email} salen de config.yaml → legal. Si faltan, se marcan en amarillo."""
    datos = {k: str(v) for k, v in (cfg.get("legal") or {}).items() if v}
    pendiente = {"titular": "[nombre y apellidos]", "nif": "[NIF]", "ciudad": "[ciudad]", "email": "[correo de contacto]"}
    for nombre, titulo in LEGALES:
        f = RAIZ / "legal" / f"{nombre}.md"
        if not f.exists():
            continue
        texto = f.read_text()
        for k, hueco in pendiente.items():
            valor = datos.get(k)
            if k == "email" and valor:
                valor = f'<a href="mailto:{_e(valor)}">{_e(valor)}</a>'
            texto = texto.replace("{" + k + "}", valor if k == "email" and valor else
                                  _e(valor) if valor else f'<span class="pendiente">{hueco}</span>')
        texto = texto.replace("{nombre}", _e(cfg["medio"]["nombre"])).replace("{web}", _e(cfg["medio"]["url_web"]))
        cuerpo = f'<div class="legal">{markdown.markdown(texto, extensions=["tables"])}</div>'
        (SALIDA / f"{nombre}.html").write_text(
            _pagina(cfg, f"{titulo} · {cfg['medio']['nombre']}", cuerpo, descripcion=f"{titulo} de {cfg['medio']['nombre']}"))
    cli = PUBLI.get("cliente", "")
    if cli:  # Google pide este archivo en la raíz del dominio
        (SALIDA / "ads.txt").write_text(f"google.com, {cli.removeprefix('ca-')}, DIRECT, f08c47fec0942fa0\n")


def _rss(cfg: dict, arts: list[dict]):
    base = cfg["medio"]["url_web"].rstrip("/")
    items = "".join(
        f"<item><title>{html.escape(a['titular'])}</title><link>{base}/{_url(a, '')}</link>"
        f"<guid>{base}/{_url(a, '')}</guid><description>{html.escape(a['entradilla'])}</description>"
        f"<pubDate>{format_datetime(datetime.fromisoformat(a['fecha']).replace(tzinfo=timezone.utc))}</pubDate></item>"
        for a in arts)
    (SALIDA / "rss.xml").write_text(
        f'<?xml version="1.0" encoding="UTF-8"?><rss version="2.0"><channel><title>{html.escape(cfg["medio"]["nombre"])}</title>'
        f"<link>{base}</link><description>{html.escape(cfg['medio']['lema'])}</description>{items}</channel></rss>")
