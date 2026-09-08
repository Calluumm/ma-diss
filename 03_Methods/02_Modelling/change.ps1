#paths for the classified maps, sets an output and grabs mask names
param(
    [string]$classifiedroot = "c:/Users/Student/Desktop/Masters/Dissertation/02_Data/02_Processed/Sentinel2_Geomorphology_OTB",
    [string]$outputroot = "c:/Users/Student/Desktop/Masters/Dissertation/02_Data/02_Processed/Sentinel2_ChangeFramework",
    [string[]]$masknames = @("water_mask", "vegetation_mask", "bare_sediment_mask", "channel_sediment_mask", "cloud_mask", "active_channel_mask"),
    [switch]$allmasks,
    [switch]$applymorphologycleanup,
    [int]$morphologyradius = 1,
    [int]$cloudbufferradius = 2
)

#live laugh love OTB, hardcoded as powershell didn't like my PATH very much
function runOtb {
    param([string[]]$Args)
    & $script:otbLauncher @Args
}

$script:otbLauncher = Get-Command otbApplicationLauncherCommandLine -ErrorAction SilentlyContinue
if ($null -eq $script:otbLauncher) {
    $fallbacks = @(
        "C:/Users/Student/Desktop/OTB/OTB-9.1.1-Win64/bin/otbApplicationLauncherCommandLine.exe",
        "C:/Program Files/OTB/bin/otbApplicationLauncherCommandLine.exe",
        "C:/OSGeo4W/bin/otbApplicationLauncherCommandLine.exe",
        "C:/OSGeo4W64/bin/otbApplicationLauncherCommandLine.exe"
    )
    foreach ($candidate in $fallbacks) {
        if (Test-Path $candidate) {
            $script:otbLauncher = $candidate
            break
        }
    }
}

$launcherdir = Split-Path $script:otbLauncher -Parent
$otbroot = Split-Path $launcherdir -Parent
$defaultappspath = Join-Path $otbroot "lib/otb/applications"
if ([string]::IsNullOrWhiteSpace($env:OTB_APPLICATION_PATH)) {
    $env:OTB_APPLICATION_PATH = $defaultappspath
}

#change run is going to loop between each adjacent date pair of classified maps and take one from the other to map the change
$scenedirs = @(
    Get-ChildItem -Path $classifiedroot -Directory |
    Where-Object { $_.Name -match '^\d{4}-\d{2}-\d{2}$' } |
    Sort-Object Name
)

$anchordate = $scenedirs[0].Name
$masklist = @(
    Get-ChildItem -Path (Join-Path $classifiedroot $anchordate) -Filter "${anchordate}_*_mask.tif" -File |
    ForEach-Object { $_.BaseName.Substring($anchordate.Length + 1) } |
    Sort-Object -Unique
)
if ($masklist.Count -eq 0) {
    $masklist = @($masknames)
}
if (-not $allmasks) {
    $masklist = @("water_mask")
}
#does above here basically just grabs per mask and scene
for ($i = 0; $i -lt ($scenedirs.Count - 1); $i++) {
    $pre = $scenedirs[$i].Name
    $post = $scenedirs[$i + 1].Name
    foreach ($mask in $masklist) {
        $preMask = Join-Path (Join-Path $classifiedroot $pre) ("{0}_{1}.tif" -f $pre, $mask)
        $postMask = Join-Path (Join-Path $classifiedroot $post) ("{0}_{1}.tif" -f $post, $mask)
        $pairdir = Join-Path (Join-Path $outputroot $mask) ("{0}_to_{1}" -f $pre, $post)
        New-Item -ItemType Directory -Path $pairdir -Force | Out-Null

        $preUse = $preMask
        $postUse = $postMask

        if ($mask -ne "cloud_mask") {
            $preCloud = Join-Path (Join-Path $classifiedroot $pre) ("{0}_cloud_mask.tif" -f $pre)
            $postCloud = Join-Path (Join-Path $classifiedroot $post) ("{0}_cloud_mask.tif" -f $post)
            if ((Test-Path $preCloud) -and (Test-Path $postCloud)) {
                $preCloudFiltered = Join-Path $pairdir "${pre}_${mask}_nocloud.tif"
                $postCloudFiltered = Join-Path $pairdir "${post}_${mask}_nocloud.tif"
                $preCloudUse = $preCloud
                $postCloudUse = $postCloud

                if ($cloudbufferradius -gt 0) {
                    $cloudRadius = [Math]::Max(1, $cloudbufferradius)
                    $preCloudBin = Join-Path $pairdir ("_tmp_cloudbin_{0}.tif" -f $pre)
                    $postCloudBin = Join-Path $pairdir ("_tmp_cloudbin_{0}.tif" -f $post)
                    $preCloudDil = Join-Path $pairdir ("_tmp_clouddil_{0}.tif" -f $pre)
                    $postCloudDil = Join-Path $pairdir ("_tmp_clouddil_{0}.tif" -f $post)

                    runOtb -Args @("BandMath", "-il", $preCloud, "-exp", "(im1b1!=0)?1:0", "-out", $preCloudBin, "uint8")
                    runOtb -Args @("BandMath", "-il", $postCloud, "-exp", "(im1b1!=0)?1:0", "-out", $postCloudBin, "uint8")
                    runOtb -Args @("BinaryMorphologicalOperation", "-in", $preCloudBin, "-channel", "1", "-structype", "box", "-xradius", $cloudRadius, "-yradius", $cloudRadius, "-foreval", "1", "-backval", "0", "-filter", "dilate", "-out", $preCloudDil, "uint8")
                    runOtb -Args @("BinaryMorphologicalOperation", "-in", $postCloudBin, "-channel", "1", "-structype", "box", "-xradius", $cloudRadius, "-yradius", $cloudRadius, "-foreval", "1", "-backval", "0", "-filter", "dilate", "-out", $postCloudDil, "uint8")
                    $preCloudUse = $preCloudDil
                    $postCloudUse = $postCloudDil
                }

                runOtb -Args @("BandMath", "-il", $preUse, $preCloudUse, $postCloudUse, "-exp", "(im2b1==1 or im3b1==1)?255:im1b1", "-out", $preCloudFiltered, "uint8")
                runOtb -Args @("BandMath", "-il", $postUse, $preCloudUse, $postCloudUse, "-exp", "(im2b1==1 or im3b1==1)?255:im1b1", "-out", $postCloudFiltered, "uint8")
                Remove-Item -Path (Join-Path $pairdir "_tmp_cloudbin_*.tif"), (Join-Path $pairdir "_tmp_clouddil_*.tif") -Force
                $preUse = $preCloudFiltered
                $postUse = $postCloudFiltered
            }
        }

        #erosion, accretion and no change maps made for each mask for each scene pair
        $erosion = Join-Path $pairdir "erosion_${pre}_to_${post}.tif"
        $accretion = Join-Path $pairdir "accretion_${pre}_to_${post}.tif"
        $noChange = Join-Path $pairdir "nochange_${pre}_to_${post}.tif"
        $changeClass = Join-Path $pairdir "change_class_${pre}_to_${post}.tif"

        runOtb -Args @("BandMath", "-il", $preUse, $postUse, "-exp", "(im1b1!=255 and im2b1!=255 and im1b1==0 and im2b1==1)?1:0", "-out", $erosion, "uint8")
        runOtb -Args @("BandMath", "-il", $preUse, $postUse, "-exp", "(im1b1!=255 and im2b1!=255 and im1b1==1 and im2b1==0)?1:0", "-out", $accretion, "uint8")
        runOtb -Args @("BandMath", "-il", $preUse, $postUse, "-exp", "(im1b1!=255 and im2b1!=255 and im1b1==im2b1)?1:0", "-out", $noChange, "uint8")
        runOtb -Args @("BandMath", "-il", $preUse, $postUse, "-exp", "(im1b1==255 or im2b1==255)?255:((im1b1==0 and im2b1==1)?1:((im1b1==1 and im2b1==0)?2:0))", "-out", $changeClass, "uint8")
    }
}

#opt/arg for cleaning single pixel noise; proved not very useful in this workflow as it never really happened
if ($applymorphologycleanup) {
    $datenames = @($scenedirs | Select-Object -ExpandProperty Name)
    foreach ($mask in $masklist) {
        foreach ($i in 0..($datenames.Count - 2)) {
            $pre = $datenames[$i]
            $post = $datenames[$i + 1]
            $pairDir = Join-Path (Join-Path $outputroot $mask) ("{0}_to_{1}" -f $pre, $post)
            $source = Join-Path $pairDir ("change_class_{0}_to_{1}.tif" -f $pre, $post)
            $structRadius = [Math]::Max(1, $morphologyradius)
            if (Test-Path $source) {
                $c1bin = Join-Path $pairDir ("_tmp_c1_{0}_to_{1}.tif" -f $pre, $post)
                $c2bin = Join-Path $pairDir ("_tmp_c2_{0}_to_{1}.tif" -f $pre, $post)
                $c1open = Join-Path $pairDir ("_tmp_c1open_{0}_to_{1}.tif" -f $pre, $post)
                $c2open = Join-Path $pairDir ("_tmp_c2open_{0}_to_{1}.tif" -f $pre, $post)
                $clean = Join-Path $pairDir ("change_class_clean_{0}_to_{1}.tif" -f $pre, $post)

                runOtb -Args @("BandMath", "-il", $source, "-exp", "(im1b1==1)?1:0", "-out", $c1bin, "uint8")
                runOtb -Args @("BandMath", "-il", $source, "-exp", "(im1b1==2)?1:0", "-out", $c2bin, "uint8")
                runOtb -Args @("BinaryMorphologicalOperation", "-in", $c1bin, "-channel", "1", "-structype", "box", "-xradius", $structRadius, "-yradius", $structRadius, "-foreval", "1", "-backval", "0", "-filter", "opening", "-out", $c1open, "uint8")
                runOtb -Args @("BinaryMorphologicalOperation", "-in", $c2bin, "-channel", "1", "-structype", "box", "-xradius", $structRadius, "-yradius", $structRadius, "-foreval", "1", "-backval", "0", "-filter", "opening", "-out", $c2open, "uint8")
                runOtb -Args @("BandMath", "-il", $source, $c1open, $c2open, "-exp", "(im1b1==255)?255:((im1b1==1 and im2b1==1)?1:((im1b1==2 and im3b1==1)?2:0))", "-out", $clean, "uint8")
                Remove-Item -Path $c1bin, $c2bin, $c1open, $c2open -Force
            }
        }
    }
}

#spits it out into that path (from cd)
$latestdir = Join-Path $outputroot "latest_masks"
New-Item -ItemType Directory -Path $latestdir -Force | Out-Null
$latestdate = $scenedirs[$scenedirs.Count - 1].Name
foreach ($mask in $masklist) {
    $latestmask = Join-Path (Join-Path $classifiedroot $latestdate) ("{0}_{1}.tif" -f $latestdate, $mask)
    if (Test-Path $latestmask) {
        Copy-Item -Path $latestmask -Destination (Join-Path $latestdir ("latest_{0}.tif" -f $mask)) -Force
    }
}

Write-Output "change fraework complete $OutputRoot"
