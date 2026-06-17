"""leadgen — generación de leads B2B con herramientas de pago (v2).

Pipeline de 5 fases:
  1. discovery  — Google Places API: empresas por rubro + comuna
  2. describe   — Claude (Haiku): descripción estructurada desde el sitio web
  3. enrich     — Hunter (descubrir) → FullEnrich (email + teléfono)
  4. icp        — perfil de cliente ideal desde la cartera + calificación
  5. score      — scoring combinado y exportación

Ver docs/MODELOS.md para la descripción completa de cada modelo y módulo.
"""

from . import config  # noqa: F401

__all__ = ["config"]
__version__ = "2.0.0"
