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

# SEIA (registro público de proyectos ambientales de Chile). No requiere clave.
# Pausa opcional entre consultas para ser amable con el servidor del SEA.
try:
    SEIA_PAUSA_SEG = float(os.getenv("SEIA_PAUSA_SEG", "0.3"))
except ValueError:
    SEIA_PAUSA_SEG = 0.3

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
    # SEIA — titular + representante legal con contacto (registro público)
    "seia_titular": ["titular seia", "titular (seia)", "razon social seia"],
    "seia_titular_email": ["email titular", "correo titular"],
    "seia_titular_telefono": ["telefono titular", "teléfono titular"],
    "seia_rep_legal": ["representante legal", "rep legal", "representante"],
    "seia_rep_email": ["email representante legal", "email representante", "correo representante", "email rep legal"],
    "seia_rep_telefono": ["telefono representante legal", "teléfono representante", "telefono rep legal"],
    "seia_expediente": ["expediente seia", "ficha seia", "expediente"],
}

# Encabezado canónico para columnas que se crean si no existen. Si un campo no
# aparece aquí, se usa el primer alias en mayúsculas de título (ver sheet.py).
# Necesario para respetar la sigla "SEIA" y los acentos, que .title() destruiría.
ENCABEZADOS_CANONICOS: dict[str, str] = {
    "seia_titular": "Titular (SEIA)",
    "seia_titular_email": "Email Titular",
    "seia_titular_telefono": "Teléfono Titular",
    "seia_rep_legal": "Representante Legal",
    "seia_rep_email": "Email Representante Legal",
    "seia_rep_telefono": "Teléfono Representante Legal",
    "seia_expediente": "Expediente SEIA",
}

# Campos que se pueden completar y el grupo al que pertenecen (para --campos).
GRUPOS_CAMPOS: dict[str, list[str]] = {
    "rut": ["rut"],
    "web": ["sitio_web", "dominio", "telefono", "direccion"],
    "contactos": ["contacto", "cargo", "email", "telefono_contacto", "linkedin"],
    "seia": [
        "seia_titular",
        "seia_titular_email",
        "seia_titular_telefono",
        "seia_rep_legal",
        "seia_rep_email",
        "seia_rep_telefono",
        "seia_expediente",
    ],
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
        "seia": True,  # registro público: no necesita clave
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
