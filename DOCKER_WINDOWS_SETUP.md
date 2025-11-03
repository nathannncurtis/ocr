# Docker Setup Guide for Windows

## What to Copy

Copy this **entire folder** to your Windows machine:
```
OCRmyPDF/
├── batch_process.py
├── FINAL.py
├── opencv_optimizer.py
├── requirements.txt
├── Dockerfile
├── .dockerignore
├── jbig2enc/              (entire folder with all contents)
└── DOCKER_WINDOWS_SETUP.md (this file)
```

## Step 1: Install Docker Desktop on Windows

### Download Docker Desktop
1. Go to: https://www.docker.com/products/docker-desktop/
2. Click "Download for Windows"
3. Download `Docker Desktop Installer.exe`

### Install Docker Desktop
1. Run the installer
2. **IMPORTANT**: Make sure "Use WSL 2 instead of Hyper-V" is checked (default on modern Windows)
3. Follow the installation wizard
4. Restart your computer when prompted

### Start Docker Desktop
1. Launch "Docker Desktop" from Start Menu
2. Wait for it to start (you'll see "Docker Desktop is running" in system tray)
3. Accept the service agreement if prompted

### Verify Docker is Working
Open PowerShell and run:
```powershell
docker --version
```

You should see something like: `Docker version 24.x.x, build xxxxx`

## Step 2: Build the Container

Open PowerShell and navigate to your OCRmyPDF folder:

```powershell
cd C:\path\to\OCRmyPDF
```

Build the Docker image (this will take 5-10 minutes the first time):
```powershell
docker build -t ocr-batch-processor .
```

You'll see output like:
```
[+] Building 245.3s (12/12) FINISHED
 => [1/7] FROM docker.io/library/python:3.11-slim
 => [2/7] RUN apt-get update && apt-get install -y tesseract-ocr...
 ...
Successfully tagged ocr-batch-processor:latest
```

**IMPORTANT**: The dot (`.`) at the end of the command is required!

## Step 3: Run Batch Processing

### Test Run (Dry Run)
First, test to see what folders would be processed:

```powershell
docker run -v "C:\path\to\input:/input" -v "C:\path\to\output:/output" ocr-batch-processor python batch_process.py /input /output --dry-run
```

Replace `C:\path\to\input` and `C:\path\to\output` with your actual paths.

### Full Processing Run

For a 48-core machine (4 folders in parallel, 12 cores each):

```powershell
docker run -v "C:\path\to\input:/input" -v "C:\path\to\output:/output" ocr-batch-processor python batch_process.py /input /output -p 4 -j 12
```

### Example with Real Paths

```powershell
docker run -v "D:\Scans\ToProcess:/input" -v "D:\Scans\Processed:/output" ocr-batch-processor python batch_process.py /input /output -p 4 -j 12
```

## What Happens

1. Docker container starts
2. Scans `/input` for all subfolders containing images/PDFs
3. Processes 4 folders simultaneously (using 48 total CPU cores)
4. Each folder becomes one searchable, compressed PDF in `/output`
5. Shows progress in real-time
6. When ALL folders are done, prints summary and **stops**

Example output:
```
[10:30:15] BATCH OCR PROCESSING
[10:30:15] Folders found: 47
[10:30:15] Parallel folders: 4
[10:30:15] Jobs per folder: 12
[10:30:15] Total cores used: 48
[10:30:15] Starting: 630666-01
[10:30:15] Starting: 629157-02
[10:30:15] Starting: 633421-03
[10:30:15] Starting: 640123-04
[10:35:42] SUCCESS: 630666-01 -> 12.34 MB
[10:35:42] Progress: 1/47 folders completed
...
[12:45:30] PROCESSING COMPLETE
[12:45:30] Total time: 135.2 minutes
[12:45:30] Success: 47
[12:45:30] Failed: 0
```

Then it stops.

## Configuration Options

### Different Parallelism (for 48 cores)

**More folders, fewer cores each** (6 folders × 8 cores = 48):
```powershell
docker run -v "C:\input:/input" -v "C:\output:/output" ocr-batch-processor python batch_process.py /input /output -p 6 -j 8
```

**Sequential processing** (1 folder × 48 cores = 48):
```powershell
docker run -v "C:\input:/input" -v "C:\output:/output" ocr-batch-processor python batch_process.py /input /output -p 1 -j 48
```

### High-Quality OCR Mode

For better OCR accuracy (slower, larger files):
```powershell
docker run -v "C:\input:/input" -v "C:\output:/output" ocr-batch-processor python batch_process.py /input /output -p 4 -j 12 --accurate-ocr
```

### Longer Timeout

For very large documents (default is 1 hour per folder):
```powershell
docker run -v "C:\input:/input" -v "C:\output:/output" ocr-batch-processor python batch_process.py /input /output -p 4 -j 12 --timeout 7200
```

## Troubleshooting

### Docker Desktop won't start
- Make sure virtualization is enabled in BIOS
- Windows 10/11 Home requires WSL 2 (should install automatically)
- Check Windows updates are installed

### "docker: command not found"
- Docker Desktop is not running (check system tray)
- Restart PowerShell after installing Docker

### "Error response from daemon: invalid mount config"
- Check your paths use `\` or `/` correctly
- Make sure paths are absolute (e.g., `C:\...`)
- Paths are case-insensitive on Windows

### "permission denied" or "access denied"
- Docker Desktop → Settings → Resources → File Sharing
- Make sure your drive (C:\, D:\, etc.) is shared
- Click "Apply & Restart"

### Container is slow or not using all cores
- Docker Desktop → Settings → Resources
- Increase CPUs to 48 (or max available)
- Increase Memory to at least 16 GB (more is better)
- Click "Apply & Restart"

### Process killed / out of memory
- Reduce parallel folders: `-p 2 -j 24` instead of `-p 4 -j 12`
- Increase Docker memory limit in Docker Desktop settings
- Process fewer folders at once

## Re-running / Updates

If you need to rebuild the container (after code changes):
```powershell
docker build -t ocr-batch-processor .
```

To remove old container images and free up space:
```powershell
docker system prune -a
```

## Input Folder Structure

Your input folder should look like:
```
D:\Scans\ToProcess\
  ├── 630666-01\
  │   ├── page_001.tif
  │   ├── page_002.tif
  │   └── page_003.tif
  ├── 629157-02\
  │   ├── scan001.jpg
  │   └── scan002.jpg
  └── 633421-03\
      └── document.pdf
```

Each subfolder will become one PDF in the output folder:
```
D:\Scans\Processed\
  ├── 630666-01.pdf
  ├── 629157-02.pdf
  └── 633421-03.pdf
```

## Performance

On a 48-core Windows machine with Docker:
- Small docs (10-20 pages): ~30-60 seconds
- Medium docs (50 pages): ~2-5 minutes
- Large docs (100+ pages): ~5-15 minutes
- 100 folders (~50 pages each): ~2-3 hours total

## What Docker Installs

Docker Desktop includes:
- Docker Engine
- WSL 2 (Windows Subsystem for Linux)
- Linux kernel for Windows

Size: ~2-3 GB

All dependencies (Tesseract, Python, etc.) are **inside the container** - your Windows system stays clean!
