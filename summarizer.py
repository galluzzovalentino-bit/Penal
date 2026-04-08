#!/usr/bin/env python3
"""
Resumidor de textos usando Claude API.
Uso:
  python summarizer.py                  # modo interactivo
  python summarizer.py -f archivo.txt   # resumir desde archivo
  python summarizer.py -t "tu texto"    # resumir texto directo
"""

import argparse
import sys
import anthropic


def summarize(text: str, level: str = "medium") -> str:
    """Envía el texto a Claude y devuelve el resumen."""
    instructions = {
        "short":  "Resume el siguiente texto en 2-3 oraciones breves.",
        "medium": "Resume el siguiente texto en un párrafo claro y conciso.",
        "long":   "Haz un resumen detallado del siguiente texto, conservando los puntos principales.",
    }
    prompt = instructions.get(level, instructions["medium"])

    client = anthropic.Anthropic()

    with client.messages.stream(
        model="claude-opus-4-6",
        max_tokens=1024,
        messages=[
            {
                "role": "user",
                "content": f"{prompt}\n\n---\n\n{text}",
            }
        ],
    ) as stream:
        result = stream.get_final_message()

    for block in result.content:
        if block.type == "text":
            return block.text
    return ""


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Resumidor de textos con Claude AI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("-f", "--file", help="Archivo de texto a resumir")
    parser.add_argument("-t", "--text", help="Texto a resumir (entre comillas)")
    parser.add_argument(
        "-l",
        "--level",
        choices=["short", "medium", "long"],
        default="medium",
        help="Nivel de detalle del resumen (default: medium)",
    )
    args = parser.parse_args()

    # Determinar la fuente del texto
    if args.file:
        try:
            with open(args.file, encoding="utf-8") as f:
                text = f.read()
        except FileNotFoundError:
            print(f"Error: No se encontró el archivo '{args.file}'", file=sys.stderr)
            sys.exit(1)
        except OSError as e:
            print(f"Error al leer el archivo: {e}", file=sys.stderr)
            sys.exit(1)
    elif args.text:
        text = args.text
    elif not sys.stdin.isatty():
        # Acepta texto por stdin (piped)
        text = sys.stdin.read()
    else:
        # Modo interactivo
        print("Pega tu texto a continuación y presiona Enter dos veces cuando termines:")
        print("(o escribe 'salir' para terminar)\n")
        lines = []
        try:
            while True:
                line = input()
                if line.lower() == "salir":
                    sys.exit(0)
                lines.append(line)
                if len(lines) >= 2 and lines[-1] == "" and lines[-2] == "":
                    break
        except EOFError:
            pass
        text = "\n".join(lines).strip()

    if not text.strip():
        print("Error: El texto está vacío.", file=sys.stderr)
        sys.exit(1)

    print("\nResumiendo...\n")
    summary = summarize(text, level=args.level)
    print("=" * 60)
    print("RESUMEN")
    print("=" * 60)
    print(summary)
    print("=" * 60)


if __name__ == "__main__":
    main()
