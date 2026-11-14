"""Temporal: comprueba qué fuentes RSS responden desde GitHub Actions. Se borra antes del PR."""
import re, html, requests
UA = {"User-Agent": "Mozilla/5.0 (compatible; SinFocosBot/1.0)"}
GN = "https://news.google.com/rss/search?hl=es&gl=ES&ceid=ES:es&q="
URLS = [
 GN + '%22Segunda+Federaci%C3%B3n%22+entrenador+when:2d',
 GN + '%22Primera+Federaci%C3%B3n%22+fichaje+when:3d',
 GN + '%22Tercera+Federaci%C3%B3n%22+entrenador+when:3d',
 "https://rfef.es/es/rss.xml", "https://rfef.es/rss.xml", "https://rfef.es/es/noticias/rss.xml",
 "https://feeds.as.com/mrss-s/pages/as/site/as.com/section/futbol/subsection/segunda/",
 "https://feeds.as.com/mrss-s/pages/as/site/as.com/section/futbol/subsection/primera_rfef/",
 "https://e00-marca.uecdn.es/rss/futbol/segunda-division.xml",
 "https://e00-marca.uecdn.es/rss/futbol/primera-rfef.xml",
 "https://e00-marca.uecdn.es/rss/futbol/futbol-modesto.xml",
 "https://www.mundodeportivo.com/rss/futbol/futbol-modesto",
 "https://www.lapreferente.com/rss.xml", "https://www.futbolme.com/rss.xml",
 "https://www.lacomarca.net/feed/", "https://www.diariobahiadecadiz.com/feed",
 "https://alicanteplaza.es/rss", "https://avilared.com/rss",
 "https://www.futbolregional.es/feed/", "https://www.tercerafederacion.es/feed/",
 "https://www.elperiodicodearagon.com/rss/section/2005", "https://www.lavozdegalicia.es/rss/deportes.xml",
 "https://www.ultimahora.es/rss/deportes.xml", "https://www.diariodeleon.es/rss/",
 "https://www.besoccer.com/rss", "https://es.besoccer.com/rss/noticias",
 "https://www.futbolfemenino.com/feed",
]
for u in URLS:
    try:
        r = requests.get(u, headers=UA, timeout=20)
        t = r.text
        items = re.findall(r"<(?:item|entry)\b.*?</(?:item|entry)>", t, re.S)
        print(f"\n== {r.status_code} {len(items)} items {u}")
        for it in items[:3]:
            ti = re.search(r"<title[^>]*>(.*?)</title>", it, re.S)
            de = re.search(r"<(?:description|summary|content:encoded)[^>]*>(.*?)</", it, re.S)
            li = re.search(r"<link[^>]*>(.*?)</link>|<link[^>]*href=\"([^\"]+)\"", it, re.S)
            limpio = lambda s: re.sub(r"<[^>]+>|<!\[CDATA\[|\]\]>", " ", html.unescape(s or ""))
            print("  -", limpio(ti.group(1) if ti else "")[:110].strip(), "| desc", len(limpio(de.group(1) if de else "")), "| link", (li.group(1) or li.group(2) if li else "")[:90])
        if "news.google" in u and items:
            link = re.search(r"<link>(.*?)</link>", items[0]).group(1)
            rr = requests.get(link, headers=UA, timeout=20)
            print("  GN resuelve ->", rr.status_code, rr.url[:120], len(rr.text))
    except Exception as e:
        print(f"\n== ERROR {u}: {e}")
