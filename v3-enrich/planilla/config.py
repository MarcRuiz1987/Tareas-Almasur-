"""Configuración central de la v3.

Carga las claves de API desde el entorno (.env) y define:
  - qué proveedores se usan para completar cada dato,
  - los *alias* de encabezado para detectar columnas en planillas heterogéneas,
  - los campos que la v3 sabe completar.

Para adaptar la herramienta a otra planilla, normalmente basta con ampliar
``ALIAS_COLUMNAS`` (encabezados equivalentes) — el resto del pipeline los consume.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # python-dotenv es opcional; las claves pueden venir del entorno
    pass

# ─── Claves de API (vía .env — ver .env.example) ──────────────────────────────

GOOGLE_PLACES_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY", "")
HUNTER_API_KEY = os.getenv("HUNTER_API_KEY", "")
FULLENRICH_API_KEY = os.getenv("FULLENRICH_API_KEY", "")

# Proveedor de RUT chileno (nombre de empresa → RUT). No hay un único servicio
# universal y gratuito, así que la v3 deja el endpoint **configurable**: define la
# URL con el marcador {q} (la consulta, URL-encoded) y, si el proveedor lo usa, la
# clave y la ruta JSON donde viene el RUT en la respuesta.
#   RUT_API_URL=https://api.tu-proveedor.cl/empresas?nombre={q}
#   RUT_API_KEY=...
#   RUT_API_JSON_PATH=data.0.rut        (ruta con puntos; índices numéricos = listas)
RUT_API_URL = os.getenv("RUT_API_URL", "")
RUT_API_KEY = os.getenv("RUT_API_KEY", "")
RUT_API_JSON_PATH = os.getenv("RUT_API_JSON_PATH", "rut")

# ─── Parámetros de descubrimiento (Google Places) ─────────────────────────────
REGION_CODE = "cl"
LANGUAGE_CODE = "es"

# ─── Alias de encabezado → campo lógico ───────────────────────────────────────
# Detección de columnas tolerante a mayúsculas, acentos y nombres alternativos.
# El primer alias de cada lista es el encabezado canónico que la v3 crea si la
# columna no existe.
ALIAS_COLUMNAS: dict[str, list[str]] = {
    # Identidad (entrada — debe existir al menos "empresa")
    "empresa": ["empresa", "nombre", "razon social", "razón social", "company"],
    "comuna": ["comuna", "ciudad", "localidad"],
    "region": ["region", "región"],
    # Campos que la v3 completa
    "rut": ["rut", "r.u.t", "tax id"],
    "sitio_web": ["sitio web", "sitio_web", "web", "website", "url"],
    "dominio": ["dominio", "domain"],
    "telefono": ["telefono", "teléfono", "fono", "phone"],
    "direccion": ["direccion", "dirección", "address"],
    "contacto": ["contacto", "nombre contacto", "nombre_contacto", "contact"],
    "cargo": ["cargo", "puesto", "position", "title"],
    "email": ["email", "correo", "e-mail", "mail"],
    "telefono_contacto": ["telefono contacto", "teléfono contacto", "celular", "movil", "móvil", "mobile"],
    "linkedin": ["linkedin", "linkedin url", "linkedin_url"],
}

# Campos que se pueden completar y el grupo al que pertenecen (para --campos).
GRUPOS_CAMPOS: dict[str, list[str]] = {
    "rut": ["rut"],
    "web": ["sitio_web", "dominio", "telefono", "direccion"],
    "contactos": ["contacto", "cargo", "email", "telefono_contacto", "linkedin"],
}


@dataclass
class MissingKey:
    name: str
    why: str


def claves_disponibles() -> dict[str, bool]:
    """Qué grupos de completado están operativos según las claves presentes."""
    return {
        "rut": bool(RUT_API_URL),
        "web": bool(GOOGLE_PLACES_API_KEY),
        "contactos": bool(HUNTER_API_KEY),
    }


def avisos_de_claves(campos_pedidos: set[str]) -> list[MissingKey]:
    """Claves que faltan para los grupos pedidos, para avisar antes de correr."""
    avisos: list[MissingKey] = []
    if "rut" in campos_pedidos and not RUT_API_URL:
        avisos.append(MissingKey("RUT_API_URL", "completar el RUT de cada empresa"))
    if "web" in campos_pedidos and not GOOGLE_PLACES_API_KEY:
        avisos.append(MissingKey("GOOGLE_PLACES_API_KEY", "resolver sitio web / teléfono / dirección"))
    if "contactos" in campos_pedidos and not HUNTER_API_KEY:
        avisos.append(MissingKey("HUNTER_API_KEY", "descubrir contactos por dominio"))
    if "contactos" in campos_pedidos and not FULLENRICH_API_KEY:
        avisos.append(MissingKey("FULLENRICH_API_KEY", "verificar email + teléfono del contacto"))
    return avisos
