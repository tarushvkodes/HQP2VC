param(
  [Parameter(Mandatory=$true)][string]$Root,
  [switch]$DeleteZips
)

$ErrorActionPreference = 'Stop'
$zips = Get-ChildItem -Path $Root -Filter *.zip -File -Recurse
Write-Host "ZIP count:" $zips.Count

foreach($z in $zips){
  Write-Host "Extracting:" $z.FullName
  Expand-Archive -Path $z.FullName -DestinationPath $z.DirectoryName -Force
}

if($DeleteZips){
  $bytes = ($zips | Measure-Object -Property Length -Sum).Sum
  $zips | Remove-Item -Force
  Write-Host "Deleted ZIPs:" $zips.Count
  Write-Host "Freed bytes:" $bytes
}
