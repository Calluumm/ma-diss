param(
    [string]$InputRoot = "c:/input",
    [bool]$ApplySinglePixelCleanup = $true,
    [int]$CleanupRadius = 2,
    [bool]$ApplyWaterEdgeRecovery = $true,
    [int]$WaterEdgeRadius = 1,
    [double]$WaterEdgeNdviMax = 0.30,
    [double]$WaterEdgeMndwiMin = -0.15,
    [double]$WaterEdgeNdwiMin = -0.03,
    [double]$BareNdwiMax = -0.02,
    [string]$ClassifiedRoot = "c:/classified file input",
    [string]$ChangeRoot = "c:/overall output for change framework",
    [bool]$AllMasks = $true,
    [bool]$ApplyMorphologyCleanup = $true,
    [int]$MorphologyRadius = 1,
    [int]$CloudBufferRadius = 2
)
#see latter keep these
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$classifyScript = Join-Path $scriptDir "classifyRGeoms.ps1"
$changeScript = Join-Path $scriptDir "change_frmk.ps1"

if (-not (Test-Path $ClassifiedRoot)) {
    New-Item -ItemType Directory -Path $ClassifiedRoot -Force | Out-Null
}

if (-not (Test-Path $ChangeRoot)) {
    New-Item -ItemType Directory -Path $ChangeRoot -Force | Out-Null
}

Write-Host "[1/2] running classify"
$classifyParams = @{
    InputRoot = $InputRoot
    OutputRoot = $ClassifiedRoot
    CleanupRadius = $CleanupRadius
    WaterEdgeRadius = $WaterEdgeRadius
    WaterEdgeNdviMax = $WaterEdgeNdviMax
    WaterEdgeMndwiMin = $WaterEdgeMndwiMin
    WaterEdgeNdwiMin = $WaterEdgeNdwiMin
    BareNdwiMax = $BareNdwiMax
}
if ($ApplySinglePixelCleanup) { $classifyParams.ApplySinglePixelCleanup = $true }
if ($ApplyWaterEdgeRecovery) { $classifyParams.ApplyWaterEdgeRecovery = $true }

& $classifyScript @classifyParams
if ($LASTEXITCODE -ne 0) {
    throw "classify failed error $LASTEXITCODE"
}
Write-Host "[2/2] running change framework."
$changeParams = @{
    MorphologyRadius = $MorphologyRadius
    CloudBufferRadius = $CloudBufferRadius
    ClassifiedRoot = $ClassifiedRoot
    OutputRoot = $ChangeRoot
}
if ($AllMasks) { $changeParams.AllMasks = $true }
if ($ApplyMorphologyCleanup) { $changeParams.ApplyMorphologyCleanup = $true }

& $changeScript @changeParams
if ($LASTEXITCODE -ne 0) {
    throw "change framework error $LASTEXITCODE"
}

Write-Host "both succeded"
