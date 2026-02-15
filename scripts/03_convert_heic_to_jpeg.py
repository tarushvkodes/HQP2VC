import argparse, csv
from pathlib import Path
from PIL import Image
import pillow_heif

pillow_heif.register_heif_opener()
HEIC_EXTS = {'.heic', '.heif'}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--log', required=True)
    args = ap.parse_args()

    root = Path(args.root)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    files = [p for p in root.rglob('*') if p.suffix.lower() in HEIC_EXTS]

    with open(args.log, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['src', 'dst', 'status', 'error'])
        for p in files:
            rel = p.relative_to(root)
            dst = out / rel.with_suffix('.jpg')
            dst.parent.mkdir(parents=True, exist_ok=True)
            if dst.exists():
                w.writerow([str(p), str(dst), 'skip_exists', ''])
                continue
            try:
                im = Image.open(p)
                im = im.convert('RGB')
                im.save(dst, format='JPEG', quality=95, subsampling=0)
                w.writerow([str(p), str(dst), 'ok', ''])
            except Exception as e:
                w.writerow([str(p), str(dst), 'fail', str(e)])


if __name__ == '__main__':
    main()
