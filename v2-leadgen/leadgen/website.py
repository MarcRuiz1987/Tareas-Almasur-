"""Acceso al sitio web de la empresa (Scrapling).

Baja la home y páginas de contacto/nosotros para alimentar la descripción (Claude)
y como fallback de contactos. Reutiliza las constantes y la lógica de regex de la
v1 (`procentro_leads.py`).
"""

from __future__ import annotations

import re
import time

# Rutas habituales donde viven contactos / descripción (reusado de la v1).
CONTACT_PATHS = [
    "/contacto",
    "/contact",
    "/nosotros",
    "/equipo",
    "/about",
    "/team",
    "/quienes-somos",
]
CARGO_KEYWORDS = [
    "gerente",
    "jefe",
    "supervisor",
    "director",
    "encargado",
    "manager",
    "coordinador",
]
EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")


def _fetcher():
    """Devuelve un Scrapling Fetcher (import perezoso)."""
    from scrapling.fetchers import Fetcher

    return Fetcher()


def texto_de_sitio(website: str, max_paginas: int = 4) -> str:
    """Concatena el texto de la home + páginas de contacto/nosotros."""
    if not website:
        return ""
    fetcher = _fetcher()
    urls = [website] + [website.rstrip("/") + p for p in CONTACT_PATHS]
    partes: list[str] = []
    vistas = 0
    for url in urls:
        if vistas >= max_paginas:
            break
        try:
            page = fetcher.get(url, timeout=10)
            if not page or page.status != 200:
                continue
            partes.append(page.text or "")
            vistas += 1
            time.sleep(0.3)
        except Exception:
            continue
    return "\n\n".join(partes)


def extraer_contacto_de_sitio(website: str) -> tuple[str, str, str]:
    """Fallback regex: (email, nombre, cargo) desde el sitio web.

    Portado de `_extract_contact_from_html` / `enrich_from_website` de la v1.
    """
    if not website:
        return "", "", ""
    fetcher = _fetcher()
    urls = [website] + [website.rstrip("/") + p for p in CONTACT_PATHS]
    email = nombre = cargo = ""

    for url in urls:
        try:
            page = fetcher.get(url, timeout=10)
            if not page or page.status != 200:
                continue
        except Exception:
            continue

        if not email:
            for el in page.css('a[href^="mailto:"]'):
                addr = el.attrib.get("href", "").replace("mailto:", "").split("?")[0].strip()
                if EMAIL_RE.match(addr) and "noreply" not in addr and "example" not in addr:
                    email = addr
                    break
        if not email:
            m = EMAIL_RE.search(page.text or "")
            if m and "noreply" not in m.group() and "example" not in m.group():
                email = m.group()

        if not nombre:
            full_text = page.text or ""
            for kw in CARGO_KEYWORDS:
                pattern = (
                    rf"([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-záéíóúñ]+){{1,3}})"
                    rf"\s*[,\-–]?\s*({kw}[a-záéíóúñ\s]{{2,30}})"
                )
                m = re.search(pattern, full_text, re.IGNORECASE)
                if m:
                    nombre = m.group(1).strip()
                    cargo = m.group(2).strip().title()
                    break

        if email and nombre:
            break
        time.sleep(0.3)

    return email, nombre, cargo
