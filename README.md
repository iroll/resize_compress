# resize_compress
A simple script to batch resize and compress images. Optimizes speed based on local or network source.

Usage: Drop an image folder onto the accompanying batch file, or run:
python resize_compress.py <folder> [--max-side N] [--jpeg-quality Q]
    
- UNC/mapped network paths processed sequentially (single core).
- Local drives processed in parallel using all CPU cores.
- Resizes so the longest side is 1280px (override with --max-side).
- Saves as JPEG with quality 65 (override with --jpeg-quality).
- Preserves EXIF data and ICC profiles when present.
