param(
    [string]$InputRoot = "c:/input",
    [string]$OutputRoot = "c:/output",
    [double]$WaterMndwi = 0.05,
    [double]$WaterNdwi = 0.02,
    [double]$WaterNdviMax = 0.20,
    [double]$WaterBsiMax = 0.05,
    [double]$WaterVisMeanMax = 0.22,
    [double]$WaterProtectNdviMax = 0.32,
    [double]$WaterProtectMndwiMin = -0.08,
    [double]$WaterProtectNdwiMin = -0.03,
    [double]$VegetationNdvi = 0.30,
    [double]$BareBsi = 0.05,
    [double]$BareMndwiMax = 0.00,
    [double]$BareNdwiMax = -0.02,
    [double]$CloudVisMeanMin = 0.23,
    [double]$CloudCoreVisMeanMin = 0.30,
    [double]$CloudNdviMax = 0.20,
    [double]$CloudMndwiMax = 0.05,
    [double]$CloudSwirMin = 0.20,
    [double]$CloudCirrusMin = 0.15,
    [double]$CloudBsiMax = 0.25,
    [double]$ReflectanceScale = 10000.0,
    [bool]$ApplyStreamPrior = $true,
    [string]$StreamPriorVector = "c:/stream outline shapefile",
    [int]$StreamPriorRadius = 2,
    [double]$StreamPriorNdviMax = 0.28,
    [double]$StreamPriorMndwiMin = -0.12,
    [double]$StreamPriorNdwiMin = -0.03,
    [double]$StreamPriorBsiMax = 0.10,
    [double]$StreamPriorVisMeanMax = 0.22,
    [int]$StreamPriorCloudExclusionRadius = 1,
    [double]$SedimentPriorNdviMax = 0.22,
    [double]$SedimentPriorMndwiMax = 0.04,
    [double]$SedimentPriorBsiMin = 0.02,
    [double]$SedimentPriorBsiMax = 0.22,
    [double]$SedimentPriorVisMeanMax = 0.32,
    [bool]$ApplyChannelContinuityRecovery = $true,
    [int]$ChannelContinuityRadius = 1,
    [bool]$ApplyWaterEdgeRecovery = $true,
    [int]$WaterEdgeRadius = 1,
    [double]$WaterEdgeNdviMax = 0.30,
    [double]$WaterEdgeMndwiMin = -0.15,
    [double]$WaterEdgeNdwiMin = -0.03,
    [bool]$ApplySinglePixelCleanup = $true,
    [int]$CleanupRadius = 1
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function gettool {
    param([string]$Name)

    $cmd = Get-Command $Name -ErrorAction SilentlyContinue
    if ($null -ne $cmd) {
        return $cmd.Source
    }

    # Fallback for common local OTB installs when PATH is not configured.
    if ($Name -eq "otbApplicationLauncherCommandLine") {
        $fallbacks = @(
            "C:/Users/Student/Desktop/OTB/OTB-9.1.1-Win64/bin/otbApplicationLauncherCommandLine.exe"
        )

        foreach ($candidate in $fallbacks) {
            if (Test-Path $candidate) {
                return $candidate
            }
        }
    }

    if ($null -eq $cmd) {
        throw "missing $Name"
    }
    return $cmd.Source
}

function runotb {
    param([Parameter(Mandatory = $true)][string[]]$Args)
    & $script:otbLauncher @Args
    if ($LASTEXITCODE -ne 0) {
        throw "OTB failed omn run"
    }
}

function dilatebin {
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
        "-filter", "dilate",
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

$useStreamPrior = $ApplyStreamPrior -and (Test-Path $StreamPriorVector)
if ($ApplyStreamPrior -and (-not $useStreamPrior)) {
    Write-Warning "stream not found: $StreamPriorVector"
}

foreach ($scene in $scenes) {
    $dateLabel = $scene.BaseName
    $sceneOut = Join-Path $OutputRoot $dateLabel
    New-Item -ItemType Directory -Path $sceneOut -Force | Out-Null

    $ndvi = Join-Path $sceneOut "${dateLabel}_ndvi.tif"
    $ndwi = Join-Path $sceneOut "${dateLabel}_ndwi.tif"
    $mndwi = Join-Path $sceneOut "${dateLabel}_mndwi.tif"
    $bsi = Join-Path $sceneOut "${dateLabel}_bsi.tif"

    $water = Join-Path $sceneOut "${dateLabel}_water_mask.tif"
    $waterCandidate = Join-Path $sceneOut "${dateLabel}_water_candidate_mask.tif"
    $waterProtect = Join-Path $sceneOut "${dateLabel}_water_protect_mask.tif"
    $vegetation = Join-Path $sceneOut "${dateLabel}_vegetation_mask.tif"
    $bare = Join-Path $sceneOut "${dateLabel}_bare_sediment_mask.tif"
    $cloud = Join-Path $sceneOut "${dateLabel}_cloud_mask.tif"
    $cloudRaw = Join-Path $sceneOut "${dateLabel}_cloud_mask_raw.tif"
    $cloudCore = Join-Path $sceneOut "${dateLabel}_cloud_mask_core.tif"
    $active = Join-Path $sceneOut "${dateLabel}_active_channel_mask.tif"
    $classmap = Join-Path $sceneOut "${dateLabel}_class_map.tif"

    runotb -Args @("BandMath", "-il", $scene.FullName, "-exp", "(im1b7-im1b3)/(im1b7+im1b3+0.0001)", "-out", $ndvi, "float")
    runotb -Args @("BandMath", "-il", $scene.FullName, "-exp", "(im1b2-im1b7)/(im1b2+im1b7+0.0001)", "-out", $ndwi, "float")
    runotb -Args @("BandMath", "-il", $scene.FullName, "-exp", "(im1b2-im1b8)/(im1b2+im1b8+0.0001)", "-out", $mndwi, "float")
    runotb -Args @("BandMath", "-il", $scene.FullName, "-exp", "((im1b8+im1b3)-(im1b7+im1b1))/((im1b8+im1b3)+(im1b7+im1b1)+0.0001)", "-out", $bsi, "float")

    runotb -Args @("BandMath", "-il", $scene.FullName, $ndvi, $mndwi, $ndwi, $bsi, "-exp", "(((im3b1>$WaterMndwi or im4b1>$WaterNdwi) and im2b1<$WaterNdviMax and im5b1<$WaterBsiMax and (((im1b1+im1b2+im1b3)/3.0)/$ReflectanceScale)<$WaterVisMeanMax)?1:0)", "-out", $waterCandidate, "uint8")
    runotb -Args @("BandMath", "-il", $ndvi, $mndwi, $ndwi, "-exp", "((im1b1<$WaterProtectNdviMax and (im2b1>$WaterProtectMndwiMin or im3b1>$WaterProtectNdwiMin))?1:0)", "-out", $waterProtect, "uint8")
    runotb -Args @("BandMath", "-il", $scene.FullName, $ndvi, $mndwi, $bsi, "-exp", "(((((im1b1+im1b2+im1b3)/3.0)/$ReflectanceScale)>$CloudVisMeanMin) and ((im1b8/$ReflectanceScale)>$CloudSwirMin and (im1b9/$ReflectanceScale)>$CloudCirrusMin) and im2b1<$CloudNdviMax and im3b1<$CloudMndwiMax and im4b1<$CloudBsiMax)?1:0", "-out", $cloudRaw, "uint8")
    runotb -Args @("BandMath", "-il", $scene.FullName, "-exp", "(((((im1b1+im1b2+im1b3)/3.0)/$ReflectanceScale)>$CloudCoreVisMeanMin) and ((im1b8/$ReflectanceScale)>$CloudSwirMin and (im1b9/$ReflectanceScale)>$CloudCirrusMin))?1:0", "-out", $cloudCore, "uint8")
    runotb -Args @("BandMath", "-il", $cloudCore, $cloudRaw, $waterProtect, "-exp", "(im1b1==1)?1:((im2b1==1 and im3b1==0)?1:0)", "-out", $cloud, "uint8")
    runotb -Args @("BandMath", "-il", $waterCandidate, $cloud, "-exp", "(im2b1==1)?255:im1b1", "-out", $water, "uint8")
    runotb -Args @("BandMath", "-il", $ndvi, $cloud, "-exp", "(im2b1==1)?255:((im1b1>$VegetationNdvi)?1:0)", "-out", $vegetation, "uint8")
    runotb -Args @("BandMath", "-il", $ndvi, $mndwi, $bsi, $ndwi, $cloud, "-exp", "(im5b1==1)?255:((im3b1>$BareBsi and im2b1<$BareMndwiMax and im4b1<$BareNdwiMax)?1:0)", "-out", $bare, "uint8")

    Remove-Item -Path $waterCandidate, $waterProtect, $cloudRaw, $cloudCore -Force -ErrorAction SilentlyContinue

    runotb -Args @(
        "BandMath",
        "-il", $water, $vegetation, $bare, $cloud,
        "-exp", "(im4b1==1)?4:((im1b1==255 or im2b1==255 or im3b1==255)?255:((im1b1==1)?1:((im2b1==1)?2:((im3b1==1)?3:0))))",
        "-out", $classmap, "uint8"
    )

    if ($ApplyWaterEdgeRecovery) {
        $edgeRadius = [Math]::Max(1, $WaterEdgeRadius)
        $waterSeed = Join-Path $sceneOut ("{0}_water_seed_bin.tif" -f $dateLabel)
        $waterSeedDil = Join-Path $sceneOut ("{0}_water_seed_dil.tif" -f $dateLabel)
        $classRecovered = Join-Path $sceneOut ("{0}_class_map_recovered.tif" -f $dateLabel)

        runotb -Args @("BandMath", "-il", $classmap, "-exp", "(im1b1==1)?1:0", "-out", $waterSeed, "uint8")
        dilatebin -InputBinary $waterSeed -OutputBinary $waterSeedDil -Radius $edgeRadius

        runotb -Args @(
            "BandMath",
            "-il", $classmap, $cloud, $ndvi, $mndwi, $ndwi, $waterSeedDil,
                "-exp", "(im2b1==1 or im1b1==255)?im1b1:((im1b1==0 and im6b1==1 and im3b1<$WaterEdgeNdviMax and (im4b1>$WaterEdgeMndwiMin or im5b1>$WaterEdgeNdwiMin))?1:im1b1)",
            "-out", $classRecovered, "uint8"
        )

        Move-Item -Path $classRecovered -Destination $classmap -Force
        Remove-Item -Path $waterSeed, $waterSeedDil, $classRecovered -Force -ErrorAction SilentlyContinue
    }

    if ($useStreamPrior) {
        $streamRadius = [Math]::Max(1, $StreamPriorRadius)
        $cloudExRadius = [Math]::Max(0, $StreamPriorCloudExclusionRadius)
        $streamPriorRaw = Join-Path $sceneOut ("{0}_stream_prior_raw.tif" -f $dateLabel)
        $streamPriorDil = Join-Path $sceneOut ("{0}_stream_prior_dil.tif" -f $dateLabel)
        $cloudPriorEx = Join-Path $sceneOut ("{0}_cloud_prior_exclusion.tif" -f $dateLabel)
        $classStream = Join-Path $sceneOut ("{0}_class_map_stream_prior.tif" -f $dateLabel)
        $waterNear = Join-Path $sceneOut ("{0}_stream_water_near.tif" -f $dateLabel)
        $waterNearDil = Join-Path $sceneOut ("{0}_stream_water_near_dil.tif" -f $dateLabel)
        $bareNear = Join-Path $sceneOut ("{0}_stream_bare_near.tif" -f $dateLabel)
        $bareNearDil = Join-Path $sceneOut ("{0}_stream_bare_near_dil.tif" -f $dateLabel)
        $classContinuity = Join-Path $sceneOut ("{0}_class_map_continuity.tif" -f $dateLabel)

        runotb -Args @(
            "Rasterization",
            "-in", $StreamPriorVector,
            "-im", $scene.FullName,
            "-background", "0",
            "-mode", "binary",
            "-mode.binary.foreground", "1",
            "-out", $streamPriorRaw, "uint8"
        )

        dilatebin -InputBinary $streamPriorRaw -OutputBinary $streamPriorDil -Radius $streamRadius

        if ($cloudExRadius -gt 0) {
            dilatebin -InputBinary $cloud -OutputBinary $cloudPriorEx -Radius $cloudExRadius
        }
        else {
            runotb -Args @("BandMath", "-il", $cloud, "-exp", "im1b1", "-out", $cloudPriorEx, "uint8")
        }

        runotb -Args @(
            "BandMath",
            "-il", $classmap, $streamPriorDil, $ndvi, $mndwi, $ndwi, $bsi, $cloudPriorEx, $scene.FullName,
            "-exp", "(im1b1==255)?255:((im1b1==4)?4:((im1b1==0 and im2b1==1 and im7b1==0 and im3b1<$StreamPriorNdviMax and im6b1<$StreamPriorBsiMax and (((im8b1+im8b2+im8b3)/3.0)/$ReflectanceScale)<$StreamPriorVisMeanMax and (im4b1>$StreamPriorMndwiMin or im5b1>$StreamPriorNdwiMin))?1:((im1b1==0 and im2b1==1 and im7b1==0 and im3b1<$SedimentPriorNdviMax and im4b1<$SedimentPriorMndwiMax and im6b1>$SedimentPriorBsiMin and im6b1<$SedimentPriorBsiMax and (((im8b1+im8b2+im8b3)/3.0)/$ReflectanceScale)<$SedimentPriorVisMeanMax)?3:im1b1)))",
            "-out", $classStream, "uint8"
        )

        if ($ApplyChannelContinuityRecovery) {
            $continuityRadius = [Math]::Max(1, $ChannelContinuityRadius)

            runotb -Args @("BandMath", "-il", $classStream, "-exp", "(im1b1==1)?1:0", "-out", $waterNear, "uint8")
            runotb -Args @("BandMath", "-il", $classStream, "-exp", "(im1b1==3)?1:0", "-out", $bareNear, "uint8")
            dilatebin -InputBinary $waterNear -OutputBinary $waterNearDil -Radius $continuityRadius
            dilatebin -InputBinary $bareNear -OutputBinary $bareNearDil -Radius $continuityRadius

            runotb -Args @(
                "BandMath",
                "-il", $classStream, $streamPriorDil, $ndvi, $mndwi, $ndwi, $bsi, $cloudPriorEx, $scene.FullName, $waterNearDil, $bareNearDil,
                "-exp", "(im1b1==255)?255:((im1b1==4)?4:((im1b1==0 and im2b1==1 and im7b1==0 and im9b1==1 and im10b1==0 and im3b1<$StreamPriorNdviMax and im6b1<$StreamPriorBsiMax and (((im8b1+im8b2+im8b3)/3.0)/$ReflectanceScale)<$StreamPriorVisMeanMax and (im4b1>$StreamPriorMndwiMin or im5b1>$StreamPriorNdwiMin))?1:((im1b1==0 and im2b1==1 and im7b1==0 and im10b1==1 and im9b1==0 and im3b1<$SedimentPriorNdviMax and im4b1<$SedimentPriorMndwiMax and im6b1>$SedimentPriorBsiMin and im6b1<$SedimentPriorBsiMax and (((im8b1+im8b2+im8b3)/3.0)/$ReflectanceScale)<$SedimentPriorVisMeanMax)?3:((im1b1==0 and im2b1==1 and im7b1==0 and im9b1==1 and im10b1==1)?((im3b1<$StreamPriorNdviMax and im6b1<$StreamPriorBsiMax and (((im8b1+im8b2+im8b3)/3.0)/$ReflectanceScale)<$StreamPriorVisMeanMax and (im4b1>$StreamPriorMndwiMin or im5b1>$StreamPriorNdwiMin))?1:((im3b1<$SedimentPriorNdviMax and im4b1<$SedimentPriorMndwiMax and im6b1>$SedimentPriorBsiMin and im6b1<$SedimentPriorBsiMax and (((im8b1+im8b2+im8b3)/3.0)/$ReflectanceScale)<$SedimentPriorVisMeanMax)?3:im1b1)):im1b1))))",
                "-out", $classContinuity, "uint8"
            )

            Move-Item -Path $classContinuity -Destination $classmap -Force
        }
        else {
            Move-Item -Path $classStream -Destination $classmap -Force
        }

        Remove-Item -Path $streamPriorRaw, $streamPriorDil, $cloudPriorEx, $classStream, $waterNear, $waterNearDil, $bareNear, $bareNearDil, $classContinuity -Force -ErrorAction SilentlyContinue
    }

    if ($ApplySinglePixelCleanup) {
        $cleanupRad = [Math]::Max(1, $CleanupRadius)
        $waterSeed = Join-Path $sceneOut ("{0}_cleanup_water_seed.tif" -f $dateLabel)
        $waterSeedDil = Join-Path $sceneOut ("{0}_cleanup_water_seed_dil.tif" -f $dateLabel)
        $bareSeed = Join-Path $sceneOut ("{0}_cleanup_bare_seed.tif" -f $dateLabel)
        $bareSeedDil = Join-Path $sceneOut ("{0}_cleanup_bare_seed_dil.tif" -f $dateLabel)
        $classClean = Join-Path $sceneOut ("{0}_class_map_cleanup.tif" -f $dateLabel)

        runotb -Args @("BandMath", "-il", $classmap, "-exp", "(im1b1==1)?1:0", "-out", $waterSeed, "uint8")
        runotb -Args @("BandMath", "-il", $classmap, "-exp", "(im1b1==3)?1:0", "-out", $bareSeed, "uint8")

        dilatebin -InputBinary $waterSeed -OutputBinary $waterSeedDil -Radius $cleanupRad
        dilatebin -InputBinary $bareSeed -OutputBinary $bareSeedDil -Radius $cleanupRad

        runotb -Args @(
            "BandMath",
            "-il", $classmap, $cloud, $ndvi, $mndwi, $ndwi, $bsi, $waterSeedDil, $bareSeedDil,
            "-exp", "(im1b1==255 or im1b1==4)?im1b1:((im1b1==3 and im2b1==0 and im7b1==1 and im3b1<$WaterEdgeNdviMax and (im4b1>$WaterEdgeMndwiMin or im5b1>$WaterEdgeNdwiMin))?1:((im1b1==0 and im2b1==0 and im7b1==1 and im3b1<$WaterEdgeNdviMax and (im4b1>$WaterEdgeMndwiMin or im5b1>$WaterEdgeNdwiMin))?1:((im1b1==0 and im2b1==0 and im8b1==1 and im3b1<$SedimentPriorNdviMax and im4b1<$SedimentPriorMndwiMax and im6b1>$SedimentPriorBsiMin and im6b1<$SedimentPriorBsiMax)?3:im1b1)))",
            "-out", $classClean, "uint8"
        )

        Move-Item -Path $classClean -Destination $classmap -Force
        Remove-Item -Path $waterSeed, $waterSeedDil, $bareSeed, $bareSeedDil, $classClean -Force -ErrorAction SilentlyContinue
    }

    runotb -Args @("BandMath", "-il", $classmap, "-exp", "(im1b1==4)?255:((im1b1==1)?1:0)", "-out", $water, "uint8")
    runotb -Args @("BandMath", "-il", $classmap, "-exp", "(im1b1==4)?255:((im1b1==2)?1:0)", "-out", $vegetation, "uint8")
    runotb -Args @("BandMath", "-il", $classmap, "-exp", "(im1b1==4)?255:((im1b1==3)?1:0)", "-out", $bare, "uint8")
    runotb -Args @("BandMath", "-il", $classmap, "-exp", "(im1b1==4)?1:0", "-out", $cloud, "uint8")
    runotb -Args @("BandMath", "-il", $classmap, "-exp", "(im1b1==4)?255:((im1b1==1 or im1b1==3)?1:0)", "-out", $active, "uint8")
}

Write-Output "classification set to $OutputRoot"
