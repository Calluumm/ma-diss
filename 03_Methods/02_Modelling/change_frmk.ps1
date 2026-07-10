param(
    [string]$ClassifiedRoot = "c:/input (classified images from the classifier script)",
    [string]$OutputRoot = "c:/output",
    [string[]]$MaskNames = @("water_mask", "vegetation_mask", "bare_sediment_mask", "cloud_mask", "active_channel_mask"),
    [switch]$AllMasks,
    [switch]$ApplyMorphologyCleanup,
    [int]$MorphologyRadius = 1,
    [int]$CloudBufferRadius = 2
)
#make sure to run in strict mode or otb will not like you one bit
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function gettool {
    param([string]$Name)
    $cmd = Get-Command $Name -ErrorAction SilentlyContinue
    if ($null -ne $cmd) {
        if ($cmd.PSObject.Properties.Name -contains "Source" -and -not [string]::IsNullOrWhiteSpace($cmd.Source)) {
            return $cmd.Source
        }
        if ($cmd.PSObject.Properties.Name -contains "Path" -and -not [string]::IsNullOrWhiteSpace($cmd.Path)) {
            return $cmd.Path
        }
    }
#hash out if running in a normal place lol
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

    throw "missing $Name"
}
function runotb {
    param([Parameter(Mandatory = $true)][string[]]$Args)
    & $script:otbLauncher @Args
    if ($LASTEXITCODE -ne 0) {
        throw "OTB failed on run"
    }
}

function maskpath {
    param(
        [Parameter(Mandatory = $true)][string]$Root,
        [Parameter(Mandatory = $true)][string]$Date,
        [Parameter(Mandatory = $true)][string]$Mask
    )

    return (Join-Path (Join-Path $Root $Date) ("{0}_{1}.tif" -f $Date, $Mask))
}

function masklist {
    param(
        [Parameter(Mandatory = $true)][string]$Root,
        [Parameter(Mandatory = $true)][string]$Date,
        [string[]]$DefaultMasks
    )

    $dir = Join-Path $Root $Date
    $files = @(Get-ChildItem -Path $dir -Filter "${Date}_*_mask.tif" -File -ErrorAction SilentlyContinue)
    $resolved = @()

    foreach ($f in $files) {
        $name = $f.BaseName
        $prefix = "${Date}_"
        if ($name.StartsWith($prefix)) {
            $resolved += $name.Substring($prefix.Length)
        }
    }

    if ($resolved.Count -eq 0) {
        return @($DefaultMasks)
    }

    return @($resolved | Sort-Object -Unique)
}

function buildpair {
    param(
        [Parameter(Mandatory = $true)][string]$Mask,
        [Parameter(Mandatory = $true)][string]$Pre,
        [Parameter(Mandatory = $true)][string]$Post,
        [Parameter(Mandatory = $true)][string]$OutDir
    )

    $preMask = maskpath -Root $ClassifiedRoot -Date $Pre -Mask $Mask
    $postMask = maskpath -Root $ClassifiedRoot -Date $Post -Mask $Mask
    if (-not (Test-Path $preMask)) { throw "pre mask missing $preMask" }
    if (-not (Test-Path $postMask)) { throw "post mask missing $postMask" }

    New-Item -ItemType Directory -Path $OutDir -Force | Out-Null

    $preUse = $preMask
    $postUse = $postMask

    if ($Mask -ne "cloud_mask") {
        $preCloud = maskpath -Root $ClassifiedRoot -Date $Pre -Mask "cloud_mask"
        $postCloud = maskpath -Root $ClassifiedRoot -Date $Post -Mask "cloud_mask"
        if ((Test-Path $preCloud) -and (Test-Path $postCloud)) {
            $preCloudFiltered = Join-Path $OutDir "${Pre}_${Mask}_nocloud.tif"
            $postCloudFiltered = Join-Path $OutDir "${Post}_${Mask}_nocloud.tif"

            $preCloudUse = $preCloud
            $postCloudUse = $postCloud

            # Buffer cloud masks to suppress cloud-edge false changes.
            if ($CloudBufferRadius -gt 0) {
                $cloudRadius = [Math]::Max(1, $CloudBufferRadius)
                $preCloudBin = Join-Path $OutDir ("_tmp_cloudbin_{0}.tif" -f $Pre)
                $postCloudBin = Join-Path $OutDir ("_tmp_cloudbin_{0}.tif" -f $Post)
                $preCloudDil = Join-Path $OutDir ("_tmp_clouddil_{0}.tif" -f $Pre)
                $postCloudDil = Join-Path $OutDir ("_tmp_clouddil_{0}.tif" -f $Post)

                runotb -Args @("BandMath", "-il", $preCloud, "-exp", "(im1b1!=0)?1:0", "-out", $preCloudBin, "uint8")
                runotb -Args @("BandMath", "-il", $postCloud, "-exp", "(im1b1!=0)?1:0", "-out", $postCloudBin, "uint8")

                runotb -Args @(
                    "BinaryMorphologicalOperation",
                    "-in", $preCloudBin,
                    "-channel", "1",
                    "-structype", "box",
                    "-xradius", $cloudRadius,
                    "-yradius", $cloudRadius,
                    "-foreval", "1",
                    "-backval", "0",
                    "-filter", "dilate",
                    "-out", $preCloudDil, "uint8"
                )

                runotb -Args @(
                    "BinaryMorphologicalOperation",
                    "-in", $postCloudBin,
                    "-channel", "1",
                    "-structype", "box",
                    "-xradius", $cloudRadius,
                    "-yradius", $cloudRadius,
                    "-foreval", "1",
                    "-backval", "0",
                    "-filter", "dilate",
                    "-out", $postCloudDil, "uint8"
                )

                $preCloudUse = $preCloudDil
                $postCloudUse = $postCloudDil
            }

            #double cloud both dates, unable to discern underneath
            runotb -Args @("BandMath", "-il", $preUse, $preCloudUse, $postCloudUse, "-exp", "(im2b1==1 or im3b1==1)?255:im1b1", "-out", $preCloudFiltered, "uint8")
            runotb -Args @("BandMath", "-il", $postUse, $preCloudUse, $postCloudUse, "-exp", "(im2b1==1 or im3b1==1)?255:im1b1", "-out", $postCloudFiltered, "uint8")

            Remove-Item -Path (Join-Path $OutDir "_tmp_cloudbin_*.tif"), (Join-Path $OutDir "_tmp_clouddil_*.tif") -Force -ErrorAction SilentlyContinue

            $preUse = $preCloudFiltered
            $postUse = $postCloudFiltered
        }
        else {
            Write-Warning "cloud mask missing for $Mask at $Pre or $Post; using unfiltered masks"
        }
    }

    $erosion = Join-Path $OutDir "erosion_${Pre}_to_${Post}.tif"
    $accretion = Join-Path $OutDir "accretion_${Pre}_to_${Post}.tif"
    $noChange = Join-Path $OutDir "nochange_${Pre}_to_${Post}.tif"
    $changeClass = Join-Path $OutDir "change_class_${Pre}_to_${Post}.tif"

    runotb -Args @("BandMath", "-il", $preUse, $postUse, "-exp", "(im1b1!=255 and im2b1!=255 and im1b1==0 and im2b1==1)?1:0", "-out", $erosion, "uint8")
    runotb -Args @("BandMath", "-il", $preUse, $postUse, "-exp", "(im1b1!=255 and im2b1!=255 and im1b1==1 and im2b1==0)?1:0", "-out", $accretion, "uint8")
    runotb -Args @("BandMath", "-il", $preUse, $postUse, "-exp", "(im1b1!=255 and im2b1!=255 and im1b1==im2b1)?1:0", "-out", $noChange, "uint8")
    runotb -Args @("BandMath", "-il", $preUse, $postUse, "-exp", "(im1b1==255 or im2b1==255)?255:((im1b1==0 and im2b1==1)?1:((im1b1==1 and im2b1==0)?2:0))", "-out", $changeClass, "uint8")

}
function cleanup {
    param(
        [Parameter(Mandatory = $true)][string]$Mask,
        [Parameter(Mandatory = $true)][string[]]$Dates
    )

    if ($Dates.Count -lt 2) {
        return
    }

    $structRadius = [Math]::Max(1, $MorphologyRadius)

    for ($i = 0; $i -lt ($Dates.Count - 1); $i++) {
        $pre = $Dates[$i]
        $post = $Dates[$i + 1]

        $pairDir = Join-Path (Join-Path $OutputRoot $Mask) ("{0}_to_{1}" -f $pre, $post)
        $source = Join-Path $pairDir ("change_class_{0}_to_{1}.tif" -f $pre, $post)
        if (-not (Test-Path $source)) {
            continue
        }

        $c1bin = Join-Path $pairDir ("_tmp_c1_{0}_to_{1}.tif" -f $pre, $post)
        $c2bin = Join-Path $pairDir ("_tmp_c2_{0}_to_{1}.tif" -f $pre, $post)
        $c1open = Join-Path $pairDir ("_tmp_c1open_{0}_to_{1}.tif" -f $pre, $post)
        $c2open = Join-Path $pairDir ("_tmp_c2open_{0}_to_{1}.tif" -f $pre, $post)
        $clean = Join-Path $pairDir ("change_class_clean_{0}_to_{1}.tif" -f $pre, $post)

        runotb -Args @("BandMath", "-il", $source, "-exp", "(im1b1==1)?1:0", "-out", $c1bin, "uint8")
        runotb -Args @("BandMath", "-il", $source, "-exp", "(im1b1==2)?1:0", "-out", $c2bin, "uint8")

        runotb -Args @(
            "BinaryMorphologicalOperation",
            "-in", $c1bin,
            "-channel", "1",
            "-structype", "box",
            "-xradius", $structRadius,
            "-yradius", $structRadius,
            "-foreval", "1",
            "-backval", "0",
            "-filter", "opening",
            "-out", $c1open, "uint8"
        )

        runotb -Args @(
            "BinaryMorphologicalOperation",
            "-in", $c2bin,
            "-channel", "1",
            "-structype", "box",
            "-xradius", $structRadius,
            "-yradius", $structRadius,
            "-foreval", "1",
            "-backval", "0",
            "-filter", "opening",
            "-out", $c2open, "uint8"
        )

        runotb -Args @(
            "BandMath", "-il", $source, $c1open, $c2open,
            "-exp", "(im1b1==255)?255:((im1b1==1 and im2b1==1)?1:((im1b1==2 and im3b1==1)?2:0))",
            "-out", $clean, "uint8"
        )

        Remove-Item -Path $c1bin, $c2bin, $c1open, $c2open -Force -ErrorAction SilentlyContinue
    }
}

$script:otbLauncher = gettool "otbApplicationLauncherCommandLine"

$launcherDir = Split-Path $script:otbLauncher -Parent
$otbRoot = Split-Path $launcherDir -Parent
$defaultAppsPath = Join-Path $otbRoot "lib/otb/applications"
if ([string]::IsNullOrWhiteSpace($env:OTB_APPLICATION_PATH) -and (Test-Path $defaultAppsPath)) {
    $env:OTB_APPLICATION_PATH = $defaultAppsPath
}

$sceneDirs = @(
    Get-ChildItem -Path $ClassifiedRoot -Directory |
        Where-Object {
            $_.Name -match '^\d{4}-\d{2}-\d{2}$' -and
            $_.Name -notmatch '(?i)_qa_mask$' -and
            $_.FullName -notmatch '(?i)[\\/]qa_masks([\\/]|$)'
        } |
        Sort-Object Name
)
if ($sceneDirs.Count -lt 2) {
    throw "need at least 2 dated classification folders in $ClassifiedRoot"
}

$anchorDate = $sceneDirs[0].Name
$maskList = @(masklist -Root $ClassifiedRoot -Date $anchorDate -DefaultMasks $MaskNames)
if ($maskList.Count -eq 0) {
    throw "no mask names resolved"
}

if (-not $AllMasks) {
    $maskList = @("water_mask")
}

for ($i = 0; $i -lt ($sceneDirs.Count - 1); $i++) {
    $pre = $sceneDirs[$i].Name
    $post = $sceneDirs[$i + 1].Name
    foreach ($mask in $maskList) {
        $pairDir = Join-Path (Join-Path $OutputRoot $mask) ("{0}_to_{1}" -f $pre, $post)
        Write-Output ("building change for {0}: {1} -> {2}" -f $mask, $pre, $post)
        buildpair -Mask $mask -Pre $pre -Post $post -OutDir $pairDir
    }
}

if ($ApplyMorphologyCleanup) {
    $dateNames = @($sceneDirs | Select-Object -ExpandProperty Name)
    foreach ($mask in $maskList) {
        Write-Output ("applying morphology cleanup" -f $mask, $MorphologyRadius)
        cleanup -Mask $mask -Dates $dateNames
    }
}

$latestDir = Join-Path $OutputRoot "latest_masks"
New-Item -ItemType Directory -Path $latestDir -Force | Out-Null
$latestDate = $sceneDirs[$sceneDirs.Count - 1].Name
foreach ($mask in $maskList) {
    $latestMask = maskpath -Root $ClassifiedRoot -Date $latestDate -Mask $mask
    if (Test-Path $latestMask) {
        Copy-Item -Path $latestMask -Destination (Join-Path $latestDir ("latest_{0}.tif" -f $mask)) -Force
    }
}

Write-Output "change fraework complete $OutputRoot"
