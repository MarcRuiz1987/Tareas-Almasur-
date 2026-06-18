"""Capa de contactos: descubrir (Hunter) → enriquecer (FullEnrich) → fallback web.

Los proveedores implementan la interfaz ``ContactProvider`` para poder reordenarlos
o desactivar uno sin tocar el pipeline:

  1. Hunter Domain Search descubre personas a partir de SÓLO el dominio
     (nombre, apellido, cargo, email, confianza).
  2. FullEnrich recibe nombre+apellido+dominio de las personas priorizadas y, vía
     waterfall de 15+ proveedores, devuelve email verificado + teléfono móvil.
  3. Si Hunter no devuelve nada, se cae al scraping del sitio (regex) de la v1.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod

import requests

from . import config
from .models import Contacto, Empresa
from .website import CARGO_KEYWORDS, extraer_contacto_de_sitio


class ContactProvider(ABC):
    """Interfaz común para proveedores de contactos."""

    @abstractmethod
    def disponible(self) -> bool:
        """True si el proveedor tiene su clave configurada."""


# ─── Hunter.io — descubrimiento por dominio ───────────────────────────────────


class HunterProvider(ContactProvider):
    _ENDPOINT = "https://api.hunter.io/v2/domain-search"

    def disponible(self) -> bool:
        return bool(config.HUNTER_API_KEY)

    def descubrir(self, dominio: str, limit: int = 10) -> list[Contacto]:
        """Devuelve personas (con email/cargo) encontradas para el dominio."""
        if not self.disponible() or not dominio:
            return []
        params = {
            "domain": dominio,
            "api_key": config.HUNTER_API_KEY,
            "limit": limit,
        }
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
                    linkedin_url=e.get("linkedin") or "",
                    confianza=int(e.get("confidence") or 0),
                )
            )
        return contactos


# ─── FullEnrich — enriquecimiento waterfall (email verificado + teléfono) ──────


class FullEnrichProvider(ContactProvider):
    # Endpoint bulk asíncrono. La ruta /api/v1 sigue vigente y responde con el
    # contrato actual de FullEnrich; la /api/v2 existe pero cambia el envoltorio
    # de la petición (espera "data" en vez de "datas"), así que usamos la v1.
    # El contrato actual (verificado contra la API):
    #   - enrich_fields usa nombres "contact.*" (no "contact_email"/"contact_phone").
    #   - el POST devuelve {"enrichment_id": ...}.
    #   - el polling GET /bulk/{id} devuelve {"status": "FINISHED"|"IN_PROGRESS"|...,
    #     "datas": [{"contact": {...}}]} con los datos anidados bajo "contact".
    _BULK = "https://app.fullenrich.com/api/v1/contact/enrich/bulk"

    def disponible(self) -> bool:
        return bool(config.FULLENRICH_API_KEY)

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {config.FULLENRICH_API_KEY}",
            "Content-Type": "application/json",
        }

    def enriquecer(
        self, contactos: list[Contacto], dominio: str, empresa: str = ""
    ) -> list[Contacto]:
        """Enriquece email + teléfono de contactos que ya tienen nombre.

        FullEnrich es asíncrono: se encola un lote y se consulta el resultado.
        """
        if not self.disponible():
            return contactos
        datas = []
        indices = []
        for i, c in enumerate(contactos):
            partes = c.nombre.split(" ", 1)
            if len(partes) < 2:
                continue  # FullEnrich exige nombre + apellido
            datas.append(
                {
                    "firstname": partes[0],
                    "lastname": partes[1],
                    "domain": dominio,
                    "company_name": empresa,
                    "linkedin_url": c.linkedin_url or None,
                    # Nombres del contrato actual (la API rechaza "contact_email"/"contact_phone").
                    "enrich_fields": ["contact.emails", "contact.phones"],
                }
            )
            indices.append(i)
        if not datas:
            return contactos

        try:
            r = requests.post(
                self._BULK,
                headers=self._headers(),
                json={"name": f"leadgen {empresa}".strip(), "datas": datas},
                timeout=30,
            )
            r.raise_for_status()
            enrichment_id = r.json().get("enrichment_id")
        except requests.RequestException:
            return contactos
        if not enrichment_id:
            return contactos

        resultado = self._poll(enrichment_id)
        for pos, item in enumerate(resultado):
            if pos >= len(indices):
                break
            # Cada elemento de "datas" envuelve los datos bajo la clave "contact".
            contact = item.get("contact", item) if isinstance(item, dict) else {}
            c = contactos[indices[pos]]
            email = _email_de_contacto(contact)
            tel = _telefono_de_contacto(contact)
            if email:
                c.email = email
                c.confianza = max(c.confianza, 90)
            if tel:
                c.telefono = tel
        return contactos

    # Estados del job (la API responde en mayúsculas: FINISHED / IN_PROGRESS / ...).
    _TERMINAL_OK = {"FINISHED"}
    _TERMINAL_FALLO = {"CANCELED", "CANCELLED", "FAILED", "ERROR", "NO_CREDITS"}

    def _poll(self, enrichment_id: str, intentos: int = 20, espera: float = 6.0) -> list[dict]:
        url = f"{self._BULK}/{enrichment_id}"
        for _ in range(intentos):
            try:
                r = requests.get(url, headers=self._headers(), timeout=30)
                r.raise_for_status()
                data = r.json()
            except requests.RequestException:
                return []
            estado = str(data.get("status", "")).upper()
            if estado in self._TERMINAL_OK:
                return data.get("datas") or data.get("results") or []
            if estado in self._TERMINAL_FALLO:
                return []
            time.sleep(espera)
        return []


def _valor(item) -> str:
    """Normaliza a string un email/teléfono que puede venir como str o como dict."""
    if isinstance(item, dict):
        for k in ("email", "value", "address", "number", "phone", "e164"):
            if item.get(k):
                return str(item[k])
        return ""
    return str(item) if item else ""


def _email_de_contacto(contact: dict) -> str:
    """Mejor email del objeto ``contact`` de FullEnrich.

    Prioriza ``most_probable_email`` (laboral) y cae a las listas ``emails`` /
    ``personal_emails`` o al email personal más probable.
    """
    if contact.get("most_probable_email"):
        return str(contact["most_probable_email"])
    for lista in ("emails", "work_emails", "personal_emails"):
        for item in contact.get(lista) or []:
            email = _valor(item)
            if email:
                return email
    if contact.get("most_probable_personal_email"):
        return str(contact["most_probable_personal_email"])
    return ""


def _telefono_de_contacto(contact: dict) -> str:
    """Mejor teléfono del objeto ``contact`` de FullEnrich."""
    if contact.get("most_probable_phone"):
        return str(contact["most_probable_phone"])
    for item in contact.get("phones") or []:
        tel = _valor(item)
        if tel:
            return tel
    return ""


# ─── Orquestación ─────────────────────────────────────────────────────────────


def _prioridad_cargo(c: Contacto) -> int:
    cargo = (c.cargo or "").lower()
    tiene_cargo_relevante = any(k in cargo for k in CARGO_KEYWORDS)
    return (2 if tiene_cargo_relevante else 0) + (1 if c.email else 0)


def enriquecer_empresa(empresa: Empresa, top_contactos: int = 3) -> Empresa:
    """Descubre y enriquece contactos de una empresa, dejándolos en empresa.contactos."""
    hunter = HunterProvider()
    fullenrich = FullEnrichProvider()

    contactos: list[Contacto] = []
    if hunter.disponible() and empresa.dominio:
        contactos = hunter.descubrir(empresa.dominio)

    # Priorizar por cargo + presencia de email, y quedarnos con los mejores.
    contactos.sort(key=_prioridad_cargo, reverse=True)
    contactos = contactos[:top_contactos]

    if contactos and fullenrich.disponible():
        contactos = fullenrich.enriquecer(contactos, empresa.dominio, empresa.nombre)

    # Fallback: si no hubo descubrimiento, raspar el sitio (regex de la v1).
    if not contactos and empresa.sitio_web:
        email, nombre, cargo = extraer_contacto_de_sitio(empresa.sitio_web)
        if email or nombre:
            contactos = [Contacto(nombre=nombre, cargo=cargo, email=email, confianza=40)]

    empresa.contactos = contactos
    return empresa
