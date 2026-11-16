# Regenerate the board, check it, and write the fabrication files.
#   pwsh hardware/pcb/export.ps1
$ErrorActionPreference = "Stop"
$kicad = Join-Path $env:LOCALAPPDATA "Programs\KiCad\10.0\bin"
Set-Location $PSScriptRoot

& "$kicad\python.exe" gen_pcb.py
if ($LASTEXITCODE) { throw "gen_pcb.py failed" }

# Design-rule check. Courtyard overlaps are expected (axial parts on a 2.54 mm
# pitch) and are filtered out; anything else of severity "error" stops here.
& "$kicad\kicad-cli.exe" pcb drc --format json --severity-all -o drc.json damper.kicad_pcb | Out-Null
$drc = Get-Content drc.json -Raw | ConvertFrom-Json
$bad = @($drc.violations | Where-Object { $_.severity -eq "error" -and $_.type -ne "courtyards_overlap" })
$open = @($drc.unconnected_items)
Remove-Item drc.json
"DRC: $($bad.Count) errors, $($open.Count) unconnected"
if ($bad.Count -or $open.Count) { $bad + $open | ForEach-Object { $_.type + ": " + $_.description }; throw "DRC failed" }

Remove-Item gerbers -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory gerbers | Out-Null
& "$kicad\kicad-cli.exe" pcb export gerbers -o gerbers/ --layers "F.Cu,B.Cu,F.Mask,B.Mask,F.SilkS,B.SilkS,Edge.Cuts" damper.kicad_pcb | Out-Null
& "$kicad\kicad-cli.exe" pcb export drill -o gerbers/ --format excellon --excellon-separate-th damper.kicad_pcb | Out-Null
Compress-Archive -Path gerbers/* -DestinationPath gerbers/damper-rev1.zip -Force

# 1:1 print for the paper fit check
& "$kicad\kicad-cli.exe" pcb export pdf -o damper-1to1.pdf --layers "F.Mask,F.SilkS,Edge.Cuts" --mode-single --black-and-white damper.kicad_pcb | Out-Null
Get-ChildItem gerbers, damper-1to1.pdf | Select-Object Name, Length
