param(
  [Parameter(Mandatory=$true)][string]$Path
)

$ErrorActionPreference='Stop'

ffprobe -v error -select_streams v:0 -show_entries stream=codec_name,profile,pix_fmt,width,height,color_space,color_transfer,color_primaries -of default=noprint_wrappers=1:nokey=0 $Path
ffprobe -v error -show_entries format=duration,size -of default=noprint_wrappers=1:nokey=0 $Path
