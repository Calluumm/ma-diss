param(
    [string]$InputRoot = "c:/input files",
    [string]$OutputRoot = "C:/output file/",
    [double]$WaterMndwi = 0.05,
    [double]$WaterNdviMax = 0.15,
    [double]$VegetationNdvi = 0.30,
    [double]$BareBsi = 0.05,
    [double]$BareMndwiMax = 0.00,
    [double]$CloudVisNirRatioMin = 1.15,
    [double]$CloudVisNirRatioLooseMin = 0.95,
    [double]$CloudNdviMax = 0.20,
    [double]$CloudNdviLooseMax = 0.35,
    [double]$CloudMndwiMax = 0.20,
    [double]$CloudMndwiLooseMax = 0.35,
    [double]$CloudBsiMax = 0.25,
    [switch]$ApplySinglePixelCleanup,
    [int]$CleanupRadius = 1
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function gettool {
    param([string]$Name)
    $cmd = Get-Command $Name -ErrorAction SilentlyContinue
    if ($null -eq $cmd) {
        throw "missing tool: $Name"
    }
    return $cmd.Source
}

function runotb {
    param([Parameter(Mandatory = $true)][string[]]$Args)
    & $script:otbLauncher @Args
    if ($LASTEXITCODE -ne 0) {
        throw "OTB failed (${LASTEXITCODE}): $($Args -join ' ')"
    }
}

function openbin {
    param(
        [Parameter(Mandatory = $true)][string]$InputBinary,
        [Parameter(Mandatory = $true)][string]$OutputBinary,
        [Parameter(Mandatory = $true)][int]$Radius
    )

    runotb -Args @(
        "BinaryMorphologicalOperation",
        "-in", $InputBinary,
        "-channel", "1",
        "-structype", "box",
        "-xradius", $Radius,
        "-yradius", $Radius,
        "-foreval", "1",
        "-backval", "0",
        "-filter", "opening",
        "-out", $OutputBinary, "uint8"
    )
}

if (-not (Test-Path $InputRoot)) {
    throw "no input $InputRoot"
}

$script:otbLauncher = gettool "otbApplicationLauncherCommandLine"

$launcherDir = Split-Path $script:otbLauncher -Parent
$otbRoot = Split-Path $launcherDir -Parent
$defaultAppsPath = Join-Path $otbRoot "lib/otb/applications"
if ([string]::IsNullOrWhiteSpace($env:OTB_APPLICATION_PATH) -and (Test-Path $defaultAppsPath)) {
    $env:OTB_APPLICATION_PATH = $defaultAppsPath
}

New-Item -ItemType Directory -Path $OutputRoot -Force | Out-Null

$scenes = @(
    Get-ChildItem -Path $InputRoot -Recurse -Filter *.tif |
        Where-Object {
            $_.DirectoryName -notmatch '(?i)[\\/]qa_masks([\\/]|$)' -and
            $_.BaseName -notmatch '(?i)_qa_mask$'
        } |
        Sort-Object FullName
)
if ($scenes.Count -eq 0) {
    Write-Output "no files found in this dir: $InputRoot"
    exit 0
}

Write-Output "processing $($scenes.Count) scenes"

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
    $cloud = Join-Path $sceneOut "${dateLabel}_cloud_mask.tif"
    $active = Join-Path $sceneOut "${dateLabel}_active_channel_mask.tif"

    Write-Output "processing $dateLabel"

    runotb -Args @("BandMath", "-il", $scene.FullName, "-exp", "(im1b7-im1b3)/(im1b7+im1b3+0.0001)", "-out", $ndvi, "float")
    runotb -Args @("BandMath", "-il", $scene.FullName, "-exp", "(im1b2-im1b7)/(im1b2+im1b7+0.0001)", "-out", $ndwi, "float")
    runotb -Args @("BandMath", "-il", $scene.FullName, "-exp", "(im1b2-im1b8)/(im1b2+im1b8+0.0001)", "-out", $mndwi, "float")
    runotb -Args @("BandMath", "-il", $scene.FullName, "-exp", "((im1b8+im1b3)-(im1b7+im1b1))/((im1b8+im1b3)+(im1b7+im1b1)+0.0001)", "-out", $bsi, "float")

    runotb -Args @("BandMath", "-il", $scene.FullName, $ndvi, $mndwi, $bsi, "-exp", "((((((im1b1+im1b2+im1b3)/(im1b7+im1b8+0.0001))>$CloudVisNirRatioMin) and im2b1<$CloudNdviMax and im3b1<$CloudMndwiMax and im4b1<$CloudBsiMax) or ((((im1b1+im1b2+im1b3)/(im1b7+im1b8+0.0001))>$CloudVisNirRatioLooseMin) and im2b1<$CloudNdviLooseMax and im3b1<$CloudMndwiLooseMax))?1:0)", "-out", $cloud, "uint8")
    runotb -Args @("BandMath", "-il", $ndvi, $mndwi, $bsi, $cloud, "-exp", "(im4b1==1)?255:((im2b1>$WaterMndwi and im1b1<$WaterNdviMax)?1:0)", "-out", $water, "uint8")
    runotb -Args @("BandMath", "-il", $ndvi, $cloud, "-exp", "(im2b1==1)?255:((im1b1>$VegetationNdvi)?1:0)", "-out", $vegetation, "uint8")
    runotb -Args @("BandMath", "-il", $ndvi, $mndwi, $bsi, $cloud, "-exp", "(im4b1==1)?255:((im3b1>$BareBsi and im2b1<$BareMndwiMax)?1:0)", "-out", $bare, "uint8")

    if ($ApplySinglePixelCleanup) {
        $radius = [Math]::Max(1, $CleanupRadius)
        $cloudClean = Join-Path $sceneOut ("{0}_cloud_mask_clean.tif" -f $dateLabel)
        Invoke-BinaryOpening -InputBinary $cloud -OutputBinary $cloudClean -Radius $radius
        Move-Item -Path $cloudClean -Destination $cloud -Force

        runotb -Args @("BandMath", "-il", $ndvi, $mndwi, $bsi, $cloud, "-exp", "(im4b1==1 or im1b1<=-9990 or im2b1<=-9990 or im3b1<=-9990)?255:((im2b1>$WaterMndwi and im1b1<$WaterNdviMax)?1:0)", "-out", $water, "uint8")
        runotb -Args @("BandMath", "-il", $ndvi, $cloud, "-exp", "(im2b1==1 or im1b1<=-9990)?255:((im1b1>$VegetationNdvi)?1:0)", "-out", $vegetation, "uint8")
        runotb -Args @("BandMath", "-il", $ndvi, $mndwi, $bsi, $cloud, "-exp", "(im4b1==1 or im1b1<=-9990 or im2b1<=-9990 or im3b1<=-9990)?255:((im3b1>$BareBsi and im2b1<$BareMndwiMax)?1:0)", "-out", $bare, "uint8")

        $waterBin = Join-Path $sceneOut ("{0}_water_mask_bin.tif" -f $dateLabel)
        $waterOpen = Join-Path $sceneOut ("{0}_water_mask_open.tif" -f $dateLabel)
        $waterTmp = Join-Path $sceneOut ("{0}_water_mask_tmp.tif" -f $dateLabel)
        $bareBin = Join-Path $sceneOut ("{0}_bare_sediment_mask_bin.tif" -f $dateLabel)
        $bareOpen = Join-Path $sceneOut ("{0}_bare_sediment_mask_open.tif" -f $dateLabel)
        $bareTmp = Join-Path $sceneOut ("{0}_bare_sediment_mask_tmp.tif" -f $dateLabel)

        runotb -Args @("BandMath", "-il", $water, "-exp", "(im1b1==1)?1:0", "-out", $waterBin, "uint8")
        runotb -Args @("BandMath", "-il", $bare, "-exp", "(im1b1==1)?1:0", "-out", $bareBin, "uint8")

        openbin -InputBinary $waterBin -OutputBinary $waterOpen -Radius $radius
        openbin -InputBinary $bareBin -OutputBinary $bareOpen -Radius $radius

        runotb -Args @("BandMath", "-il", $water, $waterOpen, "-exp", "(im1b1==255)?255:im2b1", "-out", $waterTmp, "uint8")
        runotb -Args @("BandMath", "-il", $bare, $bareOpen, "-exp", "(im1b1==255)?255:im2b1", "-out", $bareTmp, "uint8")

        Move-Item -Path $waterTmp -Destination $water -Force
        Move-Item -Path $bareTmp -Destination $bare -Force

        Remove-Item -Path $waterBin, $waterOpen, $bareBin, $bareOpen, $waterTmp, $bareTmp -Force -ErrorAction SilentlyContinue
    }

    runotb -Args @("BandMath", "-il", $water, $bare, "-exp", "(im1b1==255 or im2b1==255)?255:((im1b1==1 or im2b1==1)?1:0)", "-out", $active, "uint8")
}

Write-Output "classification set to $OutputRoot"
