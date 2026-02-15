import argparse
import json
import logging
from pathlib import Path
from datetime import datetime
from collections import defaultdict

import exifread
from PIL import Image, ImageOps

logging.getLogger('exifread').setLevel(logging.ERROR)

JPEG_EXTS = {'.jpg', '.jpeg'}
HEIC_EXTS = {'.heic', '.heif'}
RAW_EXTS = {'.cr2', '.cr3', '.nef', '.arw', '.dng', '.orf', '.rw2', '.raf', '.pef', '.srw'}
OTHER_IMAGE_EXTS = {'.png', '.tif', '.tiff', '.webp'}


def parse_dt(s: str):
    s = str(s).strip()
    for fmt in ("%Y:%m:%d %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(s, fmt)
        except Exception:
            pass
    return None


def exif_datetime(path: Path):
    try:
        with path.open('rb') as f:
            tags = exifread.process_file(f, details=False, stop_tag='EXIF DateTimeOriginal')
        for k in ('EXIF DateTimeOriginal', 'EXIF DateTimeDigitized', 'Image DateTime'):
            if k in tags:
                dt = parse_dt(tags[k])
                if dt:
                    return dt
    except Exception:
        pass
    return datetime.fromtimestamp(path.stat().st_mtime)


def exif_orientation_degrees(path: Path):
    try:
        with path.open('rb') as f:
            tags = exifread.process_file(f, details=False, stop_tag='Image Orientation')
        v = str(tags.get('Image Orientation', '')).lower()
        if '90' in v and 'cw' in v:
            return 90
        if '90' in v and 'ccw' in v:
            return 270
        if '180' in v:
            return 180
        if 'mirror' in v:
            return 0
        if 'normal' in v:
            return 0
    except Exception:
        pass
    return 0


def rel_key(root: Path, p: Path):
    rel = p.relative_to(root)
    return str(rel.parent).lower() + '|' + rel.stem.lower()


def normalize_image(src: Path, out: Path, rotate_deg: int = 0):
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists() and out.stat().st_size > 0:
        return
    tmp = out.with_suffix('.tmp.jpg')
    with Image.open(src) as im:
        im = ImageOps.exif_transpose(im)
        if rotate_deg % 360 != 0:
            im = im.rotate(-rotate_deg, expand=True)
        if im.mode not in ('RGB', 'L'):
            im = im.convert('RGB')
        elif im.mode == 'L':
            im = im.convert('RGB')
        im.save(tmp, format='JPEG', quality=95, subsampling=0)
    tmp.replace(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', required=True)
    ap.add_argument('--raw-jpeg-root', required=True)
    ap.add_argument('--heic-jpeg-root', required=True)
    ap.add_argument('--normalized-out', required=True)
    ap.add_argument('--sequence-out', required=True)
    ap.add_argument('--audit-out', required=True)
    args = ap.parse_args()

    root = Path(args.root)
    raw_jpeg_root = Path(args.raw_jpeg_root)
    heic_jpeg_root = Path(args.heic_jpeg_root)
    normalized_out = Path(args.normalized_out)

    originals = []
    for p in root.rglob('*'):
        if not p.is_file():
            continue
        rel = p.relative_to(root)
        if rel.parts and str(rel.parts[0]).startswith('_'):
            continue
        ext = p.suffix.lower()
        if ext in JPEG_EXTS | HEIC_EXTS | RAW_EXTS | OTHER_IMAGE_EXTS:
            originals.append(p)

    by_key = defaultdict(lambda: {'jpeg': [], 'raw': [], 'heic': [], 'other': []})

    for p in originals:
        ext = p.suffix.lower()
        dt = exif_datetime(p)
        odeg = exif_orientation_degrees(p)
        item = {'orig': p, 'dt': dt, 'odeg': odeg}
        k = rel_key(root, p)

        if ext in JPEG_EXTS:
            item['frame'] = p
            by_key[k]['jpeg'].append(item)
        elif ext in RAW_EXTS:
            rel = p.relative_to(root)
            frame = raw_jpeg_root / rel.with_suffix('.jpg')
            if frame.exists():
                item['frame'] = frame
                by_key[k]['raw'].append(item)
        elif ext in HEIC_EXTS:
            rel = p.relative_to(root)
            frame = heic_jpeg_root / rel.with_suffix('.jpg')
            if frame.exists():
                item['frame'] = frame
                by_key[k]['heic'].append(item)
        elif ext in OTHER_IMAGE_EXTS:
            item['frame'] = p
            by_key[k]['other'].append(item)

    events = []

    for k, buckets in by_key.items():
        j = sorted(buckets['jpeg'], key=lambda x: (x['dt'], str(x['orig'])))
        r = sorted(buckets['raw'], key=lambda x: (x['dt'], str(x['orig'])))
        h = sorted(buckets['heic'], key=lambda x: (x['dt'], str(x['orig'])))
        o = sorted(buckets['other'], key=lambda x: (x['dt'], str(x['orig'])))

        m = min(len(j), len(r))
        for i in range(m):
            jj, rr = j[i], r[i]
            evt_dt = min(jj['dt'], rr['dt'])
            rotate_raw = (jj['odeg'] - rr['odeg']) % 360
            events.append({
                'dt': evt_dt,
                'kind': 'pair',
                'key': k,
                'items': [
                    {'role': 'jpeg', 'src': str(jj['frame']), 'rotate': 0, 'orig': str(jj['orig'])},
                    {'role': 'raw', 'src': str(rr['frame']), 'rotate': rotate_raw, 'orig': str(rr['orig'])},
                ]
            })

        for x in j[m:]:
            events.append({'dt': x['dt'], 'kind': 'jpeg_single', 'key': k, 'items': [{'role': 'jpeg', 'src': str(x['frame']), 'rotate': 0, 'orig': str(x['orig'])}]})
        for x in r[m:]:
            events.append({'dt': x['dt'], 'kind': 'raw_single', 'key': k, 'items': [{'role': 'raw', 'src': str(x['frame']), 'rotate': 0, 'orig': str(x['orig'])}]})
        for x in h:
            events.append({'dt': x['dt'], 'kind': 'heic_single', 'key': k, 'items': [{'role': 'heic', 'src': str(x['frame']), 'rotate': 0, 'orig': str(x['orig'])}]})
        for x in o:
            events.append({'dt': x['dt'], 'kind': 'other_single', 'key': k, 'items': [{'role': 'other', 'src': str(x['frame']), 'rotate': 0, 'orig': str(x['orig'])}]})

    events.sort(key=lambda e: (e['dt'], e['key'], e['kind']))

    sequence = []
    audit_rows = []
    idx = 0
    for ev_i, ev in enumerate(events):
        for it_i, it in enumerate(ev['items']):
            src = Path(it['src'])
            out = normalized_out / f"{idx:06d}_{it['role']}.jpg"
            normalize_image(src, out, rotate_deg=it['rotate'])
            sequence.append(str(out.resolve()))
            audit_rows.append({
                'index': idx,
                'event_index': ev_i,
                'datetime': ev['dt'].strftime('%Y-%m-%d %H:%M:%S'),
                'event_kind': ev['kind'],
                'role': it['role'],
                'source': it['src'],
                'original': it['orig'],
                'rotate_applied_deg': it['rotate'],
                'normalized': str(out.resolve()),
            })
            idx += 1

    seq_out = Path(args.sequence_out)
    seq_out.parent.mkdir(parents=True, exist_ok=True)
    seq_out.write_text(json.dumps({'count': len(sequence), 'sequence': sequence}, indent=2), encoding='utf-8')

    aud_out = Path(args.audit_out)
    aud_out.parent.mkdir(parents=True, exist_ok=True)
    aud_out.write_text(json.dumps({'rows': audit_rows}, indent=2), encoding='utf-8')

    print(f"EVENTS={len(events)} FRAMES={len(sequence)}")


if __name__ == '__main__':
    main()
