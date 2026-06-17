"""Configuración central de la v2.

Carga las claves de API desde el entorno (.env) y define los rubros y comunas
objetivo. Para adaptar la herramienta a un nuevo rubro o zona, edita RUBROS y
COMUNAS — el resto del pipeline las consume sin más cambios.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # python-dotenv es opcional; las claves pueden venir del entorno
    pass

# ─── Claves de API (vía .env — ver .env.example) ──────────────────────────────

GOOGLE_PLACES_API_KEY = os.getenv("GOOGLE_PLACES_API_KEY", "")
HUNTER_API_KEY = os.getenv("HUNTER_API_KEY", "")
FULLENRICH_API_KEY = os.getenv("FULLENRICH_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

# ─── Modelos de Claude ────────────────────────────────────────────────────────
# Descripción de empresa a volumen → Haiku (barato y rápido).
# Calificación de ajuste al ICP → Sonnet (más capaz, donde la calidad importa).
MODELO_DESCRIPCION = "claude-haiku-4-5"
MODELO_CALIFICACION = "claude-sonnet-4-6"

# ─── Rubros objetivo ──────────────────────────────────────────────────────────
# slug → (nombre legible, término de búsqueda base para Google Places)
RUBROS: dict[str, tuple[str, str]] = {
    "logistica": ("Logística", "empresa logística"),
    "ecommerce": ("E-commerce", "ecommerce tienda online con bodega"),
    "distribucion": ("Distribución", "distribuidora"),
    "importadores": ("Importadores", "importadora"),
    "manufactura": ("Manufactura", "manufactura liviana"),
    "exportadores": ("Exportadores", "exportadora"),
    "tecnicos": ("Serv. Técnicos", "servicios técnicos industriales"),
}

# ─── Comunas / zonas objetivo (Chile) ─────────────────────────────────────────
COMUNAS_DEFAULT = [
    "Pudahuel, Santiago",
    "Quilicura, Santiago",
    "Maipú, Santiago",
    "San Bernardo, Santiago",
    "Colina, Santiago",
]

# ─── Parámetros del pipeline ──────────────────────────────────────────────────
MIN_RESENAS = 3
DEFAULT_MAX = 50
REGION_CODE = "cl"  # sesga Google Places hacia Chile
LANGUAGE_CODE = "es"

# ─── Rutas ────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
CLIENTS_DIR = BASE_DIR / "clients"
ICP_CACHE = CLIENTS_DIR / "icp_profile.json"


@dataclass
class MissingKey:
    """Pequeña ayuda para reportar claves faltantes de forma legible."""

    name: str
    why: str


def claves_faltantes() -> list[MissingKey]:
    """Devuelve las claves de pago que faltan, para avisar antes de correr."""
    faltan: list[MissingKey] = []
    if not GOOGLE_PLACES_API_KEY:
        faltan.append(MissingKey("GOOGLE_PLACES_API_KEY", "descubrimiento de empresas"))
    if not HUNTER_API_KEY:
        faltan.append(MissingKey("HUNTER_API_KEY", "descubrir contactos por dominio"))
    if not FULLENRICH_API_KEY:
        faltan.append(MissingKey("FULLENRICH_API_KEY", "enriquecer email + teléfono"))
    if not ANTHROPIC_API_KEY:
        faltan.append(MissingKey("ANTHROPIC_API_KEY", "descripción y calificación ICP"))
    return faltan


def resolver_rubro(slug: str) -> tuple[str, str]:
    """slug → (nombre, query). Lanza ValueError si el rubro no existe."""
    slug = slug.lower().strip()
    if slug not in RUBROS:
        opciones = ", ".join(RUBROS)
        raise ValueError(f"Rubro desconocido: '{slug}'. Opciones: {opciones}")
    return RUBROS[slug]
