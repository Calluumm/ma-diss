param(
    [string]$InputRoot = "c:/Users/Student/Desktop/Masters/Dissertation/02_Data/01_Raw/Scenes/Sentinel2/longtimeseries",
    [bool]$ApplySinglePixelCleanup = $true,
    [int]$CleanupRadius = 2,
    [bool]$ApplyWaterEdgeRecovery = $true,
    [int]$WaterEdgeRadius = 1,
    [double]$WaterEdgeNdviMax = 0.30,
    [double]$WaterEdgeMndwiMin = -0.15,
    [double]$WaterEdgeNdwiMin = -0.03,
    [double]$BareNdwiMax = -0.02,
    [string]$ClassifiedRoot = "c:/Users/Student/Desktop/Masters/Dissertation/02_Data/02_Processed/Sentinel2_Geomorphology_OTB",
    [string]$ChangeRoot = "c:/Users/Student/Desktop/Masters/Dissertation/02_Data/02_Processed/Sentinel2_ChangeFramework",
    [bool]$AllMasks = $true,
    [bool]$ApplyMorphologyCleanup = $true,
    [int]$MorphologyRadius = 1,
    [int]$CloudBufferRadius = 2
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$classifyScript = Join-Path $scriptDir "classifyRGeoms.ps1"
$changeScript = Join-Path $scriptDir "change_frmk.ps1"

if (-not (Test-Path $classifyScript)) {
    throw "Missing script: $classifyScript"
}
if (-not (Test-Path $changeScript)) {
    throw "Missing script: $changeScript"
}

if (-not (Test-Path $ClassifiedRoot)) {
    New-Item -ItemType Directory -Path $ClassifiedRoot -Force | Out-Null
}

if (-not (Test-Path $ChangeRoot)) {
    New-Item -ItemType Directory -Path $ChangeRoot -Force | Out-Null
}

Write-Host "[1/2] Running classifyRGeoms.ps1..."
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
    throw "classifyRGeoms.ps1 failed with exit code $LASTEXITCODE"
}
Write-Host "[2/2] Running change_frmk.ps1..."
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
    throw "change_frmk.ps1 failed with exit code $LASTEXITCODE"
}

Write-Host "Done: classification then change framework completed successfully."
