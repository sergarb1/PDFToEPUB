<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://img.shields.io/badge/PDF→EPUB-8A2BE2?style=for-the-badge&logo=readthedocs&logoColor=white">
    <img alt="PDFToEPUB" src="https://img.shields.io/badge/PDF→EPUB-8A2BE2?style=for-the-badge&logo=readthedocs&logoColor=white">
  </picture>
</p>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/python-3.10+-blue?style=flat-square&logo=python&logoColor=white">
  <img alt="License" src="https://img.shields.io/badge/license-GPLv3-blue?style=flat-square">
  <img alt="GPU" src="https://img.shields.io/badge/GPU-NVIDIA-green?style=flat-square&logo=nvidia&logoColor=white">
  <img alt="CPU" src="https://img.shields.io/badge/CPU-Tesseract-success?style=flat-square">
  <img alt="LightOnOCR" src="https://img.shields.io/badge/LightOnOCR-2--1B-FF6F00?style=flat-square">
  <img alt="GLM-OCR" src="https://img.shields.io/badge/GLM--OCR-0.9B-1E88E5?style=flat-square">
  <img alt="PRs" src="https://img.shields.io/badge/PRs-welcome-brightgreen?style=flat-square">
</p>

<p align="center">
  <b>PDF → Markdown + EPUB</b> — 3 motores OCR locales, un solo script.
</p>

<p align="center">
  <a href="#instalación">Instalación</a> •
  <a href="#uso">Uso</a> •
  <a href="#motores">Motores</a> •
  <a href="#rendimiento">Rendimiento</a> •
  <a href="#español">Español</a>
</p>

---

## ✨ Features

- **3 motores OCR** intercambiables con un flag `--engine`
- **Salida dual**: Markdown + EPUB en un solo comando
- **Contexto entre páginas**: los VLMs ven la página anterior para coherencia
- **Reanudable**: corta y vuelve a ejecutar con `--resume`
- **Bilingüe**: interfaz y prompts en español o inglés
- **Sin APIs externas**: todo corre local, 100% privado

---

## Motores

| Motor | Flag | Tipo | Params | VRAM | Velocidad | Ideal para |
|-------|------|------|--------|------|-----------|------------|
| **LightOnOCR** | `lighton` (default) | VLM end-to-end | 1.0 B | ~2 GB | ~8 s/pág | Balance calidad/velocidad |
| **GLM-OCR** | `glm` | VLM end-to-end | 0.9 B | ~2.5 GB | ~10 s/pág | Tablas, fórmulas, layouts complejos |
| **Tesseract** | `tesseract` | Clásico LSTM | — | 0 (CPU) | ~1.5 s/pág | CPU, siempre funciona |

### LightOnOCR-2-1B `[default]`
VLM basado en Pixtral + Mistral 3. **Mejor equilibrio** entre velocidad y calidad. Genera Markdown estructurado con encabezados, párrafos y listas. Licencia Apache 2.0.

### GLM-OCR
VLM de Z.ai (CogViT + GLM-0.5B). **Máxima precisión**: 94.62 en OmniDocBench (#1). Ideal para documentos densos con tablas, fórmulas y layouts complejos. Licencia Apache 2.0.

### Tesseract
OCR clásico (5.5, LSTM+legacy). **Siempre funciona**, no requiere GPU. Detección básica de párrafos mediante segmentación de página. Licencia Apache 2.0.

---

## Guía rápida

| Quieres… | Usa |
|----------|-----|
| Buen resultado por defecto | `python PDFToEPUB.py documento.pdf` |
| Máxima calidad en tablas/layout | `python PDFToEPUB.py documento.pdf --engine glm` |
| Sin GPU, ligero | `python PDFToEPUB.py documento.pdf --engine tesseract` |

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
 └──┬───┘          NO     SÍ
    │               │     │
    ▼               ▼     ▼
 tesseract        ┌───────┴───┐
 1-3s/pág       Veloc.    Precisión
                  │         │
                  ▼         ▼
               lighton     glm
               ~8s/pág   ~10s/pág
```

---

## Instalación

```bash
# Dependencias base
pip install torch transformers pdf2image pillow

# Tesseract (sistema)
sudo apt install tesseract-ocr tesseract-ocr-spa poppler-utils pandoc
pip install pytesseract

# GLM-OCR (opcional, para máxima precisión)
pip install "transformers>=5.3.0"
```

---

## Uso

```bash
# LightOnOCR (default) → .md + .epub
python PDFToEPUB.py documento.pdf

# GLM-OCR — máxima precisión
python PDFToEPUB.py documento.pdf --engine glm

# Tesseract — CPU, siempre funciona
python PDFToEPUB.py documento.pdf --engine tesseract

# Solo Markdown
python PDFToEPUB.py documento.pdf --no-epub

# Con metadatos
python PDFToEPUB.py documento.pdf --title "Mi Libro" --author "Autor"

# Rango de páginas + reanudar
python PDFToEPUB.py documento.pdf --first-page 5 --last-page 10 --resume

# Español
python PDFToEPUB.py documento.pdf --lang es
```

### Opciones

| Argumento | Descripción |
|-----------|-------------|
| `pdf` | Archivo PDF de entrada |
| `--engine` | `lighton` (default), `glm`, `tesseract` |
| `-o, --output` | Ruta de salida (.md o .epub) |
| `--dpi` | DPI de imagen (200) |
| `--max-h` | Altura máxima en px (768). Bajar si OOM |
| `--first-page` | Primera página |
| `--last-page` | Última página |
| `--resume` | Reanudar desde salida existente |
| `--cpu` | Forzar CPU |
| `--no-epub` | Saltar EPUB (solo .md) |
| `--title` | Título para metadatos EPUB |
| `--author` | Autor (repetible) |
| `--lang` | `en` o `es` |
| `--context-window` | Páginas de contexto (5). 0 = sin contexto |
| `--reload-every` | Recargar modelo cada N páginas |

---

## Cómo funciona

### VLM (lighton, glm)
```
PDF → rasterizar (200 DPI) → redimensionar (768px) → VLM (GPU) → Markdown → EPUB
```

### Tesseract
```
PDF → rasterizar → segmentación de página → OCR LSTM → texto con párrafos
```

---

## Rendimiento

| Motor | Dispersa | Texto denso | Muy denso | Media |
|-------|----------|-------------|-----------|-------|
| LightOnOCR | 4-7 s | 20-65 s | 60-130 s | ~14 s |
| GLM-OCR | 3-6 s | 15-50 s | 40-100 s | ~10 s |
| Tesseract | 0.5-2 s | 1-3 s | 2-5 s | ~1.5 s |

| Motor | VRAM (cargando) | VRAM (pico) |
|-------|-----------------|-------------|
| LightOnOCR | ~2.0 GB | ~2.5 GB |
| GLM-OCR | ~2.3 GB | ~3.0 GB |
| Tesseract | 0 (CPU) | 0 (CPU) |

---

## Solución de problemas

| Problema | Solución |
|----------|----------|
| OOM en páginas densas | `--max-h 512` o `--dpi 150` |
| GLM-OCR: transformers muy viejo | `pip install "transformers>=5.3.0"` |
| Tesseract: binario no encontrado | `sudo apt install tesseract-ocr` |
| Pandoc no instalado | `sudo apt install pandoc` |

---

## Licencias

| Componente | Licencia |
|------------|----------|
| Código del repositorio | **GPLv3** |
| LightOnOCR-2-1B | Apache 2.0 |
| GLM-OCR | Apache 2.0 |
| PyTorch | BSD |
| Transformers | Apache 2.0 |

---

<p align="center">
  Hecho con ❤️ para convertir PDFs en libros electrónicos.
</p>
