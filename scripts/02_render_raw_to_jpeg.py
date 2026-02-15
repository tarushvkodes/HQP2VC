import argparse, csv
from pathlib import Path
import rawpy, imageio.v3 as iio

RAW_EXTS = {'.cr2','.cr3','.nef','.arw','.dng','.orf','.rw2','.raf','.pef','.srw'}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--log', required=True)
    args = ap.parse_args()

    root = Path(args.root)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    raws = [p for p in root.rglob('*') if p.suffix.lower() in RAW_EXTS]

    with open(args.log, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['src','dst','status','error'])
        for p in raws:
            rel = p.relative_to(root)
            dst = out / rel.with_suffix('.jpg')
            dst.parent.mkdir(parents=True, exist_ok=True)
            if dst.exists():
                w.writerow([str(p), str(dst), 'skip_exists', ''])
                continue
            try:
                with rawpy.imread(str(p)) as raw:
                    rgb = raw.postprocess(
                        use_camera_wb=True,
                        no_auto_bright=False,
                        output_bps=8,
                        bright=1.2
                    )
                iio.imwrite(dst, rgb, quality=95)
                w.writerow([str(p), str(dst), 'ok', ''])
            except Exception as e:
                w.writerow([str(p), str(dst), 'fail', str(e)])

if __name__ == '__main__':
    main()
