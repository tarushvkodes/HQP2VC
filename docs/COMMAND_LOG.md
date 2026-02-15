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

## 9) Crash recovery (resume + stitch MKV only)

### 9.1 Build tail concat from failure time index

```powershell
python - << 'PY'
from pathlib import Path
root = Path(r"C:\Users\tarus\Downloads\LoveBytesPhotos")
concat_in = root / "_build_final_3x2_dci" / "concat.txt"
out = root / "_build_resume_tail" / "concat_tail.txt"
out.parent.mkdir(parents=True, exist_ok=True)
resume_sec = 2119  # example from 00:35:19 failure
lines = concat_in.read_text(encoding='utf-8').splitlines()
files = [ln[6:-1] for ln in lines if ln.startswith("file '") and ln.endswith("'")]
if len(files) >= 2 and files[-1] == files[-2]:
    files = files[:-1]
start = max(0, min(resume_sec, len(files)-1))
tail = files[start:]
with out.open('w', encoding='utf-8', newline='\n') as f:
    for p in tail:
        f.write(f"file '{p}'\n")
        f.write("duration 1\n")
    if tail:
        f.write(f"file '{tail[-1]}'\n")
print('TAIL', len(tail), 'START', start)
PY
```

### 9.2 Encode tail MKV

```powershell
ffmpeg -y -f concat -safe 0 -i "C:\Users\tarus\Downloads\LoveBytesPhotos\_build_resume_tail\concat_tail.txt" \
  -vf "rotate='if(gt(abs(iw/ih-3/2),abs(ih/iw-3/2)),PI/2,0)':ow='if(gt(abs(iw/ih-3/2),abs(ih/iw-3/2)),ih,iw)':oh='if(gt(abs(iw/ih-3/2),abs(ih/iw-3/2)),iw,ih)':c=black,scale=8192:5462:force_original_aspect_ratio=decrease,pad=8192:5462:(ow-iw)/2:(oh-ih)/2:black,format=p010le,setsar=1" \
  -r 6 -c:v hevc_nvenc -profile:v main10 -preset p5 -rc cbr_hq \
  -b:v 300M -minrate 300M -maxrate 300M -bufsize 600M \
  -color_primaries bt2020 -color_trc smpte2084 -colorspace bt2020nc \
  "C:\Users\tarus\Downloads\LoveBytesPhotos\LoveBytes_full_8k_3x2_ALL_1s_HDR_MAXBITRATE_tail.mkv"
```

### 9.3 Stitch partial + tail into combined MKV (no remux)

```powershell
$root='C:\Users\tarus\Downloads\LoveBytesPhotos'
$list=Join-Path $root '_build_resume_tail\stitch_list.txt'
$part=Join-Path $root 'LoveBytes_full_8k_3x2_ALL_1s_HDR_MAXBITRATE.mkv'
$tail=Join-Path $root 'LoveBytes_full_8k_3x2_ALL_1s_HDR_MAXBITRATE_tail.mkv'
$combined=Join-Path $root 'LoveBytes_full_8k_3x2_ALL_1s_HDR_MAXBITRATE_COMBINED.mkv'
$enc = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($list, "file '$part'`nfile '$tail'`n", $enc)
ffmpeg -y -f concat -safe 0 -i $list -c copy $combined
ffprobe -v error -show_entries format=duration,size -of default=noprint_wrappers=1:nokey=0 $combined
```
