#!/usr/bin/env python3
"""
resize_compress.py

Resizes and compresses images.
- UNC/mapped network paths processed sequentially (single core).
- Local drives processed in parallel using all CPU cores.
- Resizes so the longest side is 1280px (override with --max-side).
- Saves as JPEG with quality 65 (override with --jpeg-quality).
- Preserves EXIF data and ICC profiles when present.
Usage: Drop an image folder onto the accompanying batch file, or run:
    python resize_compress.py <folder> [--max-side N] [--jpeg-quality Q]
"""
import os
import sys
import time
import argparse
import ctypes
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, as_completed
from PIL import Image, ImageOps

# Optional HEIC/HEIF support
try:
    import pillow_heif  # type: ignore
    pillow_heif.register_heif_opener()
except Exception:
    pass

# Defaults (can be overridden by CLI flags)
DEFAULT_MAX_SIDE = 1280
DEFAULT_JPEG_QUALITY = 65


def is_network_path(path: Path) -> bool:
    r"""Return True for UNC (\\\\server\\share) and mapped network drives on Windows."""
    try:
        s = str(path)
        # UNC path
        if s.startswith('\\\\'):
            return True
        # Drive-letter path: check drive type
        drive = path.drive
        if not drive and len(s) >= 2 and s[1] == ':':
            drive = s[:2]
        if not drive:
            return False
        # On Windows, use GetDriveTypeW. DRIVE_REMOTE == 4
        DRIVE_REMOTE = 4
        t = ctypes.windll.kernel32.GetDriveTypeW(f"{drive}\\")  # type: ignore[attr-defined]
        return t == DRIVE_REMOTE
    except Exception:
        # Non-Windows or any failure → assume not network
        return False


def process_image(input_path: Path, output_path: Path, max_side: int, jpeg_quality: int) -> str:
    """Open, resize, and compress a single image, preserving EXIF + ICC. Converts alpha to RGB."""
    try:
        with Image.open(input_path) as img:
            exif_data = img.info.get('exif', b'')
            icc_profile = img.info.get('icc_profile')
            img = ImageOps.exif_transpose(img)

            # Handle alpha/palette
            if img.mode in ("RGBA", "LA", "P"):
                img = img.convert("RGB")

            w, h = img.size
            ratio = max_side / max(w, h)
            if ratio < 1:
                img = img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)

            output_path.parent.mkdir(parents=True, exist_ok=True)
            save_kwargs = dict(format="JPEG", quality=jpeg_quality, optimize=True)
            if exif_data:
                save_kwargs["exif"] = exif_data
            if icc_profile:
                save_kwargs["icc_profile"] = icc_profile
            img.save(output_path, **save_kwargs)
        return f"[OK] {input_path.name} -> {output_path.name}"
    except Exception as e:
        return f"[ERR] {input_path.name}: {e}"


def main():
    parser = argparse.ArgumentParser(description="Resize and compress images in a folder.")
    parser.add_argument("input_dir", help="Folder containing images to process")
    parser.add_argument("--max-side", type=int, default=DEFAULT_MAX_SIDE, dest="max_side",
                        help="Longest side target in pixels (default: %(default)s)")
    parser.add_argument("--jpeg-quality", type=int, default=DEFAULT_JPEG_QUALITY, dest="jpeg_quality",
                        help="JPEG quality 0-100 (default: %(default)s)")
    args = parser.parse_args()

    input_dir = Path(args.input_dir).resolve()
    if not input_dir.exists() or not input_dir.is_dir():
        print(f"Error: input folder not found: {input_dir}")
        sys.exit(1)

    output_dir = input_dir / "compressed"

    exts = (".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp", ".heic", ".heif", ".bmp")
    files = [p for p in input_dir.iterdir() if p.suffix.lower() in exts and p.is_file()]
    if not files:
        print(f"No images found in: {input_dir}")
        sys.exit(0)

    smb_mode = is_network_path(input_dir)
    start = time.perf_counter()

    if smb_mode:
        print(f"Mode: Network path detected. Processing sequentially in: {input_dir}")
        for p in files:
            out = output_dir / f"{p.stem}.jpg"
            print(process_image(p, out, args.max_side, args.jpeg_quality))
    else:
        cores = os.cpu_count() or 1
        print(f"Mode: Local drive. Processing in parallel with {cores} cores in: {input_dir}")
        tasks = [(p, output_dir / f"{p.stem}.jpg") for p in files]
        with ProcessPoolExecutor(max_workers=cores) as executor:
            futures = [executor.submit(process_image, inp, out, args.max_side, args.jpeg_quality)
                       for inp, out in tasks]
            for future in as_completed(futures):
                print(future.result())

    elapsed = time.perf_counter() - start
    print(f"Total elapsed time: {elapsed:.2f} seconds")


if __name__ == '__main__':
    main()
