#!/usr/bin/env python3
"""
FINAL.py - PDF processing script

Takes a folder of images/PDFs, combines them, runs OCR, and optimizes with JBIG2.
Basically my workflow for processing scanned documents.

Usage: python FINAL.py <folder> <output.pdf>
"""

import os
import sys
import tempfile
import subprocess
import shutil
from pathlib import Path
import img2pdf
import argparse

def log(msg):
    print(f"[FINAL] {msg}")

def run_cmd(cmd, desc):
    log(f"{desc}...")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        log(f"ERROR: {desc} failed!")
        log(f"Error: {result.stderr}")
        return False
    return True

def get_size_mb(path):
    return os.path.getsize(path) / (1024 * 1024)

def combine_files_to_pdf(input_folder, output_pdf):
    # combine all the tiffs/jpegs/pdfs into one pdf
    input_path = Path(input_folder)
    
    # find images and pdfs
    imgs = sorted(list(input_path.glob("*.tif")) + list(input_path.glob("*.tiff")) + 
                 list(input_path.glob("*.jpg")) + list(input_path.glob("*.jpeg")))
    
    pdfs = sorted(list(input_path.glob("*.pdf")))
    
    if not imgs and not pdfs:
        log("ERROR: No files found")
        return False
    
    log(f"Found {len(imgs)} images and {len(pdfs)} PDFs")
    
    try:
        # just one PDF? copy it
        if not imgs and len(pdfs) == 1:
            shutil.copy2(pdfs[0], output_pdf)
            size_mb = get_size_mb(output_pdf)
            log(f"Copied single PDF: {size_mb:.2f} MB")
            return True
        elif not imgs and len(pdfs) > 1:
            # merge multiple PDFs
            import fitz
            result_doc = fitz.open()
            for pdf in pdfs:
                doc = fitz.open(pdf)
                result_doc.insert_pdf(doc)
                doc.close()
            result_doc.save(output_pdf)
            result_doc.close()
            size_mb = get_size_mb(output_pdf)
            log(f"Merged {len(pdfs)} PDFs: {size_mb:.2f} MB")
            return True
        elif not pdfs:
            # just images - convert with img2pdf
            file_paths = [str(f) for f in imgs]
            with open(output_pdf, 'wb') as f:
                f.write(img2pdf.convert(file_paths))
            size_mb = get_size_mb(output_pdf)
            log(f"Combined {len(imgs)} images: {size_mb:.2f} MB")
            return True
        else:
            # mixed content - convert images first then merge everything
            import fitz
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                
                temp_img_pdf = None
                if imgs:
                    temp_img_pdf = temp_path / "images.pdf"
                    file_paths = [str(f) for f in imgs]
                    with open(temp_img_pdf, 'wb') as f:
                        f.write(img2pdf.convert(file_paths))
                
                # merge everything
                result_doc = fitz.open()
                
                if temp_img_pdf:
                    doc = fitz.open(temp_img_pdf)
                    result_doc.insert_pdf(doc)
                    doc.close()
                
                for pdf in pdfs:
                    doc = fitz.open(pdf)
                    result_doc.insert_pdf(doc)
                    doc.close()
                
                result_doc.save(output_pdf)
                result_doc.close()
                
                size_mb = get_size_mb(output_pdf)
                total = len(imgs) + len(pdfs)
                log(f"Combined {total} files: {size_mb:.2f} MB")
                return True
        
    except Exception as e:
        log(f"ERROR: Failed to combine files: {e}")
        return False

def run_ocr(input_pdf, output_pdf, fast_mode=True, args=None):
    # run ocrmypdf with my preferred settings
    
    jobs = args.jobs if args else 12
    
    cmd = [sys.executable, '-m', 'ocrmypdf',
           '--deskew', '--rotate-pages', '--rotate-pages-threshold', '1',
           '--skip-text', '--optimize', '0', '--jpeg-quality', '0', 
           '--png-quality', '0', '--jbig2-lossy', '-l', 'eng',
           '--output-type', 'pdf', '-j', str(jobs)]
    
    if fast_mode:
        cmd.extend(['--tesseract-pagesegmode', '1', '--tesseract-oem', '1', '--tesseract-timeout', '30.0'])
    else:
        cmd.extend(['--tesseract-pagesegmode', '6'])
    
    cmd.extend([input_pdf, output_pdf])
    
    mode = "fast" if fast_mode else "accurate"
    log(f"Running OCR ({mode} mode)...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        log(f"OCR failed: {result.stderr}")
        return False
    
    size_mb = get_size_mb(output_pdf)
    log(f"OCR done: {size_mb:.2f} MB")
    return True

def run_jbig2_opt(input_pdf, output_pdf, preserve_ocr=True, force_jbig2=False):
    # run my opencv optimizer script
    script_dir = Path(__file__).parent
    optimizer_script = script_dir / "opencv_optimizer.py"
    
    if not optimizer_script.exists():
        log("ERROR: opencv_optimizer.py not found")
        return False
    
    if force_jbig2 or not preserve_ocr:
        cmd = [sys.executable, str(optimizer_script), input_pdf, output_pdf, '--mode', 'jbig2-rebuild', '--dpi', '200']
        log("JBIG2 rebuild mode...")
    else:
        cmd = [sys.executable, str(optimizer_script), input_pdf, output_pdf, '--mode', 'in-place']
        log("In-place optimization...")
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        log(f"Optimization failed: {result.stderr}")
        return False
    
    size_mb = get_size_mb(output_pdf)
    log(f"Optimization done: {size_mb:.2f} MB")
    return True

def main():
    parser = argparse.ArgumentParser(
        description="Complete PDF processing: Images → OCR → JBIG2 optimization",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python FINAL.py "C:/images/folder" "result.pdf"
  python FINAL.py "C:/images/folder" "result.pdf" --dpi 300
  python FINAL.py "C:/images/folder" "result.pdf" --accurate-ocr
        """
    )
    
    parser.add_argument('input_folder', help='Folder containing TIFF, JPEG, and/or PDF files')
    parser.add_argument('output_pdf', help='Output PDF file path')
    parser.add_argument('--dpi', type=int, default=200, 
                       help='DPI for JBIG2 optimization (default: 200)')
    parser.add_argument('--fast-ocr', action='store_true', default=True,
                       help='Use fast OCR mode for smaller file size (default: True)')
    parser.add_argument('--accurate-ocr', action='store_true',
                       help='Use accurate OCR mode (larger file size, slower)')
    parser.add_argument('-j', '--jobs', type=int, default=12,
                       help='Number of parallel OCR jobs (default: 12)')
    
    args = parser.parse_args()
    
    input_folder = Path(args.input_folder)
    output_pdf = Path(args.output_pdf)
    
    # Validate input
    if not input_folder.exists():
        log(f"ERROR: Input folder does not exist: {input_folder}")
        return 1
    
    if not input_folder.is_dir():
        log(f"ERROR: Input path is not a directory: {input_folder}")
        return 1
    
    # Create output directory if needed
    output_pdf.parent.mkdir(parents=True, exist_ok=True)
    
    ocr_mode_desc = "accurate OCR (slower, larger)" if args.accurate_ocr else "fast OCR (smaller, faster)"
    log("=== FINAL WORKFLOW ===")
    log("1. Combine TIFF/JPEG/PDF files -> Single PDF")
    log(f"2. OCRmyPDF: Add text layer with deskewing & rotation ({ocr_mode_desc})")
    log("3. JBIG2 optimization (preserves OCR)")
    log("")
    
    # Create temporary directory for intermediate files
    with tempfile.TemporaryDirectory(prefix="final_workflow_") as temp_dir:
        temp_path = Path(temp_dir)
        
        # Step 1: Combine images to PDF
        base_pdf = temp_path / "01_combined.pdf"
        if not combine_files_to_pdf(input_folder, base_pdf):
            return 1
        
        # Step 2: Run OCRmyPDF first (on uncompressed images for better preservation)
        ocr_pdf = temp_path / "02_ocr.pdf"
        fast_mode = not args.accurate_ocr  # Use fast mode unless --accurate-ocr specified
        # Pass args to OCR function to access job count
        if not run_ocr(base_pdf, ocr_pdf, fast_mode=fast_mode, args=args):
            return 1
        
        # Step 3: Extract OCR, do JBIG2 rebuild, then re-inject OCR
        if not extract_compress_reinject_ocr(ocr_pdf, output_pdf, temp_path):
            return 1
    
    # Final summary
    final_size = get_size_mb(output_pdf)
    log("")
    log("=== WORKFLOW COMPLETE ===")
    log(f"SUCCESS: Final result: {final_size:.2f} MB")
    log(f"Output: {output_pdf}")
    log("")
    ocr_quality = "accurate" if args.accurate_ocr else "fast/compact"
    log("The PDF now includes:")
    log(f"  * OCR text layer (searchable, {ocr_quality} mode)")
    log("  * Deskewed and rotated pages")
    log("  * In-place optimization (preserves OCR)")
    
    return 0

def extract_compress_reinject_ocr(ocr_pdf, output_pdf, temp_path):
    # extract OCR, rebuild with jbig2, then put OCR back
    
    # extract OCR text
    ocr_text_file = temp_path / "extracted_text.txt"
    log("Extracting OCR text layer...")
    
    try:
        import fitz
        doc = fitz.open(ocr_pdf)
        all_text = []
        
        for page_num in range(doc.page_count):
            page = doc[page_num]
            text = page.get_text()
            all_text.append(f"=== PAGE {page_num + 1} ===\n{text}\n")
        
        doc.close()
        
        # Save extracted text
        with open(ocr_text_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(all_text))
        
        log(f"Extracted text from {len(all_text)} pages")
        
    except Exception as e:
        log(f"ERROR: Failed to extract OCR text: {e}")
        return False
    
    # strip text and compress with JBIG2
    images_only_pdf = temp_path / "03_images_only.pdf"
    compressed_pdf = temp_path / "04_compressed.pdf"
    
    log("Creating image-only PDF...")
    try:
        # strip text from PDF
        doc = fitz.open(ocr_pdf)
        img_doc = fitz.open()
        
        for page_num in range(doc.page_count):
            page = doc[page_num]
            # copy page without text layer
            img_page = img_doc.new_page(width=page.rect.width, height=page.rect.height)
            
            # copy images only
            for img in page.get_images():
                xref = img[0]
                base_image = doc.extract_image(xref)
                image_data = base_image["image"]
                image_rects = page.get_image_rects(xref)
                if image_rects:
                    rect = image_rects[0]
                    img_page.insert_image(rect, stream=image_data)
        
        doc.close()
        img_doc.save(images_only_pdf)
        img_doc.close()
        
        log("Created image-only PDF")
        
    except Exception as e:
        log(f"ERROR: Failed to create image-only PDF: {e}")
        return False
    
    # apply JBIG2 compression
    log("Applying JBIG2 compression...")
    if not run_jbig2_opt(images_only_pdf, compressed_pdf, preserve_ocr=False):
        return False
    
    # re-inject OCR text
    log("Re-injecting OCR text layer...")
    
    cmd = [
        sys.executable, '-m', 'ocrmypdf',
        '--force-ocr', '--optimize', '0',
        '--tesseract-timeout', '30.0',
        '-l', 'eng',
        '--output-type', 'pdf',
        '-j', '12',
        str(compressed_pdf),
        str(output_pdf)
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        log("ERROR: Failed to re-inject OCR text!")
        log(f"Error: {result.stderr}")
        # fallback: use compressed version without OCR
        import shutil
        shutil.copy2(compressed_pdf, output_pdf)
        log("Using compressed version without OCR as fallback")
    else:
        log("Successfully re-injected OCR text layer")
    
    size_mb = get_size_mb(output_pdf)
    log(f"Final optimization done: {size_mb:.2f} MB")
    return True

if __name__ == "__main__":
    sys.exit(main())