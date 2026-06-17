"""Descubrimiento de empresas vía Google Places API (Text Search, API New).

Reemplaza el scraping de Google Maps de la v1 por una API oficial y estable, con
buena cobertura en Chile. Usa field masking para pagar sólo por los campos que se
necesitan.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

import requests

from . import config
from .models import Empresa

_ENDPOINT = "https://places.googleapis.com/v1/places:searchText"

# Campos que pedimos (field mask) — controla el costo de cada búsqueda.
_FIELD_MASK = ",".join(
    [
        "places.id",
        "places.displayName",
        "places.formattedAddress",
        "places.nationalPhoneNumber",
        "places.websiteUri",
        "places.rating",
        "places.userRatingCount",
        "places.businessStatus",
        "places.primaryType",
    ]
)


def _dominio(url: str) -> str:
    if not url:
        return ""
    try:
        host = urlparse(url).netloc.lower()
        return host[4:] if host.startswith("www.") else host
    except ValueError:
        return ""


def buscar_empresas(
    rubro_query: str,
    comuna: str,
    rubro_nombre: str = "",
    max_resultados: int = config.DEFAULT_MAX,
) -> list[Empresa]:
    """Busca empresas de un rubro en una comuna.

    Args:
        rubro_query: término base del rubro (p. ej. "empresa logística").
        comuna: zona objetivo (p. ej. "Pudahuel, Santiago").
        rubro_nombre: etiqueta legible que se guarda en cada Empresa.
        max_resultados: tope de empresas a devolver.
    """
    if not config.GOOGLE_PLACES_API_KEY:
        raise RuntimeError("Falta GOOGLE_PLACES_API_KEY en el entorno (.env).")

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": config.GOOGLE_PLACES_API_KEY,
        "X-Goog-FieldMask": _FIELD_MASK + ",nextPageToken",
    }
    body = {
        "textQuery": f"{rubro_query} en {comuna}",
        "regionCode": config.REGION_CODE,
        "languageCode": config.LANGUAGE_CODE,
        "pageSize": min(20, max_resultados),  # Places New: máx 20 por página
    }

    empresas: list[Empresa] = []
    page_token = None
    while len(empresas) < max_resultados:
        if page_token:
            body["pageToken"] = page_token
        resp = requests.post(_ENDPOINT, headers=headers, json=body, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        for place in data.get("places", []):
            if place.get("businessStatus") not in (None, "OPERATIONAL"):
                continue
            reseñas = int(place.get("userRatingCount") or 0)
            if reseñas < config.MIN_RESENAS:
                continue
            web = place.get("websiteUri", "")
            empresas.append(
                Empresa(
                    nombre=(place.get("displayName") or {}).get("text", ""),
                    rubro=rubro_nombre or rubro_query,
                    comuna=comuna,
                    direccion=place.get("formattedAddress", ""),
                    telefono=place.get("nationalPhoneNumber", ""),
                    sitio_web=web,
                    dominio=_dominio(web),
                    calificacion=str(place.get("rating", "")),
                    resenas=reseñas,
                    place_id=place.get("id", ""),
                )
            )
            if len(empresas) >= max_resultados:
                break

        page_token = data.get("nextPageToken")
        if not page_token:
            break

    return empresas


def resolver_dominio_de_nombre(nombre: str) -> Empresa | None:
    """Resuelve el nombre de una empresa a su ficha (para enriquecer clientes).

    Devuelve la primera coincidencia con sitio web, o None.
    """
    if not config.GOOGLE_PLACES_API_KEY:
        raise RuntimeError("Falta GOOGLE_PLACES_API_KEY en el entorno (.env).")

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": config.GOOGLE_PLACES_API_KEY,
        "X-Goog-FieldMask": _FIELD_MASK,
    }
    body = {
        "textQuery": nombre,
        "regionCode": config.REGION_CODE,
        "languageCode": config.LANGUAGE_CODE,
        "pageSize": 5,
    }
    resp = requests.post(_ENDPOINT, headers=headers, json=body, timeout=30)
    resp.raise_for_status()
    for place in resp.json().get("places", []):
        web = place.get("websiteUri", "")
        if not web:
            continue
        return Empresa(
            nombre=(place.get("displayName") or {}).get("text", nombre),
            direccion=place.get("formattedAddress", ""),
            telefono=place.get("nationalPhoneNumber", ""),
            sitio_web=web,
            dominio=_dominio(web),
            calificacion=str(place.get("rating", "")),
            resenas=int(place.get("userRatingCount") or 0),
            place_id=place.get("id", ""),
        )
    return None
