# Batch OCR Processing - Deployment Guide

## Quick Start

### 1. Build the Docker image
```bash
docker build -t ocr-batch-processor .
```

### 2. Run batch processing
```bash
docker run -v /path/to/input:/input -v /path/to/output:/output \
  ocr-batch-processor python batch_process.py /input /output -p 4 -j 12
```

## Usage

### Basic Workflow

The script processes folders like this:
```
/input/
  ├── 630666-01/          →  /output/630666-01.pdf
  ├── 629157-02/          →  /output/629157-02.pdf
  └── 633421-03/          →  /output/633421-03.pdf
```

Each subfolder containing TIF/JPG/PDF files becomes one output PDF with OCR.

### Command Options

```bash
python batch_process.py <input_dir> <output_dir> [options]

Options:
  -p, --parallel N              Number of folders to process in parallel (default: 4)
  -j, --jobs-per-folder N       Number of OCR jobs per folder (default: 12)
  --accurate-ocr                Use accurate OCR mode (slower, larger files)
  --timeout SECONDS             Timeout per folder (default: 3600 = 1 hour)
  --dry-run                     List folders without processing
```

### Recommended Settings for 48-Core Machine

**Option 1: Balanced (recommended)**
```bash
# 4 folders in parallel, 12 cores each = 48 total cores
docker run -v /input:/input -v /output:/output \
  ocr-batch-processor python batch_process.py /input /output -p 4 -j 12
```

**Option 2: More parallelism**
```bash
# 6 folders in parallel, 8 cores each = 48 total cores
docker run -v /input:/input -v /output:/output \
  ocr-batch-processor python batch_process.py /input /output -p 6 -j 8
```

**Option 3: Sequential, max speed per folder**
```bash
# 1 folder at a time, all 48 cores on it
docker run -v /input:/input -v /output:/output \
  ocr-batch-processor python batch_process.py /input /output -p 1 -j 48
```

### Windows Paths

On Windows, use full paths like this:
```bash
docker run -v C:/Users/ncurtis/input:/input -v C:/Users/ncurtis/output:/output \
  ocr-batch-processor python batch_process.py /input /output -p 4 -j 12
```

Or with PowerShell:
```powershell
docker run -v "C:\Users\ncurtis\input:/input" -v "C:\Users\ncurtis\output:/output" `
  ocr-batch-processor python batch_process.py /input /output -p 4 -j 12
```

### Test Run (Dry Run)

To see what would be processed without actually doing it:
```bash
docker run -v /input:/input -v /output:/output \
  ocr-batch-processor python batch_process.py /input /output --dry-run
```

## What Each Step Does

1. **FINAL.py** - Processes a single folder:
   - Combines all TIF/JPG/PDF files into one PDF
   - Runs OCR with deskewing and rotation
   - Applies JBIG2 compression for smaller file size
   - Preserves OCR text layer

2. **batch_process.py** - Manages multiple folders:
   - Scans input directory for subfolders
   - Processes N folders in parallel using ProcessPoolExecutor
   - Shows progress and timing
   - Reports successes/failures at the end

## Monitoring

The script shows real-time progress:
```
[10:30:15] Starting: 630666-01
[10:30:15] Starting: 629157-02
[10:35:42] SUCCESS: 630666-01 -> 12.34 MB
[10:35:42] Progress: 1/10 folders completed
...
```

## Troubleshooting

### Folder not being processed
- Check that it contains .tif, .tiff, .jpg, .jpeg, or .pdf files
- Use `--dry-run` to see what folders are detected

### Out of memory
- Reduce parallel folders: `-p 2 -j 24` instead of `-p 4 -j 12`
- Large images use more RAM during OCR

### Timeout
- Increase timeout for large folders: `--timeout 7200` (2 hours)
- Or reduce jobs per folder to reduce memory pressure

### Permission errors
- Make sure output directory is writable
- On Windows, check Docker Desktop has access to the drives

## File Structure

```
OCRmyPDF/
├── FINAL.py              # Single folder processor
├── batch_process.py      # Batch wrapper (NEW)
├── opencv_optimizer.py   # JBIG2 compression
├── requirements.txt      # Python dependencies
├── Dockerfile           # Container definition
└── jbig2enc/            # JBIG2 encoder binaries
```

## Performance Expectations

- **Small documents** (10-20 pages): ~30-60 seconds per folder
- **Large documents** (100+ pages): 5-15 minutes per folder
- **48 cores**: Can process 4 large folders simultaneously

Example: 100 folders with ~50 pages each
- Single threaded: ~8 hours
- 4 parallel (48 cores): ~2 hours
