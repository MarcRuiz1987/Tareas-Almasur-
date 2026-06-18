"""Resolver una empresa (por nombre) a su ficha vía Google Places API.

Dado el nombre de la empresa (y opcionalmente su comuna), devuelve sitio web,
dominio, teléfono y dirección. Misma API y *field masking* que la v2, pero
orientado a **una empresa que ya conocemos** en lugar de a una búsqueda por rubro.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

import requests

from . import config

_ENDPOINT = "https://places.googleapis.com/v1/places:searchText"
_FIELD_MASK = ",".join(
    [
        "places.id",
        "places.displayName",
        "places.formattedAddress",
        "places.nationalPhoneNumber",
        "places.websiteUri",
    ]
)


def dominio_de_url(url: str) -> str:
    if not url:
        return ""
    try:
        host = urlparse(url).netloc.lower()
        return host[4:] if host.startswith("www.") else host
    except ValueError:
        return ""


# Proveedores de correo personales: su dominio no sirve para buscar contactos
# corporativos por dominio (Hunter), así que se descartan.
_DOMINIOS_PERSONALES = {
    "gmail.com", "googlemail.com", "hotmail.com", "hotmail.es", "outlook.com",
    "outlook.es", "live.com", "yahoo.com", "yahoo.es", "icloud.com", "me.com",
    "aol.com", "protonmail.com", "proton.me", "gmx.com",
}


def dominio_de_email(emails: str) -> str:
    """Dominio corporativo del primer e-mail aprovechable de una cadena.

    El SEIA suele traer varios correos separados por ';' o ','. Devuelve el
    dominio del primero que no sea de un proveedor personal (gmail, hotmail…),
    útil para enganchar al desarrollador madre de una SPV sin web propia
    ("imena@orion-power.com" → "orion-power.com"). "" si no hay uno aprovechable.
    """
    for trozo in re.split(r"[;,\s]+", str(emails or "")):
        if "@" in trozo:
            dom = trozo.split("@", 1)[1].strip().lower().strip(".")
            if dom and "." in dom and dom not in _DOMINIOS_PERSONALES:
                return dom
    return ""


def resolver(nombre: str, comuna: str = "") -> dict:
    """Devuelve {sitio_web, dominio, telefono, direccion} para una empresa.

    Si no hay clave o no hay coincidencia, devuelve un dict con valores vacíos.
    """
    vacio = {"sitio_web": "", "dominio": "", "telefono": "", "direccion": ""}
    if not config.GOOGLE_PLACES_API_KEY or not nombre:
        return vacio

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": config.GOOGLE_PLACES_API_KEY,
        "X-Goog-FieldMask": _FIELD_MASK,
    }
    consulta = f"{nombre} {comuna}".strip()
    body = {
        "textQuery": consulta,
        "regionCode": config.REGION_CODE,
        "languageCode": config.LANGUAGE_CODE,
        "pageSize": 5,
    }
    try:
        resp = requests.post(_ENDPOINT, headers=headers, json=body, timeout=30)
        resp.raise_for_status()
        lugares = resp.json().get("places", [])
    except requests.RequestException:
        return vacio

    # Preferir la primera coincidencia con sitio web; si ninguna lo tiene, la primera.
    elegido = next((p for p in lugares if p.get("websiteUri")), lugares[0] if lugares else None)
    if not elegido:
        return vacio

    web = elegido.get("websiteUri", "") or ""
    return {
        "sitio_web": web,
        "dominio": dominio_de_url(web),
        "telefono": elegido.get("nationalPhoneNumber", "") or "",
        "direccion": elegido.get("formattedAddress", "") or "",
    }
