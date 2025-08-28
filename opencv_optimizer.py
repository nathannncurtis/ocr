#!/usr/bin/env python3
"""
PDF optimizer script

Two modes:
- in-place: optimize images in PDF while keeping vectors/text
- jbig2-rebuild: rebuild PDF with maximum JBIG2 compression (images only)
"""

import io, os, sys, subprocess, tempfile, statistics, secrets, string, shutil
from pathlib import Path
from typing import List
import fitz
from PIL import Image
import numpy as np

# settings
PT_PER_INCH = 72.0
JPEG_QUALITY = 60
COLOR_THRESHOLD_PPI = 225
COLOR_TARGET_PPI = 150
MONO_THRESHOLD_PPI = 450
MONO_TARGET_PPI = 300
SIZE_IMPROVEMENT_FACTOR = 0.98

# detect environment
def is_docker():
    return os.path.exists('/.dockerenv') or os.environ.get('DOCKER_CONTAINER') == '1'

def is_wsl():
    return os.path.exists('/proc/version') and 'Microsoft' in open('/proc/version').read()

# environment-specific paths
if is_docker():
    JBIG2_BIN = "jbig2"
    # look for jbig2topdf.py in common Docker locations
    possible_paths = ["/usr/local/bin/jbig2topdf.py", "/app/jbig2enc/jbig2topdf.py", "./jbig2enc/jbig2topdf.py"]
    JBIG2TOPDF_PY = next((p for p in possible_paths if os.path.exists(p)), possible_paths[0])
    WSL_MODE = False
elif is_wsl():
    WSL_DISTRO = "Ubuntu"
    JBIG2_BIN = "jbig2"
    # WSL-specific path
    script_dir = os.path.dirname(os.path.abspath(__file__))
    JBIG2TOPDF_PY = os.path.join(script_dir, "jbig2enc", "jbig2enc", "jbig2topdf.py")
    WSL_MODE = True
else:
    # assume Linux native
    JBIG2_BIN = "jbig2"
    script_dir = os.path.dirname(os.path.abspath(__file__))
    JBIG2TOPDF_PY = os.path.join(script_dir, "jbig2enc", "jbig2topdf.py")
    WSL_MODE = False

# validate environment
if not shutil.which(JBIG2_BIN):
    print(f"WARNING: {JBIG2_BIN} not found in PATH. jbig2-rebuild mode will not work.")

if not os.path.exists(JBIG2TOPDF_PY):
    print(f"WARNING: {JBIG2TOPDF_PY} not found. jbig2-rebuild mode will not work.")

class ImgInfo:
    def __init__(self, xref, width, height, dpi_x, dpi_y, colorspace, bpc):
        self.xref = xref
        self.width = width
        self.height = height
        self.dpi_x = dpi_x
        self.dpi_y = dpi_y
        self.colorspace = colorspace
        self.bpc = bpc
    rect: fitz.Rect
    before: bytes
    pil: Image.Image
    eff_ppi: float

def _largest_rect(rects: List[fitz.Rect]) -> fitz.Rect:
    return max(rects, key=lambda r: r.width * r.height) if rects else fitz.Rect(0,0,1,1)

def _eff_ppi(pil: Image.Image, rect: fitz.Rect) -> float:
    w_in = max(rect.width / PT_PER_INCH, 1e-6)
    h_in = max(rect.height / PT_PER_INCH, 1e-6)
    return min(pil.width / w_in, pil.height / h_in)

def _is_full_color(pil, mean_tol=2.5, max_tol=25):
    # check if image is actually color or just grayscale
    im = pil
    if im.mode not in ("RGB","L","1"):
        im = im.convert("RGB")
    if im.mode in ("L","1"):
        return False
    if max(im.size) > 1200:
        s = 1200 / max(im.size)
        im = im.resize((max(1,int(im.width*s)), max(1,int(im.height*s))), Image.BILINEAR)
    arr = np.asarray(im, dtype=np.uint8)
    R,G,B = arr[...,0].astype(np.int16), arr[...,1].astype(np.int16), arr[...,2].astype(np.int16)
    md = np.maximum.reduce([np.abs(R-G), np.abs(R-B), np.abs(G-B)])
    return not (md.mean() <= mean_tol and md.max() <= max_tol)

def _target_dims(rect, eff_ppi, is_mono, w, h):
    if is_mono and eff_ppi > MONO_THRESHOLD_PPI:
        return (int(round(rect.width/PT_PER_INCH*MONO_TARGET_PPI)),
                int(round(rect.height/PT_PER_INCH*MONO_TARGET_PPI)))
    if (not is_mono) and eff_ppi > COLOR_THRESHOLD_PPI:
        return (int(round(rect.width/PT_PER_INCH*COLOR_TARGET_PPI)),
                int(round(rect.height/PT_PER_INCH*COLOR_TARGET_PPI)))
    return w,h

def _enc_jpeg(pil, w, h, gray):
    im = pil.convert("L" if gray else "RGB")
    if im.size != (w,h): im = im.resize((w,h), Image.LANCZOS)
    b = io.BytesIO(); im.save(b, "JPEG", quality=JPEG_QUALITY, optimize=True); return b.getvalue()

def _enc_g4(pil, w, h):
    im = pil.convert("1")
    if im.size != (w,h): im = im.resize((w,h), Image.NEAREST)
    b = io.BytesIO(); im.save(b, "TIFF", compression="group4"); return b.getvalue()

def _collect(page, doc):
    out=[]
    for t in page.get_images(full=True):
        xref = t[0]
        rect = _largest_rect(page.get_image_rects(xref))
        raw = doc.extract_image(xref)["image"]
        pil = Image.open(io.BytesIO(raw)); pil.load()
        # fix constructor call to match new class
        info = ImgInfo(xref, pil.width, pil.height, _eff_ppi(pil, rect), _eff_ppi(pil, rect), None, None)
        info.rect = rect
        info.raw = raw
        info.pil = pil
        out.append(info)
    return out

# ----------------- in-place -----------------

def optimize_in_place(inp: str, outp: str, linearize=False):
    orig = os.path.getsize(inp)
    doc = fitz.open(inp)
    rep = keep = 0
    print(f"[in-place] Opened {inp}, pages={doc.page_count}")

    for pno in range(doc.page_count):
        page = doc[pno]
        for info in _collect(page, doc):
            is_color = _is_full_color(info.pil)
            is_mono  = not is_color
            tw,th = _target_dims(info.rect, info.eff_ppi, is_mono, info.pil.width, info.pil.height)

            if is_mono:
                data = _enc_g4(info.pil, tw, th); method="g4"
            else:
                data = _enc_jpeg(info.pil, tw, th, gray=False); method="jpeg"

            if len(data) <= int(len(info.before)*SIZE_IMPROVEMENT_FACTOR):
                page.replace_image(info.xref, stream=data); rep += 1
                print(f"Pg {pno+1} xref {info.xref}: {'mono' if is_mono else 'color'} @{info.eff_ppi:.1f}ppi "
                      f"-> {tw}x{th} ({len(info.before)//1024}KB->{len(data)//1024}KB) via {method}")
            else:
                keep += 1
                print(f"Pg {pno+1} xref {info.xref}: kept original ({len(info.before)//1024}KB) – new {len(data)//1024}KB via {method}")

    tmp=outp+".tmp"; doc.save(tmp, deflate=True, clean=True, garbage=4); doc.close(); os.replace(tmp,outp)
    if linearize and shutil.which("qpdf"):
        tmp2=outp+".tmp"
        if subprocess.run(["qpdf","--linearize",outp,tmp2]).returncode==0: os.replace(tmp2,outp)

    fin=os.path.getsize(outp)
    print(f"\nDone: {orig//1024}KB -> {fin//1024}KB ({rep} replaced, {keep} kept)")
    if fin<=orig: print(f"Saved {(orig-fin)/orig*100:.0f}%")

# jbig2 rebuild mode

def _rand_suffix(n=6):
    alphabet = string.ascii_lowercase + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(n))

def _render_1bit_pngs(pdf_path, work, dpi):
    work.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(pdf_path)
    scale = dpi / 72.0
    pages = []
    for i, page in enumerate(doc):
        pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
        im = Image.frombytes("RGB", (pix.width, pix.height), pix.samples).convert("1")
        outp = work / f"page_{i:04d}.png"
        im.save(outp.as_posix(), "PNG", optimize=True)
        pages.append(outp)
    doc.close()
    return pages

def _run_cmd(cmd, *, input_bytes=None):
    if WSL_MODE:
        return subprocess.run(["wsl","-d",WSL_DISTRO,"bash","-lc", cmd],
                              input=input_bytes, capture_output=True)
    else:
        # Docker or native Linux
        return subprocess.run(["bash","-c", cmd],
                              input=input_bytes, capture_output=True)

def _push_bytes(abs_path, data):
    # Write bytes to file via stdin
    cmd = f"set -e; mkdir -p \"$(dirname '{abs_path}')\"; cat > '{abs_path}'"
    r = _run_cmd(cmd, input_bytes=data)
    if r.returncode != 0:
        stderr = r.stderr.decode(errors='ignore') if r.stderr else 'No stderr'
        raise RuntimeError(f"Push failed for {abs_path}: {stderr}")
    
    # verify file was created
    verify_r = _run_cmd(f"ls -l '{abs_path}'")
    if verify_r.returncode != 0:
        raise RuntimeError(f"File verification failed for {abs_path}")

def _pull_bytes(abs_path):
    r = _run_cmd(f"set -e; cat '{abs_path}'")
    if r.returncode != 0:
        raise RuntimeError(f"Pull failed for {abs_path}: {r.stderr.decode(errors='ignore')}")
    return r.stdout

def _estimate_dpi_for_rebuild(pdf_path: str) -> int:
    # Heuristic: median PPI of largest image on up to 50 pages
    doc = fitz.open(pdf_path)
    ppis=[]
    for i in range(min(doc.page_count, 50)):
        page = doc[i]
        imgs = page.get_images(full=True)
        if not imgs: continue
        def area_of_xref(x):
            r = _largest_rect(page.get_image_rects(x))
            return r.width*r.height
        xref = max((t[0] for t in imgs), key=area_of_xref)
        rect = _largest_rect(page.get_image_rects(xref))
        raw = doc.extract_image(xref)["image"]
        pil = Image.open(io.BytesIO(raw)); pil.load()
        ppis.append(_eff_ppi(pil, rect))
    doc.close()
    if not ppis: return 300
    dpi = int(round(statistics.median(ppis)))
    return max(150, min(600, dpi))

def rebuild_jbig2(inp, outp, dpi=None):
    inp = os.path.abspath(inp)
    outp = os.path.abspath(outp)
    out_dir = Path(outp).parent
    work_dir = out_dir / f"_jbig2work_{os.getpid()}"
    tag = _rand_suffix()
    temp_root = f"/tmp/jbig2rebuild_{os.getpid()}_{tag}"
    temp_in_dir = f"{temp_root}/pages"
    temp_out_base = f"{temp_root}/out"
    temp_out_pdf = f"{temp_root}/out.pdf"
    temp_topdf = f"{temp_root}/jbig2topdf.py"

    try:
        if dpi is None:
            dpi = _estimate_dpi_for_rebuild(inp)
        print(f"Using DPI={dpi}")

        # render to 1-bit PNGs
        pages = _render_1bit_pngs(inp, work_dir, dpi)
        print(f"Rendered {len(pages)} pages")

        # prepare working area
        r = _run_cmd(f"set -e; mkdir -p '{temp_in_dir}'")
        if r.returncode != 0:
            raise RuntimeError(f"mkdir failed: {r.stderr.decode(errors='ignore')}")

        # transfer PNG files
        print(f"Transferring {len(pages)} files...")
        for i, p in enumerate(pages):
            data = p.read_bytes()
            rel = p.name  # page_0000.png
            dest_path = f"{temp_in_dir}/{rel}"
            _push_bytes(dest_path, data)
            if (i + 1) % 50 == 0 or i == len(pages) - 1:
                print(f"Transferred {i + 1}/{len(pages)} files")
        # copy jbig2topdf.py
        topdf_data = Path(JBIG2TOPDF_PY).read_bytes()
        _push_bytes(temp_topdf, topdf_data)

        # run jbig2 encoding
        # verify jbig2 is available
        r = _run_cmd(f"which {JBIG2_BIN}")
        if r.returncode != 0:
            raise RuntimeError("`jbig2` not found in PATH")
        
        # verify files
        r = _run_cmd(f"ls -1 {temp_in_dir}/page_*.png | wc -l")
        if r.returncode != 0:
            raise RuntimeError("Failed to count PNG files")
        
        file_count = int(r.stdout.decode().strip())
        print(f"Found {file_count} PNG files")
        
        if file_count == 0:
            raise RuntimeError("No pages found")
        
        # create output directory and run jbig2
        r = _run_cmd(f"mkdir -p $(dirname {temp_out_base})")
        if r.returncode != 0:
            raise RuntimeError("Failed to create output directory")
            
        # run jbig2 compression
        cmd = f"cd {temp_in_dir} && {JBIG2_BIN} -s -p -b {temp_out_base} page_*.png"
        r = _run_cmd(cmd)
        if r.returncode != 0:
            stderr = r.stderr.decode(errors='ignore') if r.stderr else 'No stderr'
            raise RuntimeError(f"jbig2 failed: {stderr}")
        
        # verify jbig2 output files
        r = _run_cmd(f"ls -l {temp_out_base}.sym {temp_out_base}.0000")
        if r.returncode != 0:
            raise RuntimeError("jbig2 output files not found")
        
        # generate PDF
        python_cmd = "python3" if shutil.which("python3") else "python"
        r = _run_cmd(f"{python_cmd} {temp_topdf} {temp_out_base} > {temp_out_pdf}")
        if r.returncode != 0:
            stderr = r.stderr.decode(errors='ignore') if r.stderr else 'No stderr'
            raise RuntimeError(f"PDF generation failed: {stderr}")

        # get final PDF
        pdf_bytes = _pull_bytes(temp_out_pdf)
        Path(outp).write_bytes(pdf_bytes)

        # optional linearize
        if shutil.which("qpdf"):
            tmp = outp + ".tmp"
            if subprocess.run(["qpdf","--linearize",outp,tmp]).returncode==0:
                os.replace(tmp, outp)

        print(f"Done: {outp}")

    finally:
        # cleanup
        shutil.rmtree(work_dir, ignore_errors=True)
        _run_cmd(f"rm -rf '{temp_root}'")

# main

def main():
    if len(sys.argv) < 3:
        print("Usage: python opencv_optimizer.py input.pdf output.pdf [--mode in-place|jbig2-rebuild] [--dpi N]")
        sys.exit(1)

    inp, outp = sys.argv[1], sys.argv[2]
    mode = "in-place"
    linearize = ("--linearize" in sys.argv)
    dpi = None
    for i, tok in enumerate(sys.argv):
        if tok == "--mode" and i+1 < len(sys.argv):
            mode = sys.argv[i+1]
        if tok == "--dpi" and i+1 < len(sys.argv):
            try: dpi = int(sys.argv[i+1])
            except: pass

    if mode == "in-place":
        optimize_in_place(inp, outp, linearize=linearize)
    elif mode == "jbig2-rebuild":
        rebuild_jbig2(inp, outp, dpi=dpi)
    else:
        sys.exit(f"Unknown mode: {mode}")

if __name__ == "__main__":
    main()
