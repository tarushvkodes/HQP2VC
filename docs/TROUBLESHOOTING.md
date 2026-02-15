# Troubleshooting Notes

## 1) Output appears black

### Symptom
- Video looks black in some players/displays.

### Cause
- HDR playback path/display mismatch; not necessarily bad frames.

### Check
```bash
ffmpeg -i output.mp4 -vf signalstats -f null -
```
If signal levels vary, content exists and playback stack is the issue.

### Workarounds
- Test in HDR-capable player/display path.
- Create SDR preview for visual sanity checks.

---

## 2) FFmpeg RAW decode gives tiny/garbage images

### Symptom
- RAW decode outputs like `160x120`, monochrome, or tiny byte-size files.

### Cause
- FFmpeg selecting embedded preview/thumbnail-like streams.

### Fix
- Use `rawpy` pipeline for RAW demosaic/export.

---

## 3) HEIC conversion outputs tiny/gray frames

### Symptom
- HEIC-derived frames are tiny, grayscale, or wrong content.

### Cause
- Wrong HEIC auxiliary/depth/dependent stream selected.

### Fix
- Convert HEIC via `pillow-heif` (primary image decode path).

---

## 4) `moov atom not found` on long MP4 encode

### Symptom
- Big MP4 exists but is invalid/unfinalized after interruption/failure.

### Fix
- Encode to **MKV first**.
- On success, remux MKV -> MP4 with stream copy:

```bash
ffmpeg -y -i input.mkv -c copy -movflags +faststart output.mp4
```

---

## 5) Noisy FFmpeg warnings (`deprecated pixel format`, filter reconfig)

### Symptom
- Tons of warnings during mixed image sequence render.

### Reality
- Expected for huge mixed-source libraries with varying dimensions/pixel formats/orientation matrices.

### Action
- Monitor for fatal errors only; many warnings are non-fatal.

---

## 6) Frame duplication (`dup`) climbs quickly

### Why
- Input concat/image timing and output fps interplay can generate dup frames.

### Action
- Ensure concat durations and output `-r` choices match intended cadence.
- For fixed 1s holds, this can be acceptable depending on pipeline design.

---

## 7) RAW appears rotated opposite to JPEG

### Symptom
- Same capture shows JPEG and RAW in opposite direction.

### Cause
- RAW decoder orientation metadata/path differs from JPEG orientation handling.

### Fix
- Treat JPEG as canonical orientation for matched pair.
- Normalize both frames with EXIF transpose first.
- Compute/apply RAW correction to match JPEG orientation class.
- Enforce final policy: horizontals right-side-up, verticals consistently left-turned.

---

## 8) Long MKV encode crashes mid-run

### Symptom
- FFmpeg exits non-zero after long progress; partial MKV exists.

### Fast recovery (no full restart)
1. Estimate completed seconds from failed run time (e.g., `00:35:19` -> `2119`).
2. Build tail concat beginning at that index.
3. Encode tail to a second MKV.
4. Concatenate partial + tail with `-c copy` into a combined MKV.

### Caveat
- If start index is approximate, there may be minor overlap/gap at boundary.
- For precision, derive split point from exact packet/frame timestamps.