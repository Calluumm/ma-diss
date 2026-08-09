#& "C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe" -ExecutionPolicy Bypass -File "03_Methods/02_Modelling/dualrun.ps1"
#So i can go to lunch and not worry about starting the next part of the pipeline :D wonderful
#this literally just runs the 3 powershell scripts in series
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$scriptdir = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "running classify"
& (Join-Path $scriptdir "classify.ps1")
if ($LASTEXITCODE -ne 0) {
    throw "classify.ps1 failed with exit code $LASTEXITCODE"
}

Write-Host "running change"
& (Join-Path $scriptdir "change.ps1")
if ($LASTEXITCODE -ne 0) {
    throw "change.ps1 failed with exit code $LASTEXITCODE"
}

Write-Host "running confusion"
& (Join-Path $scriptdir "confusion.ps1")
if ($LASTEXITCODE -ne 0) {
    throw "confusion.ps1 failed with exit code $LASTEXITCODE"
}

Write-Host "finished pipeline"
