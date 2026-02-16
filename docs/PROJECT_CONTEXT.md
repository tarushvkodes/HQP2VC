# Project Context

## Original Objective
Build one final slideshow video from all photos in:

`C:\Users\tarus\Downloads\LoveBytesPhotos`

## Final Spec (locked)

- **8K 3:2 HDR** output
- **8192x5462** frame size (even height for Main10 4:2:0 safety)
- **1 sec per image**, hard cuts only
- **No crop** (fit + pad only)
- **JPG + RAW pairs kept adjacent**, with JPG first
- **HEIC included** by converting to JPEG
- **High bitrate** encode intent (used 300 Mbps CBR-HQ NVENC settings)

## Key Decisions

1. **RAW decoding moved to `rawpy`**
   - FFmpeg often selected embedded low-res/monochrome previews from RAW files.
2. **HEIC decoding moved to `pillow-heif`**
   - Avoided incorrect auxiliary/depth stream extraction that produced tiny/gray frames.
3. **Pair-lock orientation**
   - RAW render orientation was normalized to match paired JPG portrait/landscape orientation.
4. **MKV-first encoding**
   - After an invalid MP4 (`moov atom not found`), switched to encode MKV then remux to MP4.

## Dataset / Pipeline Outcomes

- ZIP archives extracted: 32
- ZIPs removed post-extraction: 32
- Total extracted files: 3141
- RAW conversion (`rawpy`) run summary:
  - total=1386, ok=1335, fail=0, skip=51
- HEIC conversion (`pillow-heif`) run summary:
  - total=163, ok=163, fail=0
- Final built sequence size: 3090 image steps

## Important Paths

- Source root: `C:\Users\tarus\Downloads\LoveBytesPhotos`
- RAW JPEG outputs: `C:\Users\tarus\Downloads\LoveBytesPhotos\_raw_jpeg_pipeline_full`
- RAW log: `C:\Users\tarus\Downloads\LoveBytesPhotos\_raw_jpeg_pipeline_full\rawpy_render_log_bright_resume.csv`
- HEIC JPEG outputs: `C:\Users\tarus\Downloads\LoveBytesPhotos\_heic_jpeg_pipeline_full`
- HEIC log: `C:\Users\tarus\Downloads\LoveBytesPhotos\_heic_jpeg_pipeline_full\heic_render_log_pillow.csv`
- Final concat list: `C:\Users\tarus\Downloads\LoveBytesPhotos\_build_final_3x2_dci\concat.txt`
- Encode target MKV: `C:\Users\tarus\Downloads\LoveBytesPhotos\LoveBytes_full_8k_3x2_ALL_1s_HDR_MAXBITRATE.mkv`
- Remux target MP4: `C:\Users\tarus\Downloads\LoveBytesPhotos\LoveBytes_full_8k_3x2_ALL_1s_HDR_MAXBITRATE.mp4`

## Chronological Pairing Rebuild (2026-02-15)

User reported sequence integrity issues in prior output:
- non-chronological ordering across mixed formats
- inconsistent JPEG/RAW adjacency
- RAW/JPEG pair orientation mismatches
- upside-down horizontals / inconsistent vertical direction

Rebuild policy locked:
1. Global sequence sorted by EXIF capture datetime.
2. Pairing handled at event level (not by extension batches).
3. For each matched event, output order is always `JPEG -> RAW`.
4. RAW orientation is normalized to JPEG orientation for the same event.
5. Vertical images are normalized to a single direction policy (left-turn consistency).

Implementation in progress script:
- `scripts/09_build_chrono_pair_sequence.py`
- Reuses existing rendered assets (`_raw_jpeg_pipeline_full`, `_heic_jpeg_pipeline_full`) to avoid full reconversion.

## Chronological-Mated Render Outcomes (2026-02-15)

- Rebuilt chronology/mating pipeline produced:
  - `EVENTS=2904`
  - `FRAMES=3081`
  - `COUNTS={'heic_single': 163, 'pair': 354, 'raw_single': 1158, 'jpeg_single': 1406}`
- Full render attempt to:
  - `LoveBytes_full_8k_3x2_ALL_1s_HDR_MAXBITRATE_CHRONO_MATED.mkv`
  failed around `00:34:05` (partial preserved).
- Recovery for chronology-mated run:
  1. Build tail from `start=2045` (of total `3081`).
  2. Encode tail to `LoveBytes_full_8k_3x2_ALL_1s_HDR_MAXBITRATE_CHRONO_MATED_tail.mkv`.
  3. Stitch partial + tail with concat demuxer (`-c copy`) to:
     - `LoveBytes_full_8k_3x2_ALL_1s_HDR_MAXBITRATE_CHRONO_MATED_COMBINED.mkv`
- Final stitched validation:
  - `duration=3082.166000`
  - `size=41272346321`

## Additional Recovery Work (2026-02-15)

- Long MKV encode run `quick-kelp` failed around `00:35:19` with partial file preserved.
- Recovery strategy used:
  1. Build a **tail concat** starting near failure second index (`start=2119` from 3090).
  2. Encode tail segment to `LoveBytes_full_8k_3x2_ALL_1s_HDR_MAXBITRATE_tail.mkv`.
  3. Stitch `partial + tail` into a combined MKV using concat demuxer and `-c copy`.
- Tail concat path: `C:\Users\tarus\Downloads\LoveBytesPhotos\_build_resume_tail\concat_tail.txt`
- Stitch list path: `C:\Users\tarus\Downloads\LoveBytesPhotos\_build_resume_tail\stitch_list.txt`
- Combined output MKV path:
  - `C:\Users\tarus\Downloads\LoveBytesPhotos\LoveBytes_full_8k_3x2_ALL_1s_HDR_MAXBITRATE_COMBINED.mkv`

> Note: This resume method can create a tiny overlap or micro-gap around the cut point if the exact failure second is estimated. For strict frame-accurate joins, compute start index from the actual completed frame count/timebase.