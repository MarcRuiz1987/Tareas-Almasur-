"""Capa aislada del modelo de lenguaje (Claude).

TODA la dependencia del proveedor de LLM vive aquí: el cliente, los IDs de modelo,
los prompts y los schemas de salida estructurada. Para portar el proyecto a otro
LLM, reescribe SÓLO este archivo manteniendo la firma de las tres funciones
públicas:

    describir_empresa(nombre, texto_web)          -> DescripcionEmpresa
    construir_perfil_icp(clientes)                -> PerfilICP
    calificar_empresa(empresa, perfil, ejemplos)  -> Calificacion

El resto del pipeline es agnóstico del proveedor.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from . import config


# ─── Schemas de salida estructurada ───────────────────────────────────────────


class DescripcionEmpresa(BaseModel):
    descripcion: str = Field(description="Qué hace la empresa, 1-3 frases.")
    sector: str = Field(description="Sector o industria principal.")
    tamano_estimado: str = Field(
        description="Tamaño estimado: micro, pequeña, mediana o grande."
    )
    senales: list[str] = Field(
        default_factory=list,
        description="Señales relevantes para calificar (ej: tiene bodega, exporta, e-commerce).",
    )


class PerfilICP(BaseModel):
    rubros: list[str] = Field(description="Rubros típicos de los clientes actuales.")
    tamano: str = Field(description="Rango de tamaño típico de los clientes.")
    senales_clave: list[str] = Field(
        description="Señales que distinguen a un buen cliente."
    )
    criterios_exclusion: list[str] = Field(
        default_factory=list,
        description="Características que descartan a una empresa como cliente.",
    )
    resumen: str = Field(description="Resumen en prosa del cliente ideal.")


class Calificacion(BaseModel):
    ajuste: str = Field(description='Veredicto de ajuste: "si", "quizas" o "no".')
    score_icp: int = Field(description="Qué tan bien encaja, de 0 a 100.")
    razon: str = Field(description="Justificación breve del veredicto.")


# ─── Cliente Claude (perezoso) ────────────────────────────────────────────────

_client = None


def _get_client():
    global _client
    if _client is None:
        import anthropic  # import perezoso para no exigir la dependencia si no se usa

        _client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY or None)
    return _client


def _parse(model: str, system: str, prompt: str, schema, **kwargs):
    """Llama a Claude con salida estructurada y devuelve la instancia Pydantic."""
    resp = _get_client().messages.parse(
        model=model,
        max_tokens=2048,
        system=system,
        messages=[{"role": "user", "content": prompt}],
        output_format=schema,
        **kwargs,
    )
    if resp.stop_reason == "refusal":
        raise RuntimeError("Claude rechazó la solicitud (stop_reason=refusal).")
    return resp.parsed_output


# ─── Funciones públicas (la superficie a reescribir para otro LLM) ─────────────


def describir_empresa(nombre: str, texto_web: str) -> DescripcionEmpresa:
    """Genera una descripción estructurada a partir del texto del sitio web."""
    system = (
        "Eres un analista B2B. A partir del texto del sitio web de una empresa, "
        "describes qué hace de forma objetiva y concisa, en español de Chile."
    )
    prompt = (
        f"Empresa: {nombre}\n\n"
        f"Texto del sitio web (puede estar incompleto):\n{texto_web[:8000]}\n\n"
        "Describe la empresa."
    )
    return _parse(config.MODELO_DESCRIPCION, system, prompt, DescripcionEmpresa)


def construir_perfil_icp(clientes: list[dict]) -> PerfilICP:
    """Resume la cartera de clientes actuales en un perfil de cliente ideal (ICP)."""
    system = (
        "Eres un estratega de ventas B2B. A partir de la lista de clientes actuales "
        "de una empresa, infieres su Perfil de Cliente Ideal (ICP): qué rubros, "
        "tamaños y señales comparten, y qué los descarta."
    )
    lineas = []
    for c in clientes:
        lineas.append(
            f"- {c.get('nombre', '')}: {c.get('descripcion', '')} "
            f"(sector: {c.get('sector', '?')}, tamaño: {c.get('tamano_estimado', '?')})"
        )
    prompt = "Clientes actuales:\n" + "\n".join(lineas) + "\n\nInfiere el ICP."
    return _parse(config.MODELO_CALIFICACION, system, prompt, PerfilICP)


def calificar_empresa(
    empresa: dict, perfil: PerfilICP, ejemplos: list[dict]
) -> Calificacion:
    """Clasifica si una empresa candidata encaja con el ICP, con few-shot de clientes."""
    system = (
        "Eres un calificador de leads B2B. Dado el Perfil de Cliente Ideal (ICP) y "
        "ejemplos de clientes reales, decides si una empresa candidata encaja. "
        'Responde "si" sólo si encaja claramente, "no" si la descartan los criterios '
        'de exclusión, y "quizas" si hay señales mixtas. Sé estricto.'
    )
    ejemplos_txt = "\n".join(
        f"- {e.get('nombre', '')}: {e.get('descripcion', '')}" for e in ejemplos[:10]
    )
    prompt = (
        f"PERFIL ICP:\n{perfil.model_dump_json(indent=2)}\n\n"
        f"EJEMPLOS DE CLIENTES REALES (todos encajan):\n{ejemplos_txt}\n\n"
        f"EMPRESA CANDIDATA:\n"
        f"Nombre: {empresa.get('nombre', '')}\n"
        f"Sector: {empresa.get('sector', '')}\n"
        f"Tamaño: {empresa.get('tamano_estimado', '')}\n"
        f"Descripción: {empresa.get('descripcion', '')}\n"
        f"Señales: {', '.join(empresa.get('senales', []))}\n\n"
        "¿Encaja con el ICP?"
    )
    return _parse(
        config.MODELO_CALIFICACION,
        system,
        prompt,
        Calificacion,
        thinking={"type": "adaptive"},
    )
