import argparse, json
from pathlib import Path


def esc(p: str) -> str:
    return p.replace("'", "'\\''")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--sequence', required=True)
    ap.add_argument('--concat-out', required=True)
    ap.add_argument('--duration', type=float, default=1.0)
    args = ap.parse_args()

    data = json.loads(Path(args.sequence).read_text(encoding='utf-8'))
    seq = data['sequence']

    out = Path(args.concat_out)
    out.parent.mkdir(parents=True, exist_ok=True)

    lines = []
    for p in seq:
        lines.append(f"file '{esc(p)}'")
        lines.append(f"duration {args.duration}")

    if seq:
        lines.append(f"file '{esc(seq[-1])}'")

    out.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(f'WROTE={out} entries={len(seq)}')


if __name__ == '__main__':
    main()
