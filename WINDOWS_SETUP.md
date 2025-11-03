# Windows Native Setup Guide

## Files to Copy

Copy this **entire folder** to your Windows machine. You need all these files:
```
OCRmyPDF/
├── batch_process.py
├── FINAL.py
├── opencv_optimizer.py
├── requirements.txt
├── jbig2enc/              (entire folder with all contents)
└── WINDOWS_SETUP.md       (this file)
```

## Installation Steps

### 1. Install Python 3.11+

Download and install Python from: https://www.python.org/downloads/

**IMPORTANT**: During installation, check the box "Add Python to PATH"

Verify installation:
```powershell
python --version
# Should show: Python 3.11.x or higher
```

### 2. Install Tesseract OCR

Download and install from: https://github.com/UB-Mannheim/tesseract/wiki

**Download**: `tesseract-ocr-w64-setup-5.3.x.exe` (or latest version)

**IMPORTANT**: During installation:
- Note the installation path (usually `C:\Program Files\Tesseract-OCR`)
- Install the "English" language pack (should be included by default)

Add Tesseract to your PATH:
1. Open System Properties → Environment Variables
2. Under "System Variables", find "Path" and click Edit
3. Add: `C:\Program Files\Tesseract-OCR`
4. Click OK

Verify installation:
```powershell
tesseract --version
# Should show version information
```

### 3. Install Ghostscript

Download from: https://ghostscript.com/releases/gsdnld.html

**Download**: `gs10.xx.x` for Windows (64-bit)

Install with default settings.

Verify (after installation):
```powershell
gswin64c --version
# Should show version information
```

### 4. Install qpdf

Download from: https://github.com/qpdf/qpdf/releases

**Download**: `qpdf-11.x.x-bin-msvc64.zip` (or latest)

Extract to `C:\Program Files\qpdf`

Add to PATH:
1. Open System Properties → Environment Variables
2. Under "System Variables", find "Path" and click Edit
3. Add: `C:\Program Files\qpdf\bin`
4. Click OK

Verify:
```powershell
qpdf --version
# Should show version information
```

### 5. Install pngquant (Optional but recommended)

Download from: https://pngquant.org/

**Download**: Windows binary

Extract `pngquant.exe` to a folder like `C:\Program Files\pngquant\`

Add to PATH:
1. Open System Properties → Environment Variables
2. Under "System Variables", find "Path" and click Edit
3. Add: `C:\Program Files\pngquant`
4. Click OK

Verify:
```powershell
pngquant --version
# Should show version information
```

### 6. Install Python Dependencies

Open PowerShell or Command Prompt in the OCRmyPDF folder and run:

```powershell
cd C:\path\to\OCRmyPDF
pip install -r requirements.txt
```

This installs:
- PyMuPDF (PDF manipulation)
- Pillow (image processing)
- numpy (numerical operations)
- ocrmypdf (main OCR engine)
- img2pdf (image to PDF conversion)

### 7. Setup jbig2enc Path

The `jbig2enc` folder contains pre-compiled binaries. Make sure the path is correct in `opencv_optimizer.py`.

Check if `jbig2enc/jbig2.exe` exists in your OCRmyPDF folder. If the script can't find it, you may need to update the path.

## Running the Batch Processor

### Test Installation

First, test with a dry run:
```powershell
cd C:\path\to\OCRmyPDF
python batch_process.py "C:\path\to\input" "C:\path\to\output" --dry-run
```

This will show you what folders would be processed without actually doing it.

### Run Batch Processing

For a 48-core machine:
```powershell
python batch_process.py "C:\path\to\input" "C:\path\to\output" -p 4 -j 12
```

This processes:
- 4 folders in parallel
- 12 CPU cores per folder (for OCR parallelism)
- Total: 48 cores utilized

### Example

```powershell
cd C:\OCRmyPDF
python batch_process.py "D:\Scans\ToProcess" "D:\Scans\Processed" -p 4 -j 12
```

## Troubleshooting

### "python not recognized"
- Python not installed or not in PATH
- Restart PowerShell/Command Prompt after installation

### "tesseract not recognized"
- Tesseract not in PATH
- Add `C:\Program Files\Tesseract-OCR` to PATH
- Restart PowerShell/Command Prompt

### "No module named 'ocrmypdf'"
- Python packages not installed
- Run: `pip install -r requirements.txt`

### "jbig2 not found"
- Check that `jbig2enc` folder exists
- Check that `jbig2enc/jbig2.exe` exists
- If missing, you may need to compile or obtain jbig2enc separately

### "Failed to find jbig2topdf.py"
- Should be in `jbig2enc/jbig2topdf.py`
- If missing, the JBIG2 optimization will fail

### Out of Memory
- Reduce parallel folders: `-p 2 -j 24` instead of `-p 4 -j 12`
- Close other applications
- Large TIF files use significant RAM during processing

### Slow Performance
- Increase jobs per folder if you have cores available
- Check Task Manager to see if CPU is fully utilized
- Some pages may take longer if they're complex or high-resolution

## Performance Expectations

On a 48-core Windows machine:
- Small documents (10-20 pages): ~30-60 seconds each
- Medium documents (50 pages): ~2-5 minutes each
- Large documents (100+ pages): ~5-15 minutes each

100 folders with ~50 pages each: approximately 2-3 hours total

## What Gets Installed

System-wide tools:
- Python 3.11+ (~100 MB)
- Tesseract OCR (~100 MB)
- Ghostscript (~50 MB)
- qpdf (~10 MB)
- pngquant (~500 KB)

Python packages (in Python's site-packages):
- ocrmypdf and dependencies (~50 MB)

Local to project:
- jbig2enc binaries (already in your folder)

Total: ~300-400 MB
