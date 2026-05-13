#!/usr/bin/env python3
"""
Generador de apuntes detallados a partir de bibliografía (PDF, Word, PPT, TXT).

Uso:
  python notes.py -f libro.pdf apuntes.docx                         # instrucciones por defecto
  python notes.py -f libro.pdf -i "Arma un esquema con definiciones y ejemplos"
  python notes.py -f cap1.pdf cap2.pdf -i "Resumen integrado para rendir examen"
  python notes.py -f clase.pptx -i "Desarrolla cada tema con subtítulos" -o mis_apuntes.md
  python notes.py -f libro.pdf -i "..." --style esquema             # esquema, resumen, flashcards, mapa
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import anthropic

from document_reader import read_multiple


STYLE_PROMPTS = {
    "detallado": (
        "Generá apuntes académicos extremadamente detallados y completos. "
        "Usá títulos (##), subtítulos (###), listas con viñetas, definiciones en negrita, "
        "ejemplos concretos y resaltá los conceptos clave. "
        "El objetivo es que alguien pueda estudiar únicamente con estos apuntes."
    ),
    "esquema": (
        "Armá un esquema jerárquico con todos los temas, subtemas, definiciones y puntos clave. "
        "Usá numeración (1., 1.1., 1.1.1.) para mostrar la jerarquía claramente."
    ),
    "resumen": (
        "Hacé un resumen ejecutivo claro y conciso de los puntos más importantes, "
        "sin perder conceptos clave. Máximo 30% de la extensión original."
    ),
    "flashcards": (
        "Generá tarjetas de estudio en formato: **Pregunta:** ... / **Respuesta:** ... "
        "Cubrí todos los conceptos importantes del material."
    ),
    "mapa": (
        "Creá un mapa conceptual en texto usando indentación y flechas (→) para mostrar "
        "relaciones entre conceptos. Incluí todos los temas principales y sus conexiones."
    ),
}


def build_prompt(docs: dict[str, str], user_instruction: str, style: str) -> str:
    style_guide = STYLE_PROMPTS.get(style, STYLE_PROMPTS["detallado"])

    parts = [
        f"Sos un experto en didáctica y síntesis académica. Tu tarea es generar apuntes de estudio.",
        f"\n## Instrucción del usuario\n{user_instruction}" if user_instruction else "",
        f"\n## Estilo de apuntes\n{style_guide}",
        "\n## Material bibliográfico proporcionado\n",
    ]

    for filename, text in docs.items():
        # Límite de tokens por documento para no exceder el contexto
        truncated = text[:80_000] if len(text) > 80_000 else text
        was_truncated = len(text) > 80_000
        parts.append(f"### Documento: {filename}")
        parts.append(truncated)
        if was_truncated:
            parts.append(f"[...documento truncado a 80.000 caracteres de {len(text):,}...]")
        parts.append("")

    parts.append(
        "\n---\nAhora generá los apuntes completos según la instrucción y el estilo indicados. "
        "Sé exhaustivo, preciso y académicamente riguroso."
    )

    return "\n".join(p for p in parts if p is not None)


def generate_notes(
    files: list[str],
    instruction: str,
    style: str,
    model: str,
    output: str | None,
) -> None:
    print("\nLeyendo documentos...", file=sys.stderr)
    docs = read_multiple(files)

    total_chars = sum(len(t) for t in docs.values())
    print(f"  Total extraído: {total_chars:,} caracteres de {len(docs)} documento(s)", file=sys.stderr)

    prompt = build_prompt(docs, instruction, style)

    print("\nGenerando apuntes con Claude...\n", file=sys.stderr)

    client = anthropic.Anthropic()

    collected = []
    with client.messages.stream(
        model=model,
        max_tokens=8192,
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        for text in stream.text_stream:
            print(text, end="", flush=True)
            collected.append(text)

    notes = "".join(collected)
    print()  # newline after streaming

    if output:
        out_path = Path(output)
        out_path.write_text(notes, encoding="utf-8")
        print(f"\nApuntes guardados en: {out_path.resolve()}", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generador de apuntes con IA a partir de bibliografía",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "-f", "--files",
        nargs="+",
        required=True,
        metavar="ARCHIVO",
        help="Uno o más archivos (PDF, DOCX, PPTX, TXT, etc.)",
    )
    parser.add_argument(
        "-i", "--instruction",
        default="",
        metavar="INSTRUCCIÓN",
        help='Instrucción sobre qué tipo de apuntes generar. Ej: "Apuntes para examen de derecho penal"',
    )
    parser.add_argument(
        "-s", "--style",
        choices=list(STYLE_PROMPTS),
        default="detallado",
        help=f"Estilo de apuntes (default: detallado). Opciones: {', '.join(STYLE_PROMPTS)}",
    )
    parser.add_argument(
        "-o", "--output",
        metavar="ARCHIVO_SALIDA",
        help="Guardar apuntes en este archivo (además de mostrarlos en pantalla)",
    )
    parser.add_argument(
        "--model",
        default="claude-opus-4-7",
        help="Modelo Claude a usar (default: claude-opus-4-7)",
    )

    args = parser.parse_args()

    generate_notes(
        files=args.files,
        instruction=args.instruction,
        style=args.style,
        model=args.model,
        output=args.output,
    )


if __name__ == "__main__":
    main()
