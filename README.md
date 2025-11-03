# OCRmyPDF Batch Processor

Batch process multiple folders of scanned documents (TIFF, JPEG, PDF) into searchable, compressed PDFs using OCR.

## Features

- **Batch processing**: Process entire directories of document folders in parallel
- **OCR with Tesseract**: Adds searchable text layer with automatic deskewing and rotation
- **JBIG2 compression**: Optimizes file size while preserving OCR quality
- **Parallel processing**: Utilize all CPU cores efficiently
- **Docker-based**: Easy deployment, consistent environment

## Quick Start

```bash
# Build the Docker image
docker build -t ocr-batch-processor .

# Process all folders in /input, output to /output
# 4 folders in parallel, 12 CPU cores per folder (48 total)
docker run -v /path/to/input:/input -v /path/to/output:/output \
  ocr-batch-processor python batch_process.py /input /output -p 4 -j 12
```

## What It Does

```
Input folder structure:       Output:
/input/                       /output/
  ├── 630666-01/             ├── 630666-01.pdf (searchable, compressed)
  │   ├── page_001.tif       ├── 629157-02.pdf (searchable, compressed)
  │   ├── page_002.tif       └── 633421-03.pdf (searchable, compressed)
  │   └── page_003.tif
  ├── 629157-02/
  │   └── scan.pdf
  └── 633421-03/
      ├── img001.jpg
      └── img002.jpg
```

Each subfolder becomes one output PDF with:
- Full text OCR layer (searchable/copyable)
- Automatic page rotation and deskewing
- JBIG2 compression (smaller file size)
- Preserved image quality

## Usage

### For 48-Core Machine (Recommended)

**Balanced approach** (4 folders × 12 cores = 48 cores):
```bash
docker run -v /input:/input -v /output:/output \
  ocr-batch-processor python batch_process.py /input /output -p 4 -j 12
```

**More parallelism** (6 folders × 8 cores = 48 cores):
```bash
docker run -v /input:/input -v /output:/output \
  ocr-batch-processor python batch_process.py /input /output -p 6 -j 8
```

### Advanced Options

```bash
# High-quality OCR (slower, larger files)
docker run -v /input:/input -v /output:/output \
  ocr-batch-processor python batch_process.py /input /output -p 4 -j 12 --accurate-ocr

# Preview what will be processed (no actual processing)
docker run -v /input:/input -v /output:/output \
  ocr-batch-processor python batch_process.py /input /output --dry-run

# Longer timeout for very large documents
docker run -v /input:/input -v /output:/output \
  ocr-batch-processor python batch_process.py /input /output -p 4 -j 12 --timeout 7200
```

### Single Folder Processing

If you just need to process one folder:
```bash
docker run -v /path/to/folder:/input -v /output:/output \
  ocr-batch-processor python FINAL.py /input/subfolder /output/result.pdf -j 48
```

## Documentation

See [DEPLOYMENT.md](DEPLOYMENT.md) for detailed deployment instructions, troubleshooting, and performance expectations.

## Components

- **batch_process.py**: Parallel batch processing wrapper
- **FINAL.py**: Single folder processor (combine → OCR → compress)
- **opencv_optimizer.py**: JBIG2 compression engine
- **jbig2enc/**: JBIG2 encoder binaries and utilities

## Requirements

- Docker
- Input folders containing TIFF, JPEG, or PDF files
- Sufficient disk space for output

## Performance

On a 48-core machine:
- Small docs (10-20 pages): ~30-60 seconds each
- Large docs (100+ pages): ~5-15 minutes each
- 100 folders (~50 pages each): ~2 hours total

## License

Uses OCRmyPDF, Tesseract OCR, and jbig2enc. See respective licenses.
