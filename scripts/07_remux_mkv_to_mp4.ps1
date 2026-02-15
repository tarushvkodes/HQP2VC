param(
  [Parameter(Mandatory=$true)][string]$InMkv,
  [Parameter(Mandatory=$true)][string]$OutMp4
)

$ErrorActionPreference='Stop'
ffmpeg -y -i $InMkv -c copy -movflags +faststart $OutMp4
