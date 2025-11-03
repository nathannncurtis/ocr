#!/usr/bin/env python3
"""
batch_process.py - Batch PDF processing script

Processes multiple folders in parallel, converting each to an OCR'd PDF.

Usage: python batch_process.py <input_dir> <output_dir> [options]
"""

import os
import sys
import argparse
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
import subprocess
import time

def log(msg):
    timestamp = time.strftime("%H:%M:%S")
    print(f"[{timestamp}] {msg}", flush=True)

def process_folder(folder_path, output_dir, args):
    """Process a single folder using FINAL.py"""
    folder_name = folder_path.name
    output_pdf = output_dir / f"{folder_name}.pdf"

    log(f"Starting: {folder_name}")

    # Build command for FINAL.py
    script_dir = Path(__file__).parent
    final_script = script_dir / "FINAL.py"

    cmd = [
        sys.executable, str(final_script),
        str(folder_path),
        str(output_pdf),
        '-j', str(args.jobs_per_folder)
    ]

    if args.accurate_ocr:
        cmd.append('--accurate-ocr')

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=args.timeout)

        if result.returncode == 0:
            # Get file size
            size_mb = output_pdf.stat().st_size / (1024 * 1024)
            log(f"SUCCESS: {folder_name} -> {size_mb:.2f} MB")
            return {'folder': folder_name, 'status': 'success', 'size_mb': size_mb}
        else:
            log(f"FAILED: {folder_name} (exit code: {result.returncode})")

            # Save full output to log files for debugging
            error_log = output_dir / f"{folder_name}_error.log"
            with open(error_log, 'w', encoding='utf-8') as f:
                f.write(f"=== COMMAND ===\n")
                f.write(' '.join(cmd) + '\n\n')
                f.write(f"=== EXIT CODE ===\n{result.returncode}\n\n")
                f.write(f"=== STDOUT ===\n{result.stdout}\n\n")
                f.write(f"=== STDERR ===\n{result.stderr}\n")

            log(f"Full error log saved to: {error_log}")

            # Print summary
            if result.stderr:
                log(f"STDERR: {result.stderr[:500]}")
            if result.stdout:
                log(f"STDOUT (last 500 chars): ...{result.stdout[-500:]}")

            error_msg = result.stderr[:500] if result.stderr else result.stdout[:500]
            return {'folder': folder_name, 'status': 'failed', 'error': error_msg, 'log': str(error_log)}

    except subprocess.TimeoutExpired:
        log(f"TIMEOUT: {folder_name} (exceeded {args.timeout}s)")
        return {'folder': folder_name, 'status': 'timeout'}
    except Exception as e:
        log(f"ERROR: {folder_name} - {str(e)}")
        return {'folder': folder_name, 'status': 'error', 'error': str(e)}

def find_folders(input_dir):
    """Find all subdirectories in input_dir that contain images or PDFs"""
    input_path = Path(input_dir)
    folders = []

    # Ignore system files
    ignore_files = {'thumbs.db', 'desktop.ini', '.ds_store'}

    for item in sorted(input_path.iterdir()):
        if item.is_dir():
            # Check if folder contains any processable files (excluding system files)
            def has_valid_files(pattern):
                return any(f for f in item.glob(pattern) if f.name.lower() not in ignore_files)

            has_files = (
                has_valid_files("*.tif") or
                has_valid_files("*.tiff") or
                has_valid_files("*.jpg") or
                has_valid_files("*.jpeg") or
                has_valid_files("*.pdf")
            )
            if has_files:
                folders.append(item)

    return folders

def main():
    parser = argparse.ArgumentParser(
        description="Batch process multiple folders of images/PDFs into OCR'd PDFs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process with 4 folders in parallel, 12 jobs each (48 cores total)
  python batch_process.py /input /output -p 4 -j 12

  # Process with 6 folders in parallel, 8 jobs each (48 cores total)
  python batch_process.py /input /output -p 6 -j 8

  # Single folder at a time, max parallelism within folder
  python batch_process.py /input /output -p 1 -j 48
        """
    )

    parser.add_argument('input_dir', help='Input directory containing subfolders to process')
    parser.add_argument('output_dir', help='Output directory for processed PDFs')
    parser.add_argument('-p', '--parallel', type=int, default=4,
                       help='Number of folders to process in parallel (default: 4)')
    parser.add_argument('-j', '--jobs-per-folder', type=int, default=12,
                       help='Number of OCR jobs per folder (default: 12)')
    parser.add_argument('--accurate-ocr', action='store_true',
                       help='Use accurate OCR mode (slower, larger files)')
    parser.add_argument('--timeout', type=int, default=3600,
                       help='Timeout per folder in seconds (default: 3600 = 1 hour)')
    parser.add_argument('--dry-run', action='store_true',
                       help='List folders that would be processed without actually processing')

    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    output_dir = Path(args.output_dir)

    # Validate input
    if not input_dir.exists():
        log(f"ERROR: Input directory does not exist: {input_dir}")
        return 1

    if not input_dir.is_dir():
        log(f"ERROR: Input path is not a directory: {input_dir}")
        return 1

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    # Find all folders to process
    folders = find_folders(input_dir)

    if not folders:
        log("ERROR: No folders with processable files found")
        return 1

    log("=" * 60)
    log("BATCH OCR PROCESSING")
    log("=" * 60)
    log(f"Input directory: {input_dir}")
    log(f"Output directory: {output_dir}")
    log(f"Folders found: {len(folders)}")
    log(f"Parallel folders: {args.parallel}")
    log(f"Jobs per folder: {args.jobs_per_folder}")
    log(f"Total cores used: {args.parallel * args.jobs_per_folder}")
    log(f"OCR mode: {'accurate' if args.accurate_ocr else 'fast'}")
    log("=" * 60)

    if args.dry_run:
        log("\nDRY RUN - Folders that would be processed:")
        for folder in folders:
            log(f"  - {folder.name}")
        return 0

    # Process folders in parallel
    results = []
    completed = 0
    total = len(folders)

    log(f"\nStarting processing of {total} folders...")
    start_time = time.time()

    with ProcessPoolExecutor(max_workers=args.parallel) as executor:
        # Submit all jobs
        future_to_folder = {
            executor.submit(process_folder, folder, output_dir, args): folder
            for folder in folders
        }

        # Process results as they complete
        for future in as_completed(future_to_folder):
            completed += 1
            result = future.result()
            results.append(result)

            log(f"Progress: {completed}/{total} folders completed")

    # Summary
    elapsed = time.time() - start_time
    elapsed_mins = elapsed / 60

    log("\n" + "=" * 60)
    log("PROCESSING COMPLETE")
    log("=" * 60)
    log(f"Total time: {elapsed_mins:.1f} minutes ({elapsed:.0f} seconds)")
    log(f"Average: {elapsed/total:.1f} seconds per folder")

    # Count successes/failures
    success_count = sum(1 for r in results if r['status'] == 'success')
    failed_count = sum(1 for r in results if r['status'] == 'failed')
    timeout_count = sum(1 for r in results if r['status'] == 'timeout')
    error_count = sum(1 for r in results if r['status'] == 'error')

    log(f"\nResults:")
    log(f"  Success: {success_count}")
    log(f"  Failed: {failed_count}")
    log(f"  Timeout: {timeout_count}")
    log(f"  Error: {error_count}")

    # Total size
    total_size = sum(r.get('size_mb', 0) for r in results if r['status'] == 'success')
    log(f"\nTotal output size: {total_size:.2f} MB")

    # List failures
    if failed_count + timeout_count + error_count > 0:
        log("\nFailed folders:")
        for r in results:
            if r['status'] != 'success':
                if 'log' in r:
                    log(f"  - {r['folder']}: {r['status']} (see {r['log']})")
                else:
                    log(f"  - {r['folder']}: {r['status']}")

    log("=" * 60)

    return 0 if failed_count + timeout_count + error_count == 0 else 1

if __name__ == "__main__":
    sys.exit(main())
