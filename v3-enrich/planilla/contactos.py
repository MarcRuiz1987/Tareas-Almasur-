"""Contactos por dominio: Hunter (descubrir) → FullEnrich (verificar email + tel).

Portado de ``v2-leadgen/leadgen/enrich.py`` y reducido a lo que la v3 necesita:
a partir del dominio de la empresa, devolver **el mejor contacto** (la persona con
cargo más relevante y email/teléfono verificados) para volcarlo en la planilla.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass

import requests

from . import config

CARGO_KEYWORDS = [
    "gerente", "jefe", "director", "encargado", "manager",
    "ceo", "owner", "founder", "socio", "dueño", "propietario",
]


@dataclass
class Contacto:
    nombre: str = ""
    cargo: str = ""
    email: str = ""
    telefono: str = ""
    linkedin: str = ""
    confianza: int = 0


class ContactProvider(ABC):
    @abstractmethod
    def disponible(self) -> bool: ...


# ─── Hunter.io — descubrimiento por dominio ───────────────────────────────────


class HunterProvider(ContactProvider):
    _ENDPOINT = "https://api.hunter.io/v2/domain-search"

    def disponible(self) -> bool:
        return bool(config.HUNTER_API_KEY)

    def descubrir(self, dominio: str, limit: int = 10) -> list[Contacto]:
        if not self.disponible() or not dominio:
            return []
        params = {"domain": dominio, "api_key": config.HUNTER_API_KEY, "limit": limit}
        try:
            resp = requests.get(self._ENDPOINT, params=params, timeout=30)
            resp.raise_for_status()
            emails = resp.json().get("data", {}).get("emails", [])
        except requests.RequestException:
            return []
        contactos = []
        for e in emails:
            nombre = " ".join(filter(None, [e.get("first_name"), e.get("last_name")])).strip()
            contactos.append(
                Contacto(
                    nombre=nombre,
                    cargo=e.get("position") or "",
                    email=e.get("value") or "",
                    linkedin=e.get("linkedin") or "",
                    confianza=int(e.get("confidence") or 0),
                )
            )
        return contactos


# ─── FullEnrich — verificación waterfall (email verificado + teléfono) ─────────


class FullEnrichProvider(ContactProvider):
    _BULK = "https://app.fullenrich.com/api/v1/contact/enrich/bulk"

    def disponible(self) -> bool:
        return bool(config.FULLENRICH_API_KEY)

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {config.FULLENRICH_API_KEY}",
            "Content-Type": "application/json",
        }

    def enriquecer(self, contactos: list[Contacto], dominio: str, empresa: str = "") -> list[Contacto]:
        if not self.disponible():
            return contactos
        datas, indices = [], []
        for i, c in enumerate(contactos):
            partes = c.nombre.split(" ", 1)
            if len(partes) < 2:
                continue
            datas.append(
                {
                    "firstname": partes[0],
                    "lastname": partes[1],
                    "domain": dominio,
                    "company_name": empresa,
                    "linkedin_url": c.linkedin or None,
                    "enrich_fields": ["contact_email", "contact_phone"],
                }
            )
            indices.append(i)
        if not datas:
            return contactos
        try:
            r = requests.post(
                self._BULK,
                headers=self._headers(),
                json={"name": f"planilla {empresa}".strip(), "datas": datas},
                timeout=30,
            )
            r.raise_for_status()
            enrichment_id = r.json().get("enrichment_id")
        except requests.RequestException:
            return contactos
        if not enrichment_id:
            return contactos
        for pos, item in enumerate(self._poll(enrichment_id)):
            if pos >= len(indices):
                break
            c = contactos[indices[pos]]
            email = _primero(item, "contact_email", "email")
            tel = _primero(item, "contact_phone", "phone", "mobile_phone")
            if email:
                c.email = email
                c.confianza = max(c.confianza, 90)
            if tel:
                c.telefono = tel
        return contactos

    def _poll(self, enrichment_id: str, intentos: int = 20, espera: float = 6.0) -> list[dict]:
        url = f"{self._BULK}/{enrichment_id}"
        for _ in range(intentos):
            try:
                r = requests.get(url, headers=self._headers(), timeout=30)
                r.raise_for_status()
                data = r.json()
            except requests.RequestException:
                return []
            if data.get("status") in ("FINISHED", "finished", "done"):
                return data.get("datas") or data.get("results") or []
            time.sleep(espera)
        return []


def _primero(d: dict, *claves: str) -> str:
    for k in claves:
        v = d.get(k)
        if isinstance(v, dict):
            v = v.get("value") or v.get("email") or v.get("number")
        if v:
            return str(v)
    return ""


def _prioridad(c: Contacto) -> int:
    cargo = (c.cargo or "").lower()
    relevante = any(k in cargo for k in CARGO_KEYWORDS)
    return (2 if relevante else 0) + (1 if c.email else 0)


def mejor_contacto(dominio: str, empresa: str = "", top: int = 3) -> Contacto | None:
    """Descubre y verifica contactos del dominio; devuelve el mejor (o None)."""
    hunter, fullenrich = HunterProvider(), FullEnrichProvider()
    if not hunter.disponible() or not dominio:
        return None
    contactos = hunter.descubrir(dominio)
    if not contactos:
        return None
    contactos.sort(key=_prioridad, reverse=True)
    contactos = contactos[:top]
    if fullenrich.disponible():
        contactos = fullenrich.enriquecer(contactos, dominio, empresa)
    return max(contactos, key=lambda c: (_prioridad(c), c.confianza, bool(c.email)))
