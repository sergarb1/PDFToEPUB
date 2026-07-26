# PDFToEPUB

Convierte PDF a **Markdown** y **EPUB** con 3 motores OCR.

Un solo script, tres motores:

```
PDFToEPUB/
├── PDFToEPUB.py            Entrada única con --engine
├── PDFToEPUB_common.py     Pipeline compartido
├── README.md
├── AGENTS.md
├── requirements.txt
└── LICENSE
```

---

## Índice

1. [Los tres motores](#los-tres-motores)
2. [¿Cuál uso? — Guía de decisión](#cul-uso--gua-de-decisin)
3. [Instalación rápida](#instalacin-rápida)
4. [Uso](#uso)
5. [Opciones](#opciones)
6. [Salida EPUB](#salida-epub)
7. [Cómo funciona](#cmo-funciona)
8. [Rendimiento](#rendimiento)
9. [Solución de problemas](#solucin-de-problemas)
10. [Licencias](#licencias)

---

## Los cuatro motores

### `--engine lighton` (por defecto) — LightOnOCR-2-1B

Modelo VLM end-to-end (1B, Pixtral + Mistral 3). **Punto óptimo** entre velocidad
y calidad. Produce Markdown estructurado con encabezados, párrafos y listas.
~8 s/página, ~2 GB VRAM. Apache 2.0.

### `--engine glm` — GLM-OCR (0.9B)

VLM de Z.ai (CogViT + GLM-0.5B). **Máxima precisión**: 94.62 OmniDocBench (#1).
Ideal para tablas, fórmulas, columnas, documentos densos.
~5-15 s/página, ~2.5 GB VRAM. Apache 2.0.

### `--engine ppocrv6` — PP-OCRv6

Pipeline clásico (detección + reconocimiento, 34.5M parámetros).
**El más rápido** (<1 s/página). Supera a VLMs de 235B en reconocimiento
de texto puro. **Sin estructura de layout** — todo sale como texto plano.
Requiere: `pip install paddleocr`. Apache 2.0.

### `--engine tesseract` — Tesseract OCR

OCR clásico de toda la vida (5.5, LSTM + legacy). **Siempre funciona**,
no necesita GPU. Detecta párrafos con segmentación de página (--psm).
~1-3 s/página en CPU. Requiere: `sudo apt install tesseract-ocr tesseract-ocr-spa`
y `pip install pytesseract`. Apache 2.0.

---

## ¿Cuál uso? — Guía de decisión

```
¿Qué documento tienes?
        │
    ┌───┴──────────┐
    │              │
  Texto          Tablas, figuras,
  plano          columnas, layouts
    │              │
    ▼              ▼
┌──────┐      ┌───┴──────────┐
│      │      │  ¿Tienes GPU?│
│¿GPU? │      └────┬────┬────┘
│      │          NO     SÍ
└──┬───┘           │     │
   │         ┌─────┴┐   ┌┴────────┐
   │         │      │   │         │
   ▼         ▼      ▼   ▼         ▼
ppocrv6  tesseract   │   ┌───────┴───┐
<1s/pág  1-3s/pág   Veloc.    Precisión
texto    texto con  │         │
plano    párrafos   ▼         ▼
                 lighton     glm
                 ~8s/pág   ~10s/pág
```

| Quieres… | Usa |
|---|---|
| Un buen resultado por defecto | `--engine lighton` (omitir) |
| Máxima calidad en tablas/layout | `--engine glm` |
| Velocidad máxima, texto plano | `--engine ppocrv6` |
| Sin GPU, ligero, siempre funciona | `--engine tesseract` |
| Sin GPU, rápido, texto plano | `--engine ppocrv6 --cpu` |

---

## Instalación rápida

```bash
# Dependencias base (todos los motores)
pip install torch transformers pdf2image pillow

# Solo para PP-OCRv6
pip install paddleocr

# Solo para Tesseract
sudo apt install tesseract-ocr tesseract-ocr-spa
pip install pytesseract

# Sistema (para EPUB y rasterizado)
sudo apt install poppler-utils pandoc
```

---

## Uso

```bash
# LightOnOCR (default) → .md + .epub
python PDFToEPUB.py documento.pdf

# Solo Markdown (sin EPUB)
python PDFToEPUB.py documento.pdf --no-epub

# GLM-OCR
python PDFToEPUB.py documento.pdf --engine glm

# PP-OCRv6 (más rápido)
python PDFToEPUB.py documento.pdf --engine ppocrv6

# Tesseract (CPU, siempre funciona)
python PDFToEPUB.py documento.pdf --engine tesseract

# Rango de páginas
python PDFToEPUB.py documento.pdf --first-page 5 --last-page 10

# Reanudar tras interrupción
python PDFToEPUB.py documento.pdf --resume

# CPU (solo útil para ppocrv6; VLMs serán muy lentos)
python PDFToEPUB.py documento.pdf --engine ppocrv6 --cpu

# Español
python PDFToEPUB.py documento.pdf --lang es

# Ayuda completa con guía de motores
python PDFToEPUB.py -h
```

---

## Opciones

| Argumento | Descripción |
|---|---|
| `pdf` | Archivo PDF de entrada |
| `--engine` | Motor: `lighton` (defecto), `glm`, `ppocrv6`, `tesseract` |
| `-o, --output` | Ruta de salida (.md o .epub) |
| `--dpi` | DPI de imagen (200) |
| `--max-h` | Altura máxima en píxeles (768). Solo VLMs. Bajar si OOM |
| `--first-page` | Primera página |
| `--last-page` | Última página |
| `--resume` | Reanudar desde salida existente |
| `--cpu` | Forzar CPU |
| `--no-epub` | Saltar conversión a EPUB (solo .md) |
| `--title` | Título para metadatos EPUB |
| `--author` | Autor (repetible) |
| `--lang` | `en` o `es` |
| `--context-window` | Páginas de contexto para VLM (5). 0 = sin contexto |
| `--reload-every` | Recargar modelo cada N páginas (0 = nunca) |

---

## Salida EPUB

Por defecto el script genera `.md` + `.epub`. Para solo Markdown:

```bash
python PDFToEPUB.py documento.pdf --no-epub
```

Para EPUB con metadatos:

```bash
python PDFToEPUB.py documento.pdf --title "Mi Libro" --author "Autor"
```

---

## Cómo funciona

### VLM (lighton, glm)

```
PDF → rasterizar → redimensionar → VLM (GPU) → Markdown → EPUB
```

1. Cada página se rasteriza a imagen (200 DPI).
2. Se redimensiona a `--max-h` px (768) para evitar OOM.
3. El VLM genera Markdown estructurado.
4. pandoc convierte a EPUB.

### Pipeline (ppocrv6)

```
PDF → rasterizar → detección (bboxes) → recorte → reconocimiento → texto plano
```

### Tesseract

```
PDF → rasterizar → segmentación de página → OCR LSTM+legacy → texto con párrafos
```

1. Detecta regiones de texto.
2. Reconoce caracteres en cada región.
3. Concatena líneas en orden de lectura.
4. **Sin estructura**: no distingue encabezados, tablas ni figuras.

---

## Rendimiento

| Motor | Dispersa | Texto denso | Muy denso | Media |
|---|---|---|---|---|
| LightOnOCR | 4-7 s | 20-65 s | 60-130 s | ~14 s |
| GLM-OCR | 3-6 s | 15-50 s | 40-100 s | ~10 s |
| PP-OCRv6 | <0.5 s | <1 s | 1-3 s | <1 s |
| Tesseract | 0.5-2 s | 1-3 s | 2-5 s | ~1.5 s |

| Motor | VRAM (cargando) | VRAM (pico OCR) |
|---|---|---|
| LightOnOCR | ~2.0 GB | ~2.5 GB |
| GLM-OCR | ~2.3 GB | ~3.0 GB |
| PP-OCRv6 | ~0.8 GB | ~1.2 GB |
| Tesseract | 0 GB (CPU) | 0 GB (CPU) |

---

## Solución de problemas

| Problema | Solución |
|---|---|
| OOM en páginas densas | `--max-h 512` o `--dpi 150` |
| PP-OCRv6: paddleocr no instalado | `pip install paddleocr` |
| PP-OCRv6: GPU no funciona | Usa `--cpu`, o fallback automático |
| GLM-OCR: transformers muy viejo | `pip install "transformers>=5.3.0"` |
| Tesseract: binario no encontrado | `sudo apt install tesseract-ocr tesseract-ocr-spa` |
| Tesseract: pytesseract no instalado | `pip install pytesseract` |
| Pandoc no instalado | `sudo apt install pandoc` |

---

## Licencias

| Componente | Licencia |
|---|---|
| Código del repositorio | **GPLv3** |
| LightOnOCR-2-1B | Apache 2.0 |
| GLM-OCR | Apache 2.0 |
| PP-OCRv6 (PaddleOCR) | Apache 2.0 |
| PyTorch | BSD |
| Transformers | Apache 2.0 |

---

---

# PDFToEPUB

Convert PDF to **Markdown** and **EPUB** with 4 local OCR engines.

Single script, four engines:

## The three engines

### `--engine lighton` (default) — LightOnOCR-2-1B

End-to-end VLM (1B, Pixtral + Mistral 3). **Best speed/quality balance**.
Structured Markdown output. ~8 s/page, ~2 GB VRAM. Apache 2.0.

### `--engine glm` — GLM-OCR (0.9B)

Z.ai VLM (CogViT + GLM-0.5B). **Highest accuracy**: 94.62 OmniDocBench (#1).
Best for tables, formulas, dense layouts. ~5-15 s/page, ~2.5 GB VRAM. Apache 2.0.

### `--engine ppocrv6` — PP-OCRv6

Classic pipeline (detection + recognition, 34.5M params). **Fastest** (<1 s/page).
Beats 235B VLMs on pure text. **No layout structure** — flat text output.
Requires: `pip install paddleocr`. Apache 2.0.

### `--engine tesseract` — Tesseract OCR

Classic LSTM+legacy OCR (5.5). **Always works**, no GPU needed.
Basic paragraph detection via page segmentation (--psm).
~1-3 s/page on CPU. Requires: `sudo apt install tesseract-ocr`
and `pip install pytesseract`. Apache 2.0.

## Quick install

```bash
pip install torch transformers pdf2image pillow   # all engines
pip install paddleocr                             # ppocrv6 only
pip install pytesseract                           # tesseract only
sudo apt install tesseract-ocr poppler-utils pandoc  # system
```

## Usage

```bash
# Default (lighton) → .md + .epub
python PDFToEPUB.py document.pdf

# Markdown only
python PDFToEPUB.py document.pdf --no-epub

# GLM-OCR
python PDFToEPUB.py document.pdf --engine glm

# PP-OCRv6 (fastest)
python PDFToEPUB.py document.pdf --engine ppocrv6

# Tesseract (CPU, always works)
python PDFToEPUB.py document.pdf --engine tesseract

# CPU mode (ppocrv6/tesseract only; VLMs will be very slow)
python PDFToEPUB.py document.pdf --engine ppocrv6 --cpu

# Page range
python PDFToEPUB.py document.pdf --first-page 5 --last-page 10

# Resume after interruption
python PDFToEPUB.py document.pdf --resume

# Spanish
python PDFToEPUB.py document.pdf --lang es
```

## Options

| Argument | Description |
|---|---|
| `pdf` | Input PDF file |
| `--engine` | Engine: `lighton` (default), `glm`, `ppocrv6`, `tesseract` |
| `-o, --output` | Output path (.md or .epub) |
| `--dpi` | Image DPI (200) |
| `--max-h` | Max height in pixels (768). VLM only. |
| `--first-page` | First page |
| `--last-page` | Last page |
| `--resume` | Resume from existing output |
| `--cpu` | Force CPU |
| `--no-epub` | Skip EPUB, Markdown only |
| `--title` | Book title for EPUB metadata |
| `--author` | Author (repeatable) |
| `--lang` | `en` or `es` |

## EPUB output

Markdown + EPUB by default. For Markdown only: `--no-epub`.
For metadata: `--title "Book" --author "Author"`.

## Performance

| Engine | Sparse | Dense text | Very dense | Average |
|---|---|---|---|---|
| LightOnOCR | 4-7 s | 20-65 s | 60-130 s | ~14 s |
| GLM-OCR | 3-6 s | 15-50 s | 40-100 s | ~10 s |
| PP-OCRv6 | <0.5 s | <1 s | 1-3 s | <1 s |

| Engine | VRAM (idle) | VRAM (peak OCR) |
|---|---|---|
| LightOnOCR | ~2.0 GB | ~2.5 GB |
| GLM-OCR | ~2.3 GB | ~3.0 GB |
| PP-OCRv6 | ~0.8 GB | ~1.2 GB |

## Troubleshooting

| Issue | Fix |
|---|---|
| OOM on dense pages | `--max-h 512` or `--dpi 150` |
| PP-OCRv6: paddleocr not found | `pip install paddleocr` |
| PP-OCRv6: GPU fails | Use `--cpu`, or auto fallback |
| GLM-OCR: old transformers | `pip install "transformers>=5.3.0"` |
| Pandoc not installed | `sudo apt install pandoc` |

## Licenses

| Component | License |
|---|---|
| Repository code | **GPLv3** |
| LightOnOCR-2-1B | Apache 2.0 |
| GLM-OCR | Apache 2.0 |
| PP-OCRv6 (PaddleOCR) | Apache 2.0 |
| PyTorch | BSD |
| Transformers | Apache 2.0 |
