"""Scoring combinado: ajuste al ICP + completitud de contacto.

Extiende la lógica de `_score` de la v1 (contacto/email/teléfono/sitio/reseñas)
sumándole el peso del ajuste al ICP, que es la señal más importante.
"""

from __future__ import annotations

from .models import Empresa


def score(empresa: Empresa) -> int:
    s = 0

    # Ajuste al ICP (lo que más pesa).
    s += int(empresa.score_icp * 0.5)  # 0-50
    if empresa.ajuste_icp == "si":
        s += 20
    elif empresa.ajuste_icp == "quizas":
        s += 5

    # Completitud de contacto (portado/ajustado de la v1).
    contacto = empresa.contacto_principal
    if contacto:
        if contacto.nombre:
            s += 10
        if contacto.email:
            s += 8
        if contacto.telefono:
            s += 7
    if empresa.sitio_web:
        s += 2

    # Señal de tracción.
    if empresa.resenas >= 50:
        s += 3
    elif empresa.resenas >= 10:
        s += 1

    empresa.score = s
    return s
