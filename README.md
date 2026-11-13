# futbol-auto

Diario digital + Instagram automáticos sobre fútbol de categorías inferiores
(Segunda, Primera/Segunda/Tercera Federación y segundas-terceras categorías extranjeras).

## Probar en local sin ninguna clave

```bash
pip install -r requirements.txt
python -m pipeline generar --fecha 2026-11-08 --demo   # datos inventados, equipos ficticios
python -m pipeline web                                 # crea _site/ (abre _site/index.html)
python -m pipeline instagram --simular                 # muestra qué publicaría
```

## En producción

Todo corre en GitHub Actions:

- `.github/workflows/diario.yml`: cada mañana (y sábados/domingos por la noche) descarga resultados,
  redacta crónicas y genera imágenes. En `modo: revision` abre un Pull Request para aprobar.
- `.github/workflows/publicar.yml`: al aprobar, despliega la web en GitHub Pages y publica en Instagram.

Secrets necesarios: `API_FOOTBALL_KEY`, `ANTHROPIC_API_KEY`, `IG_USER_ID`, `IG_ACCESS_TOKEN`.
Edita `config.yaml` (nombre del medio, URL, competiciones, límites, modelo de IA).

## Estructura

| Archivo | Qué hace |
| --- | --- |
| `pipeline/fuentes.py` | API-Football: ligas, resultados, clasificaciones, goleadores |
| `pipeline/redactor.py` | Claude redacta la crónica solo con los datos (sin inventar) |
| `pipeline/tarjetas.py` | Imágenes 1080×1350 para el carrusel (gráficos propios, sin fotos con derechos) |
| `pipeline/web.py` | Genera la web estática y el RSS |
| `pipeline/instagram.py` | Publica vía la API oficial de Instagram, con límite diario |
| `contenido/` | Artículos (JSON) e imágenes generadas; es lo que revisas en cada PR |
