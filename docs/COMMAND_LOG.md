# Command Log (Repro)

> Run from PowerShell unless stated otherwise.

## 0) Python deps

```powershell
cd C:\Users\tarus\.openclaw\workspace\lovebytes-slideshow-repro\scripts
pip install -r requirements.txt
```

## 1) Extract all ZIPs (and optional cleanup)

```powershell
pwsh .\01_extract_zips.ps1 -Root "C:\Users\tarus\Downloads\LoveBytesPhotos" -DeleteZips
```

## 2) RAW -> JPEG (rawpy)

```powershell
python .\02_render_raw_to_jpeg.py `
  --root "C:\Users\tarus\Downloads\LoveBytesPhotos" `
  --out "C:\Users\tarus\Downloads\LoveBytesPhotos\_raw_jpeg_pipeline_full" `
  --log "C:\Users\tarus\Downloads\LoveBytesPhotos\_raw_jpeg_pipeline_full\rawpy_render_log.csv"
```

## 3) HEIC -> JPEG (pillow-heif)

```powershell
python .\03_convert_heic_to_jpeg.py `
  --root "C:\Users\tarus\Downloads\LoveBytesPhotos" `
  --out "C:\Users\tarus\Downloads\LoveBytesPhotos\_heic_jpeg_pipeline_full" `
  --log "C:\Users\tarus\Downloads\LoveBytesPhotos\_heic_jpeg_pipeline_full\heic_render_log_pillow.csv"
```

## 4) Build ordered sequence (JPG then RAW pair, plus HEIC-derived JPEG)

```powershell
python .\04_build_sequence.py `
  --root "C:\Users\tarus\Downloads\LoveBytesPhotos" `
  --raw-jpeg-root "C:\Users\tarus\Downloads\LoveBytesPhotos\_raw_jpeg_pipeline_full" `
  --heic-jpeg-root "C:\Users\tarus\Downloads\LoveBytesPhotos\_heic_jpeg_pipeline_full" `
  --out-seq "C:\Users\tarus\Downloads\LoveBytesPhotos\_build_final_3x2_dci\sequence.json"
```

## 5) Build concat.txt from sequence

```powershell
python .\05_make_concat.py `
  --sequence "C:\Users\tarus\Downloads\LoveBytesPhotos\_build_final_3x2_dci\sequence.json" `
  --concat-out "C:\Users\tarus\Downloads\LoveBytesPhotos\_build_final_3x2_dci\concat.txt" `
  --duration 1.0
```

## 6) Encode MKV (crash-safe)

```powershell
pwsh .\06_encode_hdr_8k_mkv.ps1 `
  -Concat "C:\Users\tarus\Downloads\LoveBytesPhotos\_build_final_3x2_dci\concat.txt" `
  -OutMkv "C:\Users\tarus\Downloads\LoveBytesPhotos\LoveBytes_full_8k_3x2_ALL_1s_HDR_MAXBITRATE.mkv"
```

## 7) Remux MKV -> MP4

```powershell
pwsh .\07_remux_mkv_to_mp4.ps1 `
  -InMkv "C:\Users\tarus\Downloads\LoveBytesPhotos\LoveBytes_full_8k_3x2_ALL_1s_HDR_MAXBITRATE.mkv" `
  -OutMp4 "C:\Users\tarus\Downloads\LoveBytesPhotos\LoveBytes_full_8k_3x2_ALL_1s_HDR_MAXBITRATE.mp4"
```

## 8) Validate output

```powershell
pwsh .\08_validate_output.ps1 -Path "C:\Users\tarus\Downloads\LoveBytesPhotos\LoveBytes_full_8k_3x2_ALL_1s_HDR_MAXBITRATE.mp4"
```
