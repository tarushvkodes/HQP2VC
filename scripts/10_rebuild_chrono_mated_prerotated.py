import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import exifread
from PIL import Image, ImageOps

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


def load_render_map(log_csv: Path):
    out = {}
    if not log_csv.exists():
        return out
    with log_csv.open('r', encoding='utf-8', errors='ignore', newline='') as f:
        r = csv.DictReader(f)
        for row in r:
            if (row.get('status') or '').lower() != 'ok':
                continue
            src = row.get('source')
            rend = row.get('output')
            if src and rend:
                out[str(Path(src).resolve())] = str(Path(rend).resolve())
    return out


def stem_norm(stem: str):
    s = stem.lower()
    s = re.sub(r'^[^a-z0-9]+', '', s)
    s = re.sub(r'[^a-z0-9]+', '', s)
    return s


def dir_key(root: Path, p: Path):
    return str(p.relative_to(root).parent).lower()


def normalized_base(src: Path):
    with Image.open(src) as im:
        im = ImageOps.exif_transpose(im).convert('RGB')
        return im.copy()


def orient_policy(im: Image.Image):
    # horizontals upright; verticals turned left (CCW 90)
    if im.height > im.width:
        return im.rotate(90, expand=True)
    return im


def match_rotation_for_raw(jpeg_src: Path, raw_src: Path):
    j = orient_policy(normalized_base(jpeg_src))
    r0 = normalized_base(raw_src)

    j_small = ImageOps.fit(j, (256, 256), method=Image.Resampling.BICUBIC)
    best_deg = 0
    best_score = None
    for deg in (0, 90, 180, 270):
        rr = orient_policy(r0.rotate(deg, expand=True))
        rr_small = ImageOps.fit(rr, (256, 256), method=Image.Resampling.BICUBIC)
        d = ImageChops.difference(j_small, rr_small)
        score = sum(ImageStat.Stat(d).mean)
        if best_score is None or score < best_score:
            best_score = score
            best_deg = deg
    return best_deg


def save_with_rotation(src: Path, out: Path, pre_rotate_deg: int = 0):
    out.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(src) as im:
        im = ImageOps.exif_transpose(im).convert('RGB')
        if pre_rotate_deg % 360:
            im = im.rotate(pre_rotate_deg, expand=True)
        im = orient_policy(im)
        im.save(out, format='JPEG', quality=95, subsampling=0)


def pair_nearest(jpegs, raws, max_delta_s=None):
    used = set()
    pairs = []
    for j in jpegs:
        best_i, best_delta = None, None
        for i, r in enumerate(raws):
            if i in used:
                continue
            d = abs((j['dt'] - r['dt']).total_seconds())
            if max_delta_s is not None and d > max_delta_s:
                continue
            if best_delta is None or d < best_delta:
                best_delta = d
                best_i = i
        if best_i is not None:
            used.add(best_i)
            pairs.append((j, raws[best_i]))
    j_un = [j for j in jpegs if all(j is not p[0] for p in pairs)]
    r_un = [r for i, r in enumerate(raws) if i not in used]
    return pairs, j_un, r_un


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', required=True)
    ap.add_argument('--raw-log', required=True)
    ap.add_argument('--heic-log', required=True)
    ap.add_argument('--normalized-out', required=True)
    ap.add_argument('--sequence-out', required=True)
    ap.add_argument('--audit-out', required=True)
    ap.add_argument('--max-fallback-delta', type=float, default=3.0)
    args = ap.parse_args()

    root = Path(args.root)
    normalized_out = Path(args.normalized_out)
    normalized_out.mkdir(parents=True, exist_ok=True)

    raw_map = load_render_map(Path(args.raw_log))
    heic_map = load_render_map(Path(args.heic_log))

    buckets = defaultdict(lambda: {'jpeg': [], 'raw': [], 'heic': []})

    for p in root.rglob('*'):
        if not p.is_file():
            continue
        rel = p.relative_to(root)
        if rel.parts and str(rel.parts[0]).startswith('_'):
            continue

        ext = p.suffix.lower()
        if ext not in JPEG_EXTS | RAW_EXTS | HEIC_EXTS:
            continue

        k = dir_key(root, p)
        dt = exif_datetime(p)
        item = {
            'orig': p,
            'src': p,
            'dt': dt,
            'stem_norm': stem_norm(p.stem),
            'dir_key': k,
        }

        if ext in JPEG_EXTS:
            buckets[k]['jpeg'].append(item)
        elif ext in RAW_EXTS:
            rend = raw_map.get(str(p.resolve()))
            if rend and Path(rend).exists():
                item['src'] = Path(rend)
                buckets[k]['raw'].append(item)
        elif ext in HEIC_EXTS:
            rend = heic_map.get(str(p.resolve()))
            if rend and Path(rend).exists():
                item['src'] = Path(rend)
                buckets[k]['heic'].append(item)

    events = []
    for k, b in buckets.items():
        j = sorted(b['jpeg'], key=lambda x: (x['dt'], str(x['orig'])))
        r = sorted(b['raw'], key=lambda x: (x['dt'], str(x['orig'])))
        h = sorted(b['heic'], key=lambda x: (x['dt'], str(x['orig'])))

        pairs = []
        j_un_all, r_un_all = [], []
        j_by_stem = defaultdict(list)
        r_by_stem = defaultdict(list)
        for x in j:
            j_by_stem[x['stem_norm']].append(x)
        for x in r:
            r_by_stem[x['stem_norm']].append(x)

        stems = sorted(set(j_by_stem.keys()) | set(r_by_stem.keys()))
        for s in stems:
            p1, ju, ru = pair_nearest(j_by_stem.get(s, []), r_by_stem.get(s, []), max_delta_s=None)
            pairs.extend(p1)
            j_un_all.extend(ju)
            r_un_all.extend(ru)

        p2, j_un_all, r_un_all = pair_nearest(
            sorted(j_un_all, key=lambda x: x['dt']),
            sorted(r_un_all, key=lambda x: x['dt']),
            max_delta_s=args.max_fallback_delta,
        )
        pairs.extend(p2)

        for jj, rr in pairs:
            events.append({
                'dt': min(jj['dt'], rr['dt']),
                'kind': 'pair',
                'dir_key': k,
                'items': [
                    {'role': 'jpeg', 'src': str(jj['src']), 'orig': str(jj['orig']), 'raw_match_rot': 0},
                    {'role': 'raw', 'src': str(rr['src']), 'orig': str(rr['orig']), 'raw_match_rot': 0},
                ]
            })

        for x in j_un_all:
            events.append({'dt': x['dt'], 'kind': 'jpeg_single', 'dir_key': k,
                           'items': [{'role': 'jpeg', 'src': str(x['src']), 'orig': str(x['orig']), 'raw_match_rot': 0}]})
        for x in r_un_all:
            events.append({'dt': x['dt'], 'kind': 'raw_single', 'dir_key': k,
                           'items': [{'role': 'raw', 'src': str(x['src']), 'orig': str(x['orig']), 'raw_match_rot': 0}]})
        for x in h:
            events.append({'dt': x['dt'], 'kind': 'heic_single', 'dir_key': k,
                           'items': [{'role': 'heic', 'src': str(x['src']), 'orig': str(x['orig']), 'raw_match_rot': 0}]})

    events.sort(key=lambda e: (e['dt'], e['dir_key'], e['kind']))

    seq = []
    audit = []
    idx = 0
    for ei, ev in enumerate(events):
        for it in ev['items']:
            out = normalized_out / f"{idx:06d}_{it['role']}.jpg"
            rot = it.get('raw_match_rot', 0) if it['role'] == 'raw' else 0
            save_with_rotation(Path(it['src']), out, pre_rotate_deg=rot)
            seq.append(str(out.resolve()))
            audit.append({
                'index': idx,
                'event_index': ei,
                'datetime': ev['dt'].strftime('%Y-%m-%d %H:%M:%S'),
                'event_kind': ev['kind'],
                'role': it['role'],
                'source': it['src'],
                'original': it['orig'],
                'raw_match_rot': rot,
                'normalized': str(out.resolve()),
            })
            idx += 1

    Path(args.sequence_out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.sequence_out).write_text(json.dumps({'count': len(seq), 'sequence': seq}, indent=2), encoding='utf-8')
    Path(args.audit_out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.audit_out).write_text(json.dumps({'rows': audit}, indent=2), encoding='utf-8')

    counts = Counter(a['event_kind'] for a in audit)
    print(f"EVENTS={len(events)} FRAMES={len(seq)} COUNTS={dict(counts)}")


if __name__ == '__main__':
    main()
