"""Resolver el RUT de una empresa chilena a partir de su nombre (razón social).

No existe una API pública única y gratuita de *nombre → RUT*, así que la v3 deja
el proveedor **configurable** vía entorno (ver ``config``):

  RUT_API_URL=https://api.tu-proveedor.cl/empresas?nombre={q}
  RUT_API_KEY=...                 # opcional; se envía como Bearer si está
  RUT_API_JSON_PATH=data.0.rut    # ruta (con puntos) al RUT en la respuesta JSON

Proveedores chilenos habituales que encajan en este patrón: SimpleAPI, Boostr,
LibreDTE y similares. Si no hay ``RUT_API_URL``, la función devuelve "" y el RUT
se deja para completar a mano.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from urllib.parse import quote

import requests

from . import config


def _por_ruta(data: object, ruta: str) -> str:
    """Navega un JSON con una ruta tipo 'data.0.rut' (índices = listas)."""
    actual = data
    for parte in ruta.split("."):
        if actual is None:
            return ""
        if isinstance(actual, list):
            try:
                actual = actual[int(parte)]
            except (ValueError, IndexError):
                return ""
        elif isinstance(actual, dict):
            actual = actual.get(parte)
        else:
            return ""
    return str(actual).strip() if actual not in (None, "") else ""


class RutProvider(ABC):
    @abstractmethod
    def disponible(self) -> bool: ...

    @abstractmethod
    def buscar(self, nombre: str) -> str: ...


class HttpRutProvider(RutProvider):
    """Proveedor genérico configurado por entorno (sirve para varios servicios)."""

    def disponible(self) -> bool:
        return bool(config.RUT_API_URL)

    def buscar(self, nombre: str) -> str:
        if not self.disponible() or not nombre:
            return ""
        url = config.RUT_API_URL.replace("{q}", quote(nombre))
        headers = {"Accept": "application/json"}
        if config.RUT_API_KEY:
            headers["Authorization"] = f"Bearer {config.RUT_API_KEY}"
        try:
            resp = requests.get(url, headers=headers, timeout=30)
            resp.raise_for_status()
            return _por_ruta(resp.json(), config.RUT_API_JSON_PATH)
        except (requests.RequestException, ValueError):
            return ""


_proveedor = HttpRutProvider()


def buscar_rut(nombre: str) -> str:
    """Devuelve el RUT de la empresa, o "" si no se pudo resolver."""
    return _proveedor.buscar(nombre)
