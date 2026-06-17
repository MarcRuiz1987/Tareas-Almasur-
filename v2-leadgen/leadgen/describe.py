"""Descripción de empresa con Claude (Haiku) a partir del texto del sitio web."""

from __future__ import annotations

from . import llm
from .models import Empresa
from .website import texto_de_sitio


def describir(empresa: Empresa) -> Empresa:
    """Rellena descripcion, sector, tamano_estimado y senales de la empresa."""
    if not empresa.sitio_web:
        return empresa
    texto = texto_de_sitio(empresa.sitio_web)
    if not texto.strip():
        return empresa
    try:
        d = llm.describir_empresa(empresa.nombre, texto)
    except Exception:
        return empresa
    empresa.descripcion = d.descripcion
    empresa.sector = d.sector
    empresa.tamano_estimado = d.tamano_estimado
    empresa.senales = d.senales
    return empresa
