param(
  [Parameter(Mandatory=$true)][string]$Concat,
  [Parameter(Mandatory=$true)][string]$OutMkv
)

$ErrorActionPreference='Stop'

$vf = "rotate='if(gt(abs(iw/ih-3/2),abs(ih/iw-3/2)),PI/2,0)':ow='if(gt(abs(iw/ih-3/2),abs(ih/iw-3/2)),ih,iw)':oh='if(gt(abs(iw/ih-3/2),abs(ih/iw-3/2)),iw,ih)':c=black,scale=8192:5462:force_original_aspect_ratio=decrease,pad=8192:5462:(ow-iw)/2:(oh-ih)/2:black,format=p010le,setsar=1"

ffmpeg -y -f concat -safe 0 -i $Concat `
  -vf $vf `
  -r 6 `
  -c:v hevc_nvenc -profile:v main10 -preset p5 -rc cbr_hq `
  -b:v 300M -minrate 300M -maxrate 300M -bufsize 600M `
  -color_primaries bt2020 -color_trc smpte2084 -colorspace bt2020nc `
  $OutMkv
