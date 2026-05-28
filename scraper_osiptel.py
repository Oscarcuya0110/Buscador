"""
scraper_osiptel.py
==================
Genera indice_normas_telecom.json a partir de páginas de normas de OSIPTEL.

Correcciones respecto al código original:
  - Bug crítico: "for palabra en" → "for palabra in"
  - Agrega campo "fecha" extraído del texto de cada item
  - Agrega campo "tipo" (Resolución CD, Decreto Supremo, etc.)
  - Apunta a URLs reales con contenido estático en lugar de la home 404
  - Estrategia multi-fuente: recorre varias páginas de normas
  - Normaliza tildes para búsqueda robusta de palabras clave
  - Pausa de cortesía entre requests para no saturar servidores del Estado
  - Manejo de errores por página (si una falla, continúa con las demás)
"""

import requests
from bs4 import BeautifulSoup
import json
import time
import re
import unicodedata

# ---------------------------------------------------------------------------
# 1. Configuración
# ---------------------------------------------------------------------------

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

BASE_URL = "https://www.osiptel.gob.pe"

# Páginas de OSIPTEL con listados de normas en HTML estático.
# El buscador oficial (/buscador-de-normas-y-regulaciones/) usa JS dinámico
# y no es scrapeble con requests+BeautifulSoup — estas páginas sí lo son.
URLS_OBJETIVO = [
    "/portal-de-transparencia/textos-actualizados-de-las-principales-normas/",
    "/portal-del-usuario/lo-que-debes-saber/normativas-de-usuarios/",
    "/portal-de-operadoras/solucion-de-controversias/secretaria-tecnica/normas/",
    "/portal-de-operadoras/solucion-de-controversias/tribunal-de-apelaciones/normas/",
    "/portal-de-operadoras/regulacion/regulacion-cargos-de-interconexion/",
]

# Palabras clave para el sector Telecomunicaciones.
# Se usa búsqueda normalizada (sin tildes, minúsculas) para mayor cobertura.
PALABRAS_CLAVE = [
    "telecomunicaciones",
    "osiptel",
    "servicios públicos de telecomunicaciones",
    "espectro radioeléctrico",
    "interconexión",
    "radiodifusión",
]

# Patrones para detectar el tipo de norma en el título o texto
PATRONES_TIPO = [
    (r"decreto supremo",           "Decreto Supremo"),
    (r"resolución de consejo|res[\.º]?\s*\d+-\d+-cd", "Resolución de Consejo Directivo"),
    (r"resolución ministerial",    "Resolución Ministerial"),
    (r"resolución presidencial",   "Resolución Presidencial"),
    (r"directiva",                 "Directiva"),
    (r"reglamento",                "Reglamento"),
    (r"lineamiento",               "Lineamiento"),
]

# Patrones para detectar fecha en formatos peruanos comunes
PATRONES_FECHA = [
    r"\b(\d{2})[/-](\d{2})[/-](\d{4})\b",          # DD/MM/YYYY o DD-MM-YYYY
    r"\b(\d{4})[/-](\d{2})[/-](\d{2})\b",          # YYYY-MM-DD
    r"\b(\d{1,2})\s+de\s+\w+\s+de\s+(\d{4})\b",   # D de Mes de YYYY
]

# ---------------------------------------------------------------------------
# 2. Utilidades
# ---------------------------------------------------------------------------

def normalizar(texto: str) -> str:
    """Convierte a minúsculas y elimina tildes para comparación robusta."""
    texto = texto.lower()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    return texto


def detectar_tipo(texto: str) -> str:
    t = normalizar(texto)
    for patron, etiqueta in PATRONES_TIPO:
        if re.search(patron, t):
            return etiqueta
    return "Norma"


def extraer_fecha(texto: str) -> str:
    """Intenta extraer una fecha del texto; devuelve string vacío si no encuentra."""
    # Formato YYYY-MM-DD (ISO, más confiable)
    m = re.search(r"\b(\d{4})-(\d{2})-(\d{2})\b", texto)
    if m:
        return m.group(0)
    # Formato DD/MM/YYYY
    m = re.search(r"\b(\d{2})/(\d{2})/(\d{4})\b", texto)
    if m:
        y, mo, d = m.group(3), m.group(2), m.group(1)
        return f"{y}-{mo}-{d}"
    return ""


def filtrar_por_palabras_clave(titulo: str, descripcion: str) -> list:
    """
    CORRECCIÓN CRÍTICA: el código original usaba 'for palabra en' (sintaxis
    inválida en Python). La keyword correcta es 'in'.
    Retorna lista de tags que coinciden con el texto.
    """
    texto_completo = normalizar(titulo + " " + descripcion)
    tags_encontrados = [
        palabra
        for palabra in PALABRAS_CLAVE          # ← 'in', no 'en'
        if normalizar(palabra) in texto_completo
    ]
    return tags_encontrados


# ---------------------------------------------------------------------------
# 3. Extracción por página
# ---------------------------------------------------------------------------

def extraer_normas_de_pagina(url_relativa: str) -> list:
    url = BASE_URL + url_relativa
    print(f"\n→ Scraping: {url}")

    try:
        respuesta = requests.get(url, headers=HEADERS, timeout=15)
        respuesta.raise_for_status()
    except requests.RequestException as e:
        print(f"  ✗ Error al conectar: {e}")
        return []

    soup = BeautifulSoup(respuesta.text, "html.parser")
    normas = []

    # OSIPTEL publica normas principalmente como listas de enlaces (<a>)
    # dentro del contenido principal. Buscamos todos los <a> con texto
    # sustantivo que apunten a documentos o sub-páginas.
    contenido = soup.find("main") or soup.find("div", class_=re.compile(r"content|main|entry"))
    if not contenido:
        contenido = soup  # fallback: todo el documento

    for enlace in contenido.find_all("a", href=True):
        href = enlace["href"].strip()
        titulo = enlace.get_text(separator=" ", strip=True)

        # Descartar enlaces de navegación cortos o sin texto útil
        if len(titulo) < 20:
            continue
        # Descartar enlaces de menú (rutas de navegación conocidas)
        if any(nav in href for nav in ["/portal-del-usuario/", "/portal-de-operadoras/",
                                        "#", "javascript:", "accesibilidad", "english"]):
            continue

        # Contexto adicional: párrafo o li padre para buscar fecha y descripción
        padre = enlace.find_parent(["li", "p", "div", "td"])
        contexto = padre.get_text(separator=" ", strip=True) if padre else titulo

        # Construir URL absoluta
        if href.startswith("http"):
            url_oficial = href
        elif href.startswith("/"):
            url_oficial = BASE_URL + href
        else:
            continue  # enlace relativo no manejable, omitir

        descripcion = contexto
        tags = filtrar_por_palabras_clave(titulo, descripcion)

        # Solo guardamos si hay match con palabras clave del sector
        if not tags:
            continue

        norma = {
            "titulo":      titulo,
            "tipo":        detectar_tipo(titulo + " " + contexto),
            "fecha":       extraer_fecha(contexto),
            "tags":        tags,
            "url_oficial": url_oficial,
            "fuente":      url,
        }
        normas.append(norma)
        print(f"  ✓ [{norma['tipo']}] {titulo[:70]}...")

    return normas


# ---------------------------------------------------------------------------
# 4. Deduplicación
# ---------------------------------------------------------------------------

def deduplicar(normas: list) -> list:
    """Elimina duplicados por url_oficial, conservando el primero encontrado."""
    vistas = set()
    resultado = []
    for n in normas:
        clave = n["url_oficial"]
        if clave not in vistas:
            vistas.add(clave)
            resultado.append(n)
    return resultado


# ---------------------------------------------------------------------------
# 5. Ejecución principal
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    todas_las_normas = []

    for url_relativa in URLS_OBJETIVO:
        normas_pagina = extraer_normas_de_pagina(url_relativa)
        todas_las_normas.extend(normas_pagina)
        # Pausa de cortesía entre requests (no saturar servidores del Estado)
        time.sleep(2)

    # Deduplicar y ordenar por fecha descendente (más recientes primero)
    resultado_final = deduplicar(todas_las_normas)
    resultado_final.sort(key=lambda n: n["fecha"], reverse=True)

    # Guardar JSON
    archivo_salida = "indice_normas_telecom.json"
    with open(archivo_salida, "w", encoding="utf-8") as f:
        json.dump(resultado_final, f, ensure_ascii=False, indent=4)

    print(f"\n{'='*60}")
    print(f"✅ Scraping completado.")
    print(f"   Normas encontradas : {len(resultado_final)}")
    print(f"   Archivo generado   : {archivo_salida}")
    print(f"{'='*60}")

    # Vista previa de los primeros 3 resultados
    if resultado_final:
        print("\nVista previa (primeras 3 normas):")
        for n in resultado_final[:3]:
            print(f"  - {n['titulo'][:60]}...")
            print(f"    tipo   : {n['tipo']}")
            print(f"    fecha  : {n['fecha'] or '(no detectada)'}")
            print(f"    tags   : {', '.join(n['tags'])}")
            print(f"    url    : {n['url_oficial']}")
