# Technical Write-up

This pipeline was built to handle a real-world mixed media export at scale.

## What made it hard

- Inputs were highly heterogeneous (JPG, HEIC, many RAW families, mixed orientation metadata).
- FFmpeg alone was not reliable for all HEIC/RAW decodes.
- Long-run high-bitrate MP4 encode is fragile if interrupted (container finalization risk).

## Reliability pattern used

1. Normalize fragile source formats to stable JPEG intermediates.
2. Build deterministic sequence order in JSON.
3. Generate concat list from sequence.
4. Encode into resilient MKV container.
5. Remux to MP4 at the end (stream copy, no re-encode).

## Quality profile used

- Main10 HEVC
- BT.2020 + PQ signaling
- 8192x5462 render size (3:2 with even height)
- No crop, only rotate-fit + scale + pad
- High bitrate CBR-HQ profile tuned for visual integrity

## Repro philosophy

- Keep scripts small and auditable.
- Keep path conventions explicit.
- Keep logs for every conversion stage.
- Separate context docs from executable scripts.