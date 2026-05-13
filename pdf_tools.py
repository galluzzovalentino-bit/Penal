#!/usr/bin/env python3
"""
Herramienta de manipulación de PDFs (estilo ilovepdf).

Comandos disponibles:
  split    — Dividir un PDF en rangos de páginas
  extract  — Extraer páginas específicas
  merge    — Fusionar varios PDFs en uno
  info     — Mostrar información del PDF (páginas, metadatos)
  rotate   — Rotar páginas

Ejemplos:
  python pdf_tools.py info documento.pdf
  python pdf_tools.py split documento.pdf --ranges "1-5" "10-15" "20"
  python pdf_tools.py extract documento.pdf --pages 3,7,12-15 -o extraido.pdf
  python pdf_tools.py merge parte1.pdf parte2.pdf parte3.pdf -o completo.pdf
  python pdf_tools.py rotate documento.pdf --angle 90 --pages 1,3 -o rotado.pdf
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


def _require_pypdf() -> None:
    try:
        import pypdf  # noqa: F401
    except ImportError:
        sys.exit("Falta pypdf. Ejecutá: pip install pypdf")


def _parse_page_spec(spec: str, total_pages: int) -> list[int]:
    """
    Convierte una especificación de páginas a lista de índices 0-based.
    Acepta: "1,3,5-10,15" o "1-5" etc. (numeración desde 1).
    """
    pages = []
    for part in re.split(r"[,\s]+", spec.strip()):
        if not part:
            continue
        if "-" in part:
            start_s, end_s = part.split("-", 1)
            start, end = int(start_s), int(end_s)
            if start < 1 or end > total_pages:
                sys.exit(f"Rango {part} fuera de límites (el PDF tiene {total_pages} páginas).")
            pages.extend(range(start - 1, end))
        else:
            n = int(part)
            if n < 1 or n > total_pages:
                sys.exit(f"Página {n} fuera de límites (el PDF tiene {total_pages} páginas).")
            pages.append(n - 1)
    return pages


def _ensure_output_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


# ─── Comandos ────────────────────────────────────────────────────────────────

def cmd_info(args: argparse.Namespace) -> None:
    _require_pypdf()
    from pypdf import PdfReader

    reader = PdfReader(args.file)
    n = len(reader.pages)
    meta = reader.metadata or {}

    print(f"\nArchivo : {args.file}")
    print(f"Páginas : {n}")
    for key in ("Title", "Author", "Subject", "Creator", "Producer"):
        val = meta.get(f"/{key}", "")
        if val:
            print(f"{key:8}: {val}")


def cmd_split(args: argparse.Namespace) -> None:
    _require_pypdf()
    from pypdf import PdfReader, PdfWriter

    reader = PdfReader(args.file)
    total = len(reader.pages)
    stem = Path(args.file).stem
    out_dir = Path(args.output) if args.output else Path(".")
    out_dir.mkdir(parents=True, exist_ok=True)

    for i, rng in enumerate(args.ranges, 1):
        indices = _parse_page_spec(rng, total)
        writer = PdfWriter()
        for idx in indices:
            writer.add_page(reader.pages[idx])
        out_file = out_dir / f"{stem}_parte{i}.pdf"
        with open(out_file, "wb") as f:
            writer.write(f)
        label = rng.replace(",", "_")
        print(f"  Creado: {out_file}  (páginas {label})")

    print(f"\n{len(args.ranges)} archivo(s) generado(s) en '{out_dir}'.")


def cmd_extract(args: argparse.Namespace) -> None:
    _require_pypdf()
    from pypdf import PdfReader, PdfWriter

    reader = PdfReader(args.file)
    total = len(reader.pages)
    indices = _parse_page_spec(args.pages, total)

    out_path = Path(args.output) if args.output else Path(Path(args.file).stem + "_extraido.pdf")
    _ensure_output_dir(out_path)

    writer = PdfWriter()
    for idx in indices:
        writer.add_page(reader.pages[idx])

    with open(out_path, "wb") as f:
        writer.write(f)

    print(f"Extraídas {len(indices)} página(s) → {out_path}")


def cmd_merge(args: argparse.Namespace) -> None:
    _require_pypdf()
    from pypdf import PdfReader, PdfWriter

    writer = PdfWriter()
    total = 0
    for src in args.files:
        reader = PdfReader(src)
        n = len(reader.pages)
        for page in reader.pages:
            writer.add_page(page)
        total += n
        print(f"  Agregado: {src}  ({n} páginas)")

    out_path = Path(args.output) if args.output else Path("fusionado.pdf")
    _ensure_output_dir(out_path)

    with open(out_path, "wb") as f:
        writer.write(f)

    print(f"\nFusionados {len(args.files)} archivos ({total} páginas) → {out_path}")


def cmd_rotate(args: argparse.Namespace) -> None:
    _require_pypdf()
    from pypdf import PdfReader, PdfWriter

    if args.angle not in (90, 180, 270):
        sys.exit("El ángulo debe ser 90, 180 o 270.")

    reader = PdfReader(args.file)
    total = len(reader.pages)
    target = set(_parse_page_spec(args.pages, total)) if args.pages else set(range(total))

    writer = PdfWriter()
    for i, page in enumerate(reader.pages):
        if i in target:
            page.rotate(args.angle)
        writer.add_page(page)

    out_path = Path(args.output) if args.output else Path(Path(args.file).stem + "_rotado.pdf")
    _ensure_output_dir(out_path)

    with open(out_path, "wb") as f:
        writer.write(f)

    print(f"Rotadas {len(target)} página(s) {args.angle}° → {out_path}")


# ─── CLI ─────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Herramienta de manipulación de PDFs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # info
    p_info = sub.add_parser("info", help="Mostrar información del PDF")
    p_info.add_argument("file", help="Archivo PDF")

    # split
    p_split = sub.add_parser("split", help="Dividir PDF en partes")
    p_split.add_argument("file", help="Archivo PDF de entrada")
    p_split.add_argument(
        "--ranges", nargs="+", required=True, metavar="RANGO",
        help='Rangos de páginas a extraer. Ej: "1-5" "6-10" "11"',
    )
    p_split.add_argument("-o", "--output", metavar="CARPETA", help="Carpeta de salida (default: .)")

    # extract
    p_extract = sub.add_parser("extract", help="Extraer páginas específicas")
    p_extract.add_argument("file", help="Archivo PDF de entrada")
    p_extract.add_argument(
        "--pages", required=True, metavar="PÁGINAS",
        help='Páginas a extraer. Ej: "1,3,5-10"',
    )
    p_extract.add_argument("-o", "--output", metavar="ARCHIVO", help="Archivo PDF de salida")

    # merge
    p_merge = sub.add_parser("merge", help="Fusionar varios PDFs")
    p_merge.add_argument("files", nargs="+", metavar="ARCHIVO", help="Archivos PDF a fusionar (en orden)")
    p_merge.add_argument("-o", "--output", metavar="ARCHIVO", help="Archivo PDF de salida (default: fusionado.pdf)")

    # rotate
    p_rotate = sub.add_parser("rotate", help="Rotar páginas de un PDF")
    p_rotate.add_argument("file", help="Archivo PDF de entrada")
    p_rotate.add_argument(
        "--angle", type=int, choices=[90, 180, 270], required=True,
        help="Ángulo de rotación: 90, 180 o 270",
    )
    p_rotate.add_argument(
        "--pages", metavar="PÁGINAS",
        help='Páginas a rotar. Ej: "1,3,5-10". Si se omite, rota todas.',
    )
    p_rotate.add_argument("-o", "--output", metavar="ARCHIVO", help="Archivo PDF de salida")

    args = parser.parse_args()

    commands = {
        "info":    cmd_info,
        "split":   cmd_split,
        "extract": cmd_extract,
        "merge":   cmd_merge,
        "rotate":  cmd_rotate,
    }
    commands[args.command](args)


if __name__ == "__main__":
    main()
