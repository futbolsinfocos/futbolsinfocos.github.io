"""Nombres de selecciones y equipos en español.

API-Football da los nombres en inglés (o sin tildes). Aquí se traducen antes de guardarlos,
para que web, tarjetas de Instagram y crónicas salgan en español. Para añadir uno, basta
con una línea más: "Nombre en la API": "Nombre en español".
"""
from __future__ import annotations

SELECCIONES = {
    "Albania": "Albania", "Andorra": "Andorra", "Armenia": "Armenia", "Austria": "Austria",
    "Azerbaijan": "Azerbaiyán", "Belarus": "Bielorrusia", "Belgium": "Bélgica",
    "Bosnia & Herzegovina": "Bosnia y Herzegovina", "Bosnia and Herzegovina": "Bosnia y Herzegovina",
    "Bulgaria": "Bulgaria", "Croatia": "Croacia", "Cyprus": "Chipre", "Czech Republic": "Chequia",
    "Czechia": "Chequia", "Denmark": "Dinamarca", "England": "Inglaterra", "Estonia": "Estonia",
    "Faroe Islands": "Islas Feroe", "Finland": "Finlandia", "France": "Francia", "Georgia": "Georgia",
    "Germany": "Alemania", "Gibraltar": "Gibraltar", "Greece": "Grecia", "Hungary": "Hungría",
    "Iceland": "Islandia", "Ireland": "Irlanda", "Republic of Ireland": "Irlanda", "Israel": "Israel",
    "Italy": "Italia", "Kazakhstan": "Kazajistán", "Kosovo": "Kosovo", "Latvia": "Letonia",
    "Liechtenstein": "Liechtenstein", "Lithuania": "Lituania", "Luxembourg": "Luxemburgo",
    "Malta": "Malta", "Moldova": "Moldavia", "Montenegro": "Montenegro", "Netherlands": "Países Bajos",
    "North Macedonia": "Macedonia del Norte", "FYR Macedonia": "Macedonia del Norte",
    "Northern Ireland": "Irlanda del Norte", "Norway": "Noruega", "Poland": "Polonia",
    "Portugal": "Portugal", "Romania": "Rumanía", "Russia": "Rusia", "San Marino": "San Marino",
    "Scotland": "Escocia", "Serbia": "Serbia", "Slovakia": "Eslovaquia", "Slovenia": "Eslovenia",
    "Spain": "España", "Sweden": "Suecia", "Switzerland": "Suiza", "Turkey": "Turquía",
    "Türkiye": "Turquía", "Ukraine": "Ucrania", "Wales": "Gales",
    "Argentina": "Argentina", "Brazil": "Brasil", "Mexico": "México", "USA": "Estados Unidos",
    "United States": "Estados Unidos", "Canada": "Canadá", "Morocco": "Marruecos", "Japan": "Japón",
    "South Korea": "Corea del Sur", "Korea Republic": "Corea del Sur", "Peru": "Perú",
    "Egypt": "Egipto", "Algeria": "Argelia", "Tunisia": "Túnez", "Cameroon": "Camerún",
    "Ivory Coast": "Costa de Marfil", "Saudi Arabia": "Arabia Saudí", "New Zealand": "Nueva Zelanda",
    "Australia": "Australia", "Chile": "Chile", "Colombia": "Colombia", "Uruguay": "Uruguay",
}

CLUBES = {
    # España (la API suele quitar tildes o usar el nombre inglés)
    "Atletico Madrid": "Atlético de Madrid", "Alaves": "Alavés", "Leganes": "Leganés",
    "Cadiz": "Cádiz", "Malaga": "Málaga", "Almeria": "Almería", "Cordoba": "Córdoba",
    "Deportivo La Coruna": "Deportivo de La Coruña", "Sporting Gijon": "Sporting de Gijón",
    "Celta Vigo": "Celta de Vigo", "Mirandes": "Mirandés", "Castellon": "Castellón",
    "Racing Santander": "Racing de Santander", "Racing Ferrol": "Racing de Ferrol",
    "Merida AD": "Mérida", "Gimnastic": "Nàstic de Tarragona", "Gimnastic Tarragona": "Nàstic de Tarragona",
    "Sevilla Atletico": "Sevilla Atlético", "Atletico Madrid II": "Atlético de Madrid B",
    "Real Madrid II": "Real Madrid Castilla", "UD Logrones": "UD Logroñés", "SD Logrones": "SD Logroñés",
    "Alcorcon": "Alcorcón",
    # Extranjero, solo cuando hay nombre español de uso común
    "Bayern Munich": "Bayern de Múnich", "Bayern München": "Bayern de Múnich",
    "Inter": "Inter de Milán", "AC Milan": "Milan", "Napoli": "Nápoles",
    "Sporting CP": "Sporting de Portugal", "FC Porto": "Oporto",
    "Paris Saint Germain": "PSG", "Olympique Marseille": "Olympique de Marsella",
    "Olympique Lyonnais": "Olympique de Lyon", "Lyon": "Olympique de Lyon", "Marseille": "Olympique de Marsella",
}

_TODOS = {**SELECCIONES, **CLUBES}


def es(nombre: str | None) -> str | None:
    """Devuelve el nombre en español si lo conocemos; si no, el original."""
    if not nombre:
        return nombre
    return _TODOS.get(nombre, nombre)
