param(
    [string]$InputRoot = "c:/input/dir",
    [string]$OutputRoot = "c:/output/dir",
    [double]$WaterMndwi = 0.05,
    [double]$WaterNdviMax = 0.15,
    [double]$VegetationNdvi = 0.30,
    [double]$BareBsi = 0.05,
    [double]$BareMndwiMax = 0.00
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Get-ToolPath {
    param([string]$Name)
    $cmd = Get-Command $Name -ErrorAction SilentlyContinue
    if ($null -eq $cmd) {
        throw "some tool error: $Name"
    }
    return $cmd.Source
}

$otbLauncher = Get-ToolPath "otbApplicationLauncherCommandLine"

$launcherDir = Split-Path $otbLauncher -Parent
$otbRoot = Split-Path $launcherDir -Parent
$defaultAppsPath = Join-Path $otbRoot "lib/otb/applications"
if ([string]::IsNullOrWhiteSpace($env:OTB_APPLICATION_PATH) -and (Test-Path $defaultAppsPath)) {
    $env:OTB_APPLICATION_PATH = $defaultAppsPath
}

function Invoke-Otb {
    param(
        [Parameter(Mandatory = $true)][string[]]$Args
    )

    & $otbLauncher @Args
    if ($LASTEXITCODE -ne 0) {
        throw "otb failure, exit was: ${LASTEXITCODE}: $($Args -join ' ')"
    }
}

if (-not (Test-Path $InputRoot)) {
    throw "this inputt doesn't exis: $InputRoot"
}

New-Item -ItemType Directory -Path $OutputRoot -Force | Out-Null

$scenes = @(Get-ChildItem -Path $InputRoot -Recurse -Filter *.tif | Sort-Object FullName)
if ($scenes.Count -eq 0) {
    Write-Output "no files found in this dir: $InputRoot"
    exit 0
}

Write-Output "there are $($scenes.Count) found to use"

foreach ($scene in $scenes) {
    $dateLabel = $scene.BaseName
    $sceneOut = Join-Path $OutputRoot $dateLabel
    New-Item -ItemType Directory -Path $sceneOut -Force | Out-Null

    $ndvi = Join-Path $sceneOut "${dateLabel}_ndvi.tif"
    $ndwi = Join-Path $sceneOut "${dateLabel}_ndwi.tif"
    $mndwi = Join-Path $sceneOut "${dateLabel}_mndwi.tif"
    $bsi = Join-Path $sceneOut "${dateLabel}_bsi.tif"

    $water = Join-Path $sceneOut "${dateLabel}_water_mask.tif"
    $vegetation = Join-Path $sceneOut "${dateLabel}_vegetation_mask.tif"
    $bare = Join-Path $sceneOut "${dateLabel}_bare_sediment_mask.tif"
    $active = Join-Path $sceneOut "${dateLabel}_active_channel_mask.tif"

    Write-Output "Processing $($scene.FullName)"

    Invoke-Otb -Args @("BandMath", "-il", $scene.FullName, "-exp", "(im1b7-im1b3)/(im1b7+im1b3+0.0001)", "-out", $ndvi, "float")
    Invoke-Otb -Args @("BandMath", "-il", $scene.FullName, "-exp", "(im1b2-im1b7)/(im1b2+im1b7+0.0001)", "-out", $ndwi, "float")
    Invoke-Otb -Args @("BandMath", "-il", $scene.FullName, "-exp", "(im1b2-im1b8)/(im1b2+im1b8+0.0001)", "-out", $mndwi, "float")
    Invoke-Otb -Args @("BandMath", "-il", $scene.FullName, "-exp", "((im1b8+im1b3)-(im1b7+im1b1))/((im1b8+im1b3)+(im1b7+im1b1)+0.0001)", "-out", $bsi, "float")

    Invoke-Otb -Args @("BandMath", "-il", $ndvi, $mndwi, $bsi, "-exp", "(im2b1>$WaterMndwi and im1b1<$WaterNdviMax)?1:0", "-out", $water, "uint8")
    Invoke-Otb -Args @("BandMath", "-il", $ndvi, "-exp", "(im1b1>$VegetationNdvi)?1:0", "-out", $vegetation, "uint8")
    Invoke-Otb -Args @("BandMath", "-il", $ndvi, $mndwi, $bsi, "-exp", "(im3b1>$BareBsi and im2b1<$BareMndwiMax)?1:0", "-out", $bare, "uint8")
    Invoke-Otb -Args @("BandMath", "-il", $water, $bare, "-exp", "(im1b1==1 or im2b1==1)?1:0", "-out", $active, "uint8")
}

Write-Output "finished, saved in $OutputRoot"
