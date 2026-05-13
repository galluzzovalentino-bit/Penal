# Sistema de Apuntes Automáticos + Herramientas PDF

## Instalación

```bash
pip install -r requirements.txt
```

---

## 1. Generador de Apuntes (`notes.py`)

Adjuntá uno o varios documentos y el sistema genera apuntes detallados usando IA.

### Uso básico

```bash
python notes.py -f libro.pdf
```

### Con instrucciones personalizadas

```bash
python notes.py -f libro.pdf -i "Armá apuntes para rendir el examen de Derecho Penal. Enfocate en los elementos del delito."
```

### Varios documentos a la vez

```bash
python notes.py -f capitulo1.pdf capitulo2.docx clase.pptx -i "Integrá todo el material en apuntes unificados"
```

### Guardar el resultado en un archivo

```bash
python notes.py -f biblio.pdf -i "Resumen ejecutivo" -o mis_apuntes.md
```

### Estilos disponibles (`--style`)

| Estilo       | Descripción                                         |
|-------------|------------------------------------------------------|
| `detallado`  | Apuntes completos con títulos, subtítulos, ejemplos (default) |
| `esquema`    | Esquema jerárquico numerado (1., 1.1., 1.1.1.)      |
| `resumen`    | Síntesis concisa (~30% del original)                |
| `flashcards` | Tarjetas Pregunta/Respuesta para estudiar           |
| `mapa`       | Mapa conceptual con relaciones entre temas          |

```bash
python notes.py -f libro.pdf --style flashcards -i "Conceptos de Parte General"
python notes.py -f libro.pdf --style esquema -o esquema_penal.md
```

### Formatos de documento soportados

- **PDF** — `.pdf`
- **Word** — `.docx`, `.doc`
- **PowerPoint** — `.pptx`, `.ppt`
- **Texto plano** — `.txt`, `.md`, `.csv`

---

## 2. Herramientas PDF (`pdf_tools.py`)

### Ver información del PDF

```bash
python pdf_tools.py info documento.pdf
```

### Dividir un PDF en partes

```bash
# Divide en 3 partes: páginas 1-10, 11-20 y 21-30
python pdf_tools.py split documento.pdf --ranges "1-10" "11-20" "21-30"

# Guardar en una carpeta específica
python pdf_tools.py split documento.pdf --ranges "1-5" "6-10" -o partes/
```

### Extraer páginas específicas

```bash
# Extraer páginas 1, 3, 5 y del 10 al 15
python pdf_tools.py extract documento.pdf --pages "1,3,5,10-15" -o extraido.pdf
```

### Fusionar varios PDFs

```bash
python pdf_tools.py merge parte1.pdf parte2.pdf parte3.pdf -o completo.pdf
```

### Rotar páginas

```bash
# Rotar todo el documento 90°
python pdf_tools.py rotate documento.pdf --angle 90 -o rotado.pdf

# Rotar solo páginas específicas
python pdf_tools.py rotate documento.pdf --angle 180 --pages "1,3,5" -o rotado.pdf
```

---

## 3. Resumidor simple (`summarizer.py`)

```bash
python summarizer.py -f texto.txt -l long
python summarizer.py -t "Tu texto aquí"
```

---

## Variables de entorno

```bash
export ANTHROPIC_API_KEY="tu-api-key"
```
