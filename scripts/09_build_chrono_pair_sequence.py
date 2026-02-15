import argparse
import csv
import json
import logging
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import exifread
from PIL import Image, ImageChops, ImageOps, ImageStat

logging.getLogger('exifread').setLevel(logging.ERROR)

JPEG_EXTS = {'.jpg', '.jpeg'}
HEIC_EXTS = {'.heic', '.heif'}
RAW_EXTS = {'.cr2', '.cr3', '.nef', '.arw', '.dng', '.orf', '.rw2', '.raf', '.pef', '.srw'}


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
            tags = exifread.process_file(f, details=False)
        for k in ('EXIF DateTimeOriginal', 'EXIF DateTimeDigitized', 'Image DateTime'):
            if k in tags:
                dt = parse_dt(tags[k])
                if dt:
                    return dt
    except Exception:
        pass
    return datetime.fromtimestamp(path.stat().st_mtime)


def norm_key(root: Path, p: Path):
    rel = p.relative_to(root)
    return f"{str(rel.parent).lower()}|{p.stem.lower()}"


def load_map_csv(path: Path):
    m = {}
    if not path.exists():
        return m
    with path.open('r', encoding='utf-8', errors='ignore', newline='') as f:
        r = csv.DictReader(f)
        for row in r:
            if (row.get('status') or '').lower() != 'ok':
                continue
            src = row.get('source')
            out = row.get('output')
            if src and out:
                m[str(Path(src))] = str(Path(out))
    return m


def prep_img(path: Path):
    with Image.open(path) as im:
        im = ImageOps.exif_transpose(im).convert('RGB')
        return im.copy()


def match_rotation_deg(jpeg_path: Path, raw_path: Path):
    j = prep_img(jpeg_path)
    r = prep_img(raw_path)
    j_small = ImageOps.fit(j, (256, 256), method=Image.Resampling.BICUBIC)

    best = None
    for deg in (0, 90, 180, 270):
        rr = r.rotate(deg, expand=True)
        rr_small = ImageOps.fit(rr, (256, 256), method=Image.Resampling.BICUBIC)
        diff = ImageChops.difference(j_small, rr_small)
        score = sum(ImageStat.Stat(diff).mean)  # lower is better
        if best is None or score < best[0]:
            best = (score, deg)
    return best[1]


def save_normalized(src: Path, out: Path, ccw_deg: int):
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix('.tmp.jpg')
    with Image.open(src) as im:
        im = ImageOps.exif_transpose(im).convert('RGB')
        if ccw_deg % 360:
            im = im.rotate(ccw_deg, expand=True)
        im.save(tmp, format='JPEG', quality=95, subsampling=0)
    tmp.replace(out)


def pair_lists(jpegs, raws):
    # pair by nearest timestamp within same key bucket
    used = set()
    pairs = []
    for j in jpegs:
        best_i = None
        best_dt = None
        for i, r in enumerate(raws):
            if i in used:
                continue
            delta = abs((j['dt'] - r['dt']).total_seconds())
            if best_dt is None or delta < best_dt:
                best_dt = delta
                best_i = i
        if best_i is not None:
            used.add(best_i)
            pairs.append((j, raws[best_i]))
    raw_un = [r for i, r in enumerate(raws) if i not in used]
    j_un = [j for j in jpegs if all(j is not p[0] for p in pairs)]
    return pairs, j_un, raw_un


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', required=True)
    ap.add_argument('--raw-jpeg-root', required=True)
    ap.add_argument('--heic-jpeg-root', required=True)
    ap.add_argument('--normalized-out', required=True)
    ap.add_argument('--sequence-out', required=True)
    ap.add_argument('--audit-out', required=True)
    ap.add_argument('--raw-log', default='')
    ap.add_argument('--heic-log', default='')
    args = ap.parse_args()

    root = Path(args.root)
    normalized_out = Path(args.normalized_out)
    normalized_out.mkdir(parents=True, exist_ok=True)

    raw_log = Path(args.raw_log) if args.raw_log else Path(args.raw_jpeg_root) / 'rawpy_render_log_bright_resume.csv'
    heic_log = Path(args.heic_log) if args.heic_log else Path(args.heic_jpeg_root) / 'heic_render_log_pillow.csv'

    raw_map = load_map_csv(raw_log)
    heic_map = load_map_csv(heic_log)

    buckets = defaultdict(lambda: {'jpeg': [], 'raw': [], 'heic': []})

    for p in root.rglob('*'):
        if not p.is_file():
            continue
        rel = p.relative_to(root)
        if rel.parts and str(rel.parts[0]).startswith('_'):
            continue
        ext = p.suffix.lower()
        k = norm_key(root, p)
        dt = exif_datetime(p)

        if ext in JPEG_EXTS:
            buckets[k]['jpeg'].append({'orig': p, 'src': p, 'dt': dt})
        elif ext in RAW_EXTS:
            out = raw_map.get(str(p))
            if out and Path(out).exists():
                buckets[k]['raw'].append({'orig': p, 'src': Path(out), 'dt': dt})
        elif ext in HEIC_EXTS:
            out = heic_map.get(str(p))
            if out and Path(out).exists():
                buckets[k]['heic'].append({'orig': p, 'src': Path(out), 'dt': dt})

    events = []

    for k, b in buckets.items():
        j = sorted(b['jpeg'], key=lambda x: (x['dt'], str(x['orig'])))
        r = sorted(b['raw'], key=lambda x: (x['dt'], str(x['orig'])))
        h = sorted(b['heic'], key=lambda x: (x['dt'], str(x['orig'])))

        pairs, j_un, r_un = pair_lists(j, r)

        for jj, rr in pairs:
            # Determine RAW correction so it matches JPEG orientation/content
            raw_match_rot = match_rotation_deg(jj['src'], rr['src'])

            # Enforce user policy: vertical should be turned left (CCW 90)
            with Image.open(jj['src']) as t:
                t = ImageOps.exif_transpose(t)
                jpeg_vertical = t.height > t.width
            jpeg_final_rot = 90 if jpeg_vertical else 0
            raw_final_rot = (raw_match_rot + jpeg_final_rot) % 360

            events.append({
                'dt': min(jj['dt'], rr['dt']),
                'kind': 'pair',
                'key': k,
                'items': [
                    {'role': 'jpeg', 'src': str(jj['src']), 'orig': str(jj['orig']), 'rot': jpeg_final_rot},
                    {'role': 'raw', 'src': str(rr['src']), 'orig': str(rr['orig']), 'rot': raw_final_rot},
                ]
            })

        for x in j_un:
            with Image.open(x['src']) as t:
                t = ImageOps.exif_transpose(t)
                rot = 90 if t.height > t.width else 0
            events.append({'dt': x['dt'], 'kind': 'jpeg_single', 'key': k,
                           'items': [{'role': 'jpeg', 'src': str(x['src']), 'orig': str(x['orig']), 'rot': rot}]})

        for x in r_un:
            with Image.open(x['src']) as t:
                t = ImageOps.exif_transpose(t)
                rot = 90 if t.height > t.width else 0
            events.append({'dt': x['dt'], 'kind': 'raw_single', 'key': k,
                           'items': [{'role': 'raw', 'src': str(x['src']), 'orig': str(x['orig']), 'rot': rot}]})

        for x in h:
            with Image.open(x['src']) as t:
                t = ImageOps.exif_transpose(t)
                rot = 90 if t.height > t.width else 0
            events.append({'dt': x['dt'], 'kind': 'heic_single', 'key': k,
                           'items': [{'role': 'heic', 'src': str(x['src']), 'orig': str(x['orig']), 'rot': rot}]})

    events.sort(key=lambda e: (e['dt'], e['key'], e['kind']))

    sequence = []
    audit = []
    idx = 0
    for ei, ev in enumerate(events):
        for it in ev['items']:
            out = normalized_out / f"{idx:06d}_{it['role']}.jpg"
            save_normalized(Path(it['src']), out, ccw_deg=it['rot'])
            sequence.append(str(out.resolve()))
            audit.append({
                'index': idx,
                'event_index': ei,
                'datetime': ev['dt'].strftime('%Y-%m-%d %H:%M:%S'),
                'event_kind': ev['kind'],
                'role': it['role'],
                'source': it['src'],
                'original': it['orig'],
                'rotate_ccw_deg': it['rot'],
                'normalized': str(out.resolve()),
            })
            idx += 1

    seq_out = Path(args.sequence_out)
    seq_out.parent.mkdir(parents=True, exist_ok=True)
    seq_out.write_text(json.dumps({'count': len(sequence), 'sequence': sequence}, indent=2), encoding='utf-8')

    aud_out = Path(args.audit_out)
    aud_out.parent.mkdir(parents=True, exist_ok=True)
    aud_out.write_text(json.dumps({'rows': audit}, indent=2), encoding='utf-8')

    print(f"EVENTS={len(events)} FRAMES={len(sequence)}")


if __name__ == '__main__':
    main()
