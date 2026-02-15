# HQP2VC — High Quality Photo Video Concat

This repo (**HQP2VC**, short for **High Quality Photo Video Concat**) documents and packages the full workflow used to build a **single 8K 3:2 HDR slideshow** from mixed Amazon Photos exports (JPG + RAW + HEIC), with strict pairing and sequence rules.

## Final Target

- Container: MP4 (from MKV remux)
- Codec: HEVC Main10 (`hevc_nvenc`)
- HDR signaling: BT.2020 + PQ (`smpte2084`)
- Resolution: `8192x5462` (3:2, even height for 4:2:0 Main10 compatibility)
- Cadence: 1 second per image (hard cuts only)
- Rule: keep JPG and RAW counterparts adjacent (`JPG -> RAW`)
- Rule: include HEIC content via conversion to JPEG
- Rule: no crop (rotate-to-fit heuristic + scale + pad)
- Rule: sequence by EXIF capture time at the **event level** (never grouped by file type)
- Rule: orientation consistency per pair: RAW is matched to JPEG orientation; vertical outputs are normalized to a consistent left-turn policy

## Why this exists

Raw command history got long and iterative. This repo turns everything into a reproducible pipeline with scripts, command templates, and troubleshooting notes.

## Repo Layout

- `docs/PROJECT_CONTEXT.md` — full project goals, constraints, decisions, outcomes
- `docs/COMMAND_LOG.md` — canonical command sequence
- `docs/TROUBLESHOOTING.md` — known failures + fixes
- `scripts/` — reproducible scripts for extraction, conversion, sequence build, encode, remux, validation

## Quick Start

1. Install dependencies
2. Extract all Amazon ZIPs
3. Convert RAW -> JPEG (`rawpy`)
4. Convert HEIC -> JPEG (`pillow-heif`)
5. Build EXIF-chronological event sequence with strict `JPEG->RAW` adjacency and orientation normalization
6. Build concat list
7. Encode MKV (crash-safe)
8. Remux MKV -> MP4
9. Validate output metadata

See `docs/COMMAND_LOG.md` for exact commands.

## Dependencies

- FFmpeg + ffprobe (newer builds recommended)
- Python 3.10+
- `pip install -r scripts/requirements.txt`

## Important Notes

- Prior direct MP4 full encode failed with `moov atom not found` after interruption. MKV-first is safer.
- Some MJPEG decode warnings/errors are expected in giant mixed photo sets; pipeline is resilient and continues.
- HEIC auxiliary streams can produce tiny/gray output when decoded incorrectly; use `pillow-heif` conversion path.
- FFmpeg RAW decode can choose embedded tiny previews (`160x120` etc.); use `rawpy` for full-quality demosaic.
- If long MKV encode crashes mid-run, use the documented **tail resume + MKV stitch** workflow in `docs/COMMAND_LOG.md` and `docs/TROUBLESHOOTING.md` to avoid starting over.

## GitHub Publish

This repo is local. To publish:

```bash
git init
git add .
git commit -m "Add reproducible LoveBytes 8K HDR slideshow pipeline"
git branch -M main
git remote add origin https://github.com/<you>/HQP2VC.git
git push -u origin main
```

If you want, I can also wire this to your GitHub remote and push directly.