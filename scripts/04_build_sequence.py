import argparse, json
from pathlib import Path

JPG_EXTS = {'.jpg', '.jpeg'}
RAW_EXTS = {'.cr2','.cr3','.nef','.arw','.dng','.orf','.rw2','.raf','.pef','.srw'}


def key_of(p: Path):
    return p.stem.lower()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', required=True)
    ap.add_argument('--raw-jpeg-root', required=True)
    ap.add_argument('--heic-jpeg-root', required=True)
    ap.add_argument('--out-seq', required=True)
    args = ap.parse_args()

    root = Path(args.root)
    raw_jpeg_root = Path(args.raw_jpeg_root)
    heic_jpeg_root = Path(args.heic_jpeg_root)

    src_jpgs = [p for p in root.rglob('*') if p.suffix.lower() in JPG_EXTS]
    src_raws = [p for p in root.rglob('*') if p.suffix.lower() in RAW_EXTS]
    heic_jpgs = [p for p in heic_jpeg_root.rglob('*.jpg')]

    raw_rendered = {key_of(p): p for p in raw_jpeg_root.rglob('*.jpg')}
    jpg_map = {}
    for j in src_jpgs:
        jpg_map.setdefault(key_of(j), []).append(j)

    sequence = []

    # Pair JPG then RAW-rendered JPEG where possible.
    # IMPORTANT: emit each JPEG immediately followed by its paired RAW
    # so pairs stay adjacent (never batch all JPEGs then all RAWs).
    for k in sorted(jpg_map.keys()):
        jpegs = sorted(jpg_map[k])
        raw = raw_rendered.get(k)
        if raw and jpegs:
            # First JPEG pairs with the RAW — emit them adjacent
            sequence.append(str(jpegs[0].resolve()))
            sequence.append(str(raw.resolve()))
            # Remaining JPEGs for this stem (no RAW mate available)
            for j in jpegs[1:]:
                sequence.append(str(j.resolve()))
        else:
            for j in jpegs:
                sequence.append(str(j.resolve()))

    # Append rendered RAWs that did not find JPG mate
    jpg_keys = set(jpg_map.keys())
    for k, p in sorted(raw_rendered.items()):
        if k not in jpg_keys:
            sequence.append(str(p.resolve()))

    # Append HEIC-derived JPEGs
    for p in sorted(heic_jpgs):
        sequence.append(str(p.resolve()))

    out_path = Path(args.out_seq)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps({"sequence": sequence, "count": len(sequence)}, indent=2), encoding='utf-8')
    print(f'SEQUENCE_COUNT={len(sequence)}')


if __name__ == '__main__':
    main()
