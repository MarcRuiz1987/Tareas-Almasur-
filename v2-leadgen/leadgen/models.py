"""Estructuras de datos compartidas por el pipeline.

Son dataclasses neutrales (sin dependencia del LLM ni de ningún proveedor),
para que cualquier módulo pueda producirlas o consumirlas. Los schemas de salida
estructurada del LLM viven aparte, en ``llm.py``.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict


@dataclass
class Contacto:
    """Una persona de contacto en la empresa."""

    nombre: str = ""
    cargo: str = ""
    email: str = ""
    telefono: str = ""
    linkedin_url: str = ""
    confianza: int = 0  # 0-100; confianza de la fuente en el email

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Empresa:
    """Un lead: empresa descubierta + datos enriquecidos a lo largo del pipeline."""

    nombre: str
    rubro: str = ""
    comuna: str = ""
    direccion: str = ""
    telefono: str = ""
    sitio_web: str = ""
    dominio: str = ""
    calificacion: str = ""  # rating de Google (texto, p. ej. "4.3")
    resenas: int = 0
    place_id: str = ""

    # Enriquecido por describe.py
    descripcion: str = ""
    sector: str = ""
    tamano_estimado: str = ""
    senales: list[str] = field(default_factory=list)

    # Enriquecido por enrich.py
    contactos: list[Contacto] = field(default_factory=list)

    # Enriquecido por icp.py
    ajuste_icp: str = ""  # "si" | "quizas" | "no"
    score_icp: int = 0  # 0-100
    razon_icp: str = ""

    # Calculado por score.py
    score: int = 0

    @property
    def contacto_principal(self) -> Contacto | None:
        """El contacto con mayor confianza (o el primero disponible)."""
        if not self.contactos:
            return None
        return max(self.contactos, key=lambda c: (c.confianza, bool(c.email)))

    def to_dict(self) -> dict:
        d = asdict(self)
        d["senales"] = "; ".join(self.senales)
        d["contactos"] = [c.to_dict() for c in self.contactos]
        return d
