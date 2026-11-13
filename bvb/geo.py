"""Países de destino: nombre en español (como lo da Travelpayouts) → código ISO y región.

Lo usan el explorador por presupuesto (filtro por región y bandera del destino),
las páginas de visas y las de feriados. Las banderas están en static/flags/<cc>.png
(48x36, de flag-icons, licencia MIT); un país sin bandera simplemente no la muestra.
"""
import unicodedata

REGIONS = {
    "norteamerica": "Norteamérica",
    "centroamerica": "Centroamérica",
    "caribe": "Caribe",
    "sudamerica": "Sudamérica",
    "europa": "Europa",
    "asia": "Asia y Oceanía",
    "otros": "Medio Oriente y África",
}

# nombre en español → (código ISO-2, región)
COUNTRIES = {
    "EE. UU.": ("us", "norteamerica"), "Estados Unidos": ("us", "norteamerica"),
    "Canadá": ("ca", "norteamerica"), "México": ("mx", "norteamerica"),
    "Guatemala": ("gt", "centroamerica"), "Belice": ("bz", "centroamerica"),
    "El Salvador": ("sv", "centroamerica"), "Honduras": ("hn", "centroamerica"),
    "Nicaragua": ("ni", "centroamerica"), "Costa Rica": ("cr", "centroamerica"),
    "Panamá": ("pa", "centroamerica"),
    "Cuba": ("cu", "caribe"), "República Dominicana": ("do", "caribe"), "Puerto Rico": ("pr", "caribe"),
    "Jamaica": ("jm", "caribe"), "Haití": ("ht", "caribe"), "Aruba": ("aw", "caribe"),
    "Curazao": ("cw", "caribe"), "Bahamas": ("bs", "caribe"), "Barbados": ("bb", "caribe"),
    "Santa Lucía": ("lc", "caribe"), "Trinidad y Tobago": ("tt", "caribe"), "San Martín": ("sx", "caribe"),
    "Guadalupe": ("gp", "caribe"), "Martinica": ("mq", "caribe"), "Dominica": ("dm", "caribe"),
    "Islas Vírgenes de los Estados Unidos": ("vi", "caribe"), "Islas Caimán": ("ky", "caribe"),
    "Granada": ("gd", "caribe"), "Antigua y Barbuda": ("ag", "caribe"), "Bonaire": ("bq", "caribe"),
    "San Vicente y las Granadinas": ("vc", "caribe"), "Islas Turcas y Caicos": ("tc", "caribe"),
    "Colombia": ("co", "sudamerica"), "Venezuela": ("ve", "sudamerica"), "Ecuador": ("ec", "sudamerica"),
    "Perú": ("pe", "sudamerica"), "Bolivia": ("bo", "sudamerica"), "Brasil": ("br", "sudamerica"),
    "Chile": ("cl", "sudamerica"), "Argentina": ("ar", "sudamerica"), "Uruguay": ("uy", "sudamerica"),
    "Paraguay": ("py", "sudamerica"), "Guyana": ("gy", "sudamerica"), "Surinam": ("sr", "sudamerica"),
    "Guayana Francesa": ("gf", "sudamerica"),
    "España": ("es", "europa"), "Portugal": ("pt", "europa"), "Francia": ("fr", "europa"),
    "Italia": ("it", "europa"), "Alemania": ("de", "europa"), "Reino Unido": ("gb", "europa"),
    "Irlanda": ("ie", "europa"), "Países Bajos": ("nl", "europa"), "Bélgica": ("be", "europa"),
    "Suiza": ("ch", "europa"), "Austria": ("at", "europa"), "Grecia": ("gr", "europa"),
    "Polonia": ("pl", "europa"), "Hungría": ("hu", "europa"), "República Checa": ("cz", "europa"),
    "Chequia": ("cz", "europa"), "Serbia": ("rs", "europa"), "Croacia": ("hr", "europa"),
    "Rumania": ("ro", "europa"), "Rumanía": ("ro", "europa"), "Bulgaria": ("bg", "europa"),
    "Finlandia": ("fi", "europa"), "Suecia": ("se", "europa"), "Noruega": ("no", "europa"),
    "Dinamarca": ("dk", "europa"), "Islandia": ("is", "europa"), "Estonia": ("ee", "europa"),
    "Letonia": ("lv", "europa"), "Lituania": ("lt", "europa"), "Rusia": ("ru", "europa"),
    "Ucrania": ("ua", "europa"), "Georgia": ("ge", "europa"), "Turquía": ("tr", "europa"),
    "Malta": ("mt", "europa"), "Chipre": ("cy", "europa"), "Luxemburgo": ("lu", "europa"),
    "Eslovaquia": ("sk", "europa"), "Eslovenia": ("si", "europa"), "Albania": ("al", "europa"),
    "Azerbaiyán": ("az", "asia"), "Armenia": ("am", "asia"), "Kazajistán": ("kz", "asia"),
    "Uzbekistán": ("uz", "asia"),
    "República Popular China": ("cn", "asia"), "China": ("cn", "asia"), "Hong Kong": ("hk", "asia"),
    "Japón": ("jp", "asia"), "Corea del Sur": ("kr", "asia"), "Taiwán": ("tw", "asia"),
    "Tailandia": ("th", "asia"), "Vietnam": ("vn", "asia"), "Singapur": ("sg", "asia"),
    "Malasia": ("my", "asia"), "Indonesia": ("id", "asia"), "Filipinas": ("ph", "asia"),
    "India": ("in", "asia"), "Sri Lanka": ("lk", "asia"), "Maldivas": ("mv", "asia"),
    "Australia": ("au", "asia"), "Nueva Zelanda": ("nz", "asia"), "Polinesia Francesa": ("pf", "asia"),
    "Emiratos Árabes Unidos": ("ae", "otros"), "Catar": ("qa", "otros"), "Israel": ("il", "otros"),
    "Jordania": ("jo", "otros"), "Arabia Saudita": ("sa", "otros"), "Egipto": ("eg", "otros"),
    "Marruecos": ("ma", "otros"), "Sudáfrica": ("za", "otros"), "Kenia": ("ke", "otros"),
    "Tanzania": ("tz", "otros"), "Madagascar": ("mg", "otros"), "Etiopía": ("et", "otros"),
    "Nigeria": ("ng", "otros"), "Senegal": ("sn", "otros"), "Ghana": ("gh", "otros"),
    "Mauricio": ("mu", "otros"), "Seychelles": ("sc", "otros"), "Túnez": ("tn", "otros"),
}


def _plain(s: str) -> str:
    return unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower().strip()


_BY_PLAIN = {_plain(k): v for k, v in COUNTRIES.items()}


def country(name: str) -> tuple[str, str]:
    """('es', 'europa') para 'España'; ('', 'otros') si no se conoce."""
    return COUNTRIES.get(name) or _BY_PLAIN.get(_plain(name)) or ("", "otros")


def cc(name: str) -> str:
    return country(name)[0]


def region(name: str) -> str:
    return country(name)[1]
