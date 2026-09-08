Set-StrictMode -Version Latest

#in/out
$inputroot = "c:/Users/Student/Desktop/Masters/Dissertation/02_Data/01_Raw/Scenes/Sentinel2/longtimeseries"
$outputroot = "c:/Users/Student/Desktop/Masters/Dissertation/02_Data/02_Processed/Sentinel2_Geomorphology_OTB"

#Okay so this is a long list of various thresholds used to tweak the classifiers sensitivity
#They are generally grouped by the class or index used by classifier 
#the boolean ones are specific functions that I turned on or off while controlling sensitivity and iterating, the ones I ended up sacking off are gone hence why they are all true
#While it looks quite convoluted and trust me it is, I was essentially checking the classified image then working on the thresholds around a specific feature I noticed was messing up, such as an interface between water and sediment
#A lot of them end up doing the same thing and just dragging the file length, I chose not to further refactor this as I wanted to keep the exact same values I ultimately settled on and I'm not sure that would have been
#the case if I tried to condense them down.
$watermndwi = 0.06
$waterndwi = 0.03
$waterndvimx = 0.20
$waterbsimx = 0.04
$watervismeanmx = 0.22
$waterprotectndvimx = 0.32
$waterprotectmndwimn = -0.08
$waterprotectndwimn = -0.03
$vegetationndvi = 0.30
$barebsi = 0.05
$baremndwimx = 0.00
$barendwimx = -0.02
$cloudvismeanmn = 0.23
$cloudcorevismeanmn = 0.30
$cloudndvimx = 0.20
$cloudmndwimx = 0.05
$cloudswirmn = 0.20
$cloudcirrusmn = 0.15
$cloudbsimx = 0.25
$useadaptivebrightness = $true
$adaptivescenevisreference = 0.18
$adaptivewatervissensitivity = 0.60
$adaptivewatervismeanfloor = 0.16
$adaptivewatervismeancap = 0.35
$adaptivecloudstdfactor = 1.00
$adaptivecloudoffset = 0.03
$adaptivecloudcoreoffset = 0.08
$reflectancescale = 10000.0
$applystreamp = $true
#stream shapefile itself when I manually lineated it to help with continuity "soft guide" if you will
$streampvector = "c:/Users/Student/Desktop/Masters/Dissertation/02_Data/01_Raw/manual stream/manual4326.shp"
$streampr = 2
$streampndvimx = 0.28
$streampmndwimn = -0.12
$streampndwimn = -0.03
$streampbsimx = 0.10
$streampvismeanmx = 0.22
$streampcloudexclusionr = 1
$sedimentpriorndvimx = 0.22
$sedimentpriormndwimx = 0.04
$sedimentpriorbsimn = 0.02
$sedimentpriorbsimx = 0.22
$sedimentpriorvismeanmx = 0.32
$inchannelsedimentndvimx = 0.35
$inchannelsedimentmndwimx = 0.14
$inchannelsedimentbsimn = -0.02
$inchannelsedimentbsimx = 0.36
$inchannelsedimentvismeanmx = 0.55
$inchannelsedimentadjndvimx = 0.45
$inchannelsedimentadjmndwimx = 0.30
$inchannelsedimentadjbsimx = 0.55
$inchannelsedimentadjvismeanmx = 0.65
$applychannelsedimentsplit = $true
$channelsedimentpriorr = 6
$channelsedimentwateradjacencyr = 4
$allowsedimentsplitwithoutwateradjacency = $true
$inchannelsedimentnoadjndvimx = 0.32
$inchannelsedimentnoadjmndwimx = 0.18
$inchannelsedimentnoadjbsimn = -0.05
$inchannelsedimentnoadjbsimx = 0.36
$inchannelsedimentnoadjvismeanmx = 0.60
$applywaterspksedimentcleanup = $false
$waterspkopeningr = 1
$waterspkchannelpriorr = 2
$waterspksedimentndvimx = 0.30
$waterspksedimentmndwimx = 0.08
$waterspksedimentbsimn = 0.00
$waterspksedimentvismeanmx = 0.36
$applychannelcntyrcvy = $true
$channelcntyr = 1
$applywateredgercvy = $true
$wateredger = 1
$wateredgendvimx = 0.24
$wateredgemndwimn = -0.08
$wateredgendwimn = 0.00
$applysinglepixelcleanup = $true
$cleanupr = 1
$applyunclassifiedrcvy = $true
$unclassifiedwateradjacencyr = 1
$unclassifiedchannelpriorr = 2
$unclassifiedsedimentndvimx = 0.30
$unclassifiedsedimentmndwimx = 0.10
$unclassifiedsedimentbsimn = -0.02
$unclassifiedsedimentvismeanmx = 0.38
$unclassifiedbarendvimx = 0.35
$unclassifiedbarebsimn = 0.01
$applyfinalclass0fallback = $true
$finalfallbackchannelpriorr = 3
$applybankclass0rcvy = $true
$bankrcvywaterr = 3
$bankrcvychannelr = 3
$bankrcvyndvimx = 0.42
$bankrcvymndwimx = 0.20
$bankrcvybsimn = -0.08
$bankrcvyvismeanmx = 0.45
$applywatercntyrcvy = $true
$watercntyr = 3
$watercntyndvimx = 0.28
$watercntymndwimn = -0.02
$watercntyndwimn = -0.01
$watercntyrecoverbare = $true
$watercntypriorr = 4
$watercntybarendvimx = 0.30
$watercntybaremndwimn = -0.10
$watercntybarendwimn = -0.04
$watercntybarebsimx = 0.16
$watercntybarevismeanmx = 0.40
$watercntyrecoverclass0 = $true
$watercntyclass0ndvimx = 0.34
$watercntyclass0mndwimn = -0.14
$watercntyclass0ndwimn = -0.08
$watercntyclass0bsimx = 0.16
$watercntyclass0vismeanmx = 0.42
$applywaterchannelclosing = $true
$waterchannelclosingr = 2
$waterchannelclosingpriorr = 4
$applydrychannelbridgercvy = $false
$drychannelbridgewatercloser = 4
$drychannelbridgepriorr = 3
$drychannelbridgendvimx = 0.30
$drychannelbridgemndwimn = -0.12
$drychannelbridgendwimn = -0.06
$drychannelbridgebsimx = 0.18
$drychannelbridgevismeanmx = 0.40
$drychannelbridgeincludeclass0 = $true
$drychannelbridgeconvertsediment = $false
$applycatchmentmask = $false

#general housekeeping functions, otb call and a way to ease mask editing through binary dilation
function runOtb {
    param([string[]]$Args)
    & $script:otblauncher @Args
}

function dilateBin {
    param(
        [string]$inputbinary,
        [string]$outputbinary,
        [int]$r
    )
    runOtb -Args @(
        "BinaryMorphologicalOperation",
        "-in", $inputbinary,
        "-channel", "1",
        "-structype", "box",
        "-xradius", $r,
        "-yradius", $r,
        "-foreval", "1",
        "-backval", "0",
        "-filter", "dilate",
        "-out", $outputbinary, "uint8"
    )
}

#my paths, placing in PATH would be easier but powershell is not a blessing all my paths ended up hardcoded
$script:otblauncher = "C:/Users/Student/Desktop/OTB/OTB-9.1.1-Win64/bin/otbApplicationLauncherCommandLine.exe"
$env:otbapplicationpath = "C:/Users/Student/Desktop/OTB/OTB-9.1.1-Win64/lib/otb/applications"
New-Item -ItemType Directory -Path $outputroot -Force | Out-Null

#loops through each scene and builds the raster masks / classes

$scenes = @(
    Get-ChildItem -Path $inputroot -Recurse -Filter *.tif |
    Where-Object {
        $_.DirectoryName -notmatch '(?i)[\\/]qa_masks([\\/]|$)' -and
        $_.BaseName -notmatch '(?i)_qa_mask$'
    } |
    Sort-Object FullName
)
$usestreamp = $applystreamp

#its going to look excessive but its just a long list of thresholds and parameters tweaking classifier sensitivity

foreach ($scene in $scenes) {
    $datelabel = $scene.BaseName
    $sceneout = Join-Path $outputroot $datelabel
    New-Item -ItemType Directory -Path $sceneout -Force | Out-Null
    #indices and masks
    $ndvi = Join-Path $sceneout "${datelabel}_ndvi.tif"
    $ndwi = Join-Path $sceneout "${datelabel}_ndwi.tif"
    $mndwi = Join-Path $sceneout "${datelabel}_mndwi.tif"
    $bsi = Join-Path $sceneout "${datelabel}_bsi.tif"
    $water = Join-Path $sceneout "${datelabel}_water_mask.tif"
    $watercandidate = Join-Path $sceneout "${datelabel}_water_candidate_mask.tif"
    $waterprotect = Join-Path $sceneout "${datelabel}_water_protect_mask.tif"
    $vegetation = Join-Path $sceneout "${datelabel}_vegetation_mask.tif"
    $bare = Join-Path $sceneout "${datelabel}_bare_sediment_mask.tif"
    $channelsediment = Join-Path $sceneout "${datelabel}_channel_sediment_mask.tif"
    $cloud = Join-Path $sceneout "${datelabel}_cloud_mask.tif"
    $cloudraw = Join-Path $sceneout "${datelabel}_cloud_mask_raw.tif"
    $cloudcore = Join-Path $sceneout "${datelabel}_cloud_mask_core.tif"
    $active = Join-Path $sceneout "${datelabel}_active_channel_mask.tif"
    $classmap = Join-Path $sceneout "${datelabel}_class_map.tif"

    $scenewatervismeanmx = $watervismeanmx
    $scenecloudvismeanmn = $cloudvismeanmn
    $scenecloudcorevismeanmn = $cloudcorevismeanmn
    $scenestreampvismeanmx = $streampvismeanmx
    $scenesedimentpriorvismeanmx = $sedimentpriorvismeanmx

    #brightness modifier; it basically just uniformally flatterns RGB by reference to not effect spectral signature but flatten brightness
    if ($useadaptivebrightness) {
        $stats = & $script:otblauncher "ComputeImagesStatistics" "-il" $scene.FullName 2>&1
        $meanline = $null
        $stdline = $null
        foreach ($line in $stats) {
            if ($line -match 'out\.mean:') { $meanline = $line.ToString() }
            elseif ($line -match 'out\.std:') { $stdline = $line.ToString() }
        }

        if ($null -ne $meanline -and $null -ne $stdline) {
            $means = @([regex]::Matches($meanline, '-?\d+(?:\.\d+)?') | ForEach-Object { [double]$_.Value })
            $stds = @([regex]::Matches($stdline, '-?\d+(?:\.\d+)?') | ForEach-Object { [double]$_.Value })
            if ($means.Count -ge 3 -and $stds.Count -ge 3) {
                $scenevismean = (($means[0] + $means[1] + $means[2]) / 3.0) / $reflectancescale
                $scenevisstd = (($stds[0] + $stds[1] + $stds[2]) / 3.0) / $reflectancescale
                $scenewatervismeanmx = [Math]::Min($adaptivewatervismeancap, [Math]::Max($adaptivewatervismeanfloor, $watervismeanmx + (($scenevismean - $adaptivescenevisreference) * $adaptivewatervissensitivity)))
                $scenecloudvismeanmn = [Math]::Max($cloudvismeanmn, $scenevismean + ($adaptivecloudstdfactor * $scenevisstd) + $adaptivecloudoffset)
                $scenecloudcorevismeanmn = [Math]::Max($cloudcorevismeanmn, $scenevismean + (($adaptivecloudstdfactor + 0.4) * $scenevisstd) + $adaptivecloudcoreoffset)
                $scenestreampvismeanmx = [Math]::Min($adaptivewatervismeancap, [Math]::Max($scenewatervismeanmx, $streampvismeanmx + (($scenevismean - $adaptivescenevisreference) * 0.35)))
                $scenesedimentpriorvismeanmx = [Math]::Min(0.40, [Math]::Max(0.24, $sedimentpriorvismeanmx + (($scenevismean - $adaptivescenevisreference) * 0.45)))
            }
        }
    }

    #the main bulk, otb classifiers by the given thresholds and params, masks are then output out the bottom
    #At the top here is primarily indices creation you'll see directly below here the band maths for ndvi, ndwi, etc... and then pushing some of the thresholds through them to suit them to palanan better
    runOtb -Args @("BandMath", "-il", $scene.FullName, "-exp", "(im1b7-im1b3)/(im1b7+im1b3+0.0001)", "-out", $ndvi, "float")
    runOtb -Args @("BandMath", "-il", $scene.FullName, "-exp", "(im1b2-im1b7)/(im1b2+im1b7+0.0001)", "-out", $ndwi, "float")
    runOtb -Args @("BandMath", "-il", $scene.FullName, "-exp", "(im1b2-im1b8)/(im1b2+im1b8+0.0001)", "-out", $mndwi, "float")
    runOtb -Args @("BandMath", "-il", $scene.FullName, "-exp", "((im1b8+im1b3)-(im1b7+im1b1))/((im1b8+im1b3)+(im1b7+im1b1)+0.0001)", "-out", $bsi, "float")
    runOtb -Args @("BandMath", "-il", $scene.FullName, $ndvi, $mndwi, $ndwi, $bsi, "-exp", "(((im3b1>$watermndwi or im4b1>$waterndwi) and im2b1<$waterndvimx and im5b1<$waterbsimx and (((im1b1+im1b2+im1b3)/3.0)/$reflectancescale)<$scenewatervismeanmx)?1:0)", "-out", $watercandidate, "uint8")
    runOtb -Args @("BandMath", "-il", $ndvi, $mndwi, $ndwi, "-exp", "((im1b1<$waterprotectndvimx and (im2b1>$waterprotectmndwimn or im3b1>$waterprotectndwimn))?1:0)", "-out", $waterprotect, "uint8")
    runOtb -Args @("BandMath", "-il", $scene.FullName, $ndvi, $mndwi, $bsi, "-exp", "(((((im1b1+im1b2+im1b3)/3.0)/$reflectancescale)>$scenecloudvismeanmn) and ((im1b8/$reflectancescale)>$cloudswirmn and (im1b9/$reflectancescale)>$cloudcirrusmn) and im2b1<$cloudndvimx and im3b1<$cloudmndwimx and im4b1<$cloudbsimx)?1:0)", "-out", $cloudraw, "uint8")
    runOtb -Args @("BandMath", "-il", $scene.FullName, "-exp", "(((((im1b1+im1b2+im1b3)/3.0)/$reflectancescale)>$scenecloudcorevismeanmn) and ((im1b8/$reflectancescale)>$cloudswirmn and (im1b9/$reflectancescale)>$cloudcirrusmn))?1:0)", "-out", $cloudcore, "uint8")
    runOtb -Args @("BandMath", "-il", $cloudcore, $cloudraw, $waterprotect, "-exp", "(im1b1==1)?1:((im2b1==1 and im3b1==0)?1:0)", "-out", $cloud, "uint8")
    runOtb -Args @("BandMath", "-il", $watercandidate, $cloud, "-exp", "(im2b1==1)?255:im1b1", "-out", $water, "uint8")
    runOtb -Args @("BandMath", "-il", $ndvi, $cloud, "-exp", "(im2b1==1)?255:((im1b1>$vegetationndvi)?1:0)", "-out", $vegetation, "uint8")
    runOtb -Args @("BandMath", "-il", $ndvi, $mndwi, $bsi, $ndwi, $cloud, "-exp", "(im5b1==1)?255:((im3b1>$barebsi and im2b1<$baremndwimx and im4b1<$barendwimx)?1:0)", "-out", $bare, "uint8")
    Remove-Item -Path $watercandidate, $waterprotect, $cloudraw, $cloudcore -Force

    runOtb -Args @("BandMath", "-il", $water, $vegetation, $bare, $cloud, "-exp", "(im4b1==1)?4:((im1b1==255 or im2b1==255 or im3b1==255)?255:((im1b1==1)?1:((im2b1==1)?2:((im3b1==1)?3:0))))", "-out", $classmap, "uint8")

    #edge case fill, helps recover lost water pixels by checking adjacent pixels to existing water
    #all of this recoveries and edge modifiers follow the same basics, I'm sure if I was more proficient in powershell there would be a more efficient way;
    #I'll explain it on this one, I take the existing water class map binary and re-do the processes we've been going through but only on pixels adjacent to existing water
    #This can then be made more agressive or more/less targetting in some cases
    if ($applywateredgercvy) {
        $edger = [Math]::Max(1, $wateredger)
        $waterseed = Join-Path $sceneout ("{0}_water_seed_bin.tif" -f $datelabel)
        $waterseeddil = Join-Path $sceneout ("{0}_water_seed_dil.tif" -f $datelabel)
        $classrecovered = Join-Path $sceneout ("{0}_class_map_recovered.tif" -f $datelabel)
        runOtb -Args @("BandMath", "-il", $classmap, "-exp", "(im1b1==1)?1:0", "-out", $waterseed, "uint8")
        dilateBin -inputbinary $waterseed -outputbinary $waterseeddil -r $edger
        runOtb -Args @("BandMath", "-il", $classmap, $cloud, $ndvi, $mndwi, $ndwi, $waterseeddil, "-exp", "(im2b1==1 or im1b1==255)?im1b1:((im1b1==0 and im6b1==1 and im3b1<$wateredgendvimx and (im4b1>$wateredgemndwimn or im5b1>$wateredgendwimn))?1:im1b1)", "-out", $classrecovered, "uint8")
        Move-Item -Path $classrecovered -Destination $classmap -Force
        Remove-Item -Path $waterseed, $waterseeddil, $classrecovered -Force
    }

    #same as above but checks adjacent to the manually lineated shapefile I fed it, this basically checks along the line i KNOW there is a river
    #and is a little nicer on classification than above 
    if ($usestreamp) {
        $streamr = [Math]::Max(1, $streampr)
        $cloudexr = [Math]::Max(0, $streampcloudexclusionr)
        $streampraw = Join-Path $sceneout ("{0}_stream_prior_raw.tif" -f $datelabel)
        $streampdil = Join-Path $sceneout ("{0}_stream_prior_dil.tif" -f $datelabel)
        $cloudpriorex = Join-Path $sceneout ("{0}_cloud_prior_exclusion.tif" -f $datelabel)
        $classstream = Join-Path $sceneout ("{0}_class_map_stream_prior.tif" -f $datelabel)
        $waternear = Join-Path $sceneout ("{0}_stream_water_near.tif" -f $datelabel)
        $waterneardil = Join-Path $sceneout ("{0}_stream_water_near_dil.tif" -f $datelabel)
        $barenear = Join-Path $sceneout ("{0}_stream_bare_near.tif" -f $datelabel)
        $bareneardil = Join-Path $sceneout ("{0}_stream_bare_near_dil.tif" -f $datelabel)
        $classcnty = Join-Path $sceneout ("{0}_class_map_continuity.tif" -f $datelabel)

        runOtb -Args @("Rasterization", "-in", $streampvector, "-im", $scene.FullName, "-background", "0", "-mode", "binary", "-mode.binary.foreground", "1", "-out", $streampraw, "uint8")
        dilateBin -inputbinary $streampraw -outputbinary $streampdil -r $streamr

        if ($cloudexr -gt 0) {
            dilateBin -inputbinary $cloud -outputbinary $cloudpriorex -r $cloudexr
        }
        else {
            runOtb -Args @("BandMath", "-il", $cloud, "-exp", "im1b1", "-out", $cloudpriorex, "uint8")
        }

        runOtb -Args @("BandMath", "-il", $classmap, $streampdil, $ndvi, $mndwi, $ndwi, $bsi, $cloudpriorex, $scene.FullName, "-exp", "(im1b1==255)?255:((im1b1==4)?4:((im1b1==0 and im2b1==1 and im7b1==0 and im3b1<$streampndvimx and im6b1<$streampbsimx and (((im8b1+im8b2+im8b3)/3.0)/$reflectancescale)<$scenestreampvismeanmx and (im4b1>$streampmndwimn or im5b1>$streampndwimn))?1:((im1b1==0 and im2b1==1 and im7b1==0 and im3b1<$sedimentpriorndvimx and im4b1<$sedimentpriormndwimx and im6b1>$sedimentpriorbsimn and im6b1<$sedimentpriorbsimx and (((im8b1+im8b2+im8b3)/3.0)/$reflectancescale)<$scenesedimentpriorvismeanmx)?5:im1b1)))", "-out", $classstream, "uint8")

        if ($applychannelcntyrcvy) {
            $cntyr = [Math]::Max(1, $channelcntyr)
            runOtb -Args @("BandMath", "-il", $classstream, "-exp", "(im1b1==1)?1:0", "-out", $waternear, "uint8")
            runOtb -Args @("BandMath", "-il", $classstream, "-exp", "(im1b1==3)?1:0", "-out", $barenear, "uint8")
            dilateBin -inputbinary $waternear -outputbinary $waterneardil -r $cntyr
            dilateBin -inputbinary $barenear -outputbinary $bareneardil -r $cntyr
            runOtb -Args @("BandMath", "-il", $classstream, $streampdil, $ndvi, $mndwi, $ndwi, $bsi, $cloudpriorex, $scene.FullName, $waterneardil, $bareneardil, "-exp", "(im1b1==255)?255:((im1b1==4)?4:((im1b1==0 and im2b1==1 and im7b1==0 and im9b1==1 and im10b1==0 and im3b1<$streampndvimx and im6b1<$streampbsimx and (((im8b1+im8b2+im8b3)/3.0)/$reflectancescale)<$scenestreampvismeanmx and (im4b1>$streampmndwimn or im5b1>$streampndwimn))?1:((im1b1==0 and im2b1==1 and im7b1==0 and im10b1==1 and im9b1==0 and im3b1<$sedimentpriorndvimx and im4b1<$sedimentpriormndwimx and im6b1>$sedimentpriorbsimn and im6b1<$sedimentpriorbsimx and (((im8b1+im8b2+im8b3)/3.0)/$reflectancescale)<$scenesedimentpriorvismeanmx)?5:((im1b1==0 and im2b1==1 and im7b1==0 and im9b1==1 and im10b1==1)?((im3b1<$streampndvimx and im6b1<$streampbsimx and (((im8b1+im8b2+im8b3)/3.0)/$reflectancescale)<$scenestreampvismeanmx and (im4b1>$streampmndwimn or im5b1>$streampndwimn))?1:((im3b1<$sedimentpriorndvimx and im4b1<$sedimentpriormndwimx and im6b1>$sedimentpriorbsimn and im6b1<$sedimentpriorbsimx and (((im8b1+im8b2+im8b3)/3.0)/$reflectancescale)<$scenesedimentpriorvismeanmx)?5:im1b1)):im1b1))))", "-out", $classcnty, "uint8")
            Move-Item -Path $classcnty -Destination $classmap -Force
        }
        else {
            Move-Item -Path $classstream -Destination $classmap -Force
        }

        Remove-Item -Path $streampraw, $streampdil, $cloudpriorex, $classstream, $waternear, $waterneardil, $barenear, $bareneardil, $classcnty -Force
    }

    #same as water recovery but for sediment
    if ($applychannelsedimentsplit) {
        $channelpriorr = [Math]::Max(1, $channelsedimentpriorr)
        $channelwaterr = [Math]::Max(1, $channelsedimentwateradjacencyr)
        $channelpriorraw = Join-Path $sceneout ("{0}_channel_prior_raw.tif" -f $datelabel)
        $channelpriordil = Join-Path $sceneout ("{0}_channel_prior_dil.tif" -f $datelabel)
        $channelwaterseed = Join-Path $sceneout ("{0}_channel_water_seed.tif" -f $datelabel)
        $channelwaterseeddil = Join-Path $sceneout ("{0}_channel_water_seed_dil.tif" -f $datelabel)
        $classchannelsplit = Join-Path $sceneout ("{0}_class_map_channel_split.tif" -f $datelabel)

        if ($usestreamp) {
            runOtb -Args @("Rasterization", "-in", $streampvector, "-im", $scene.FullName, "-background", "0", "-mode", "binary", "-mode.binary.foreground", "1", "-out", $channelpriorraw, "uint8")
            dilateBin -inputbinary $channelpriorraw -outputbinary $channelpriordil -r $channelpriorr
        }
        else {
            runOtb -Args @("BandMath", "-il", $classmap, "-exp", "1", "-out", $channelpriordil, "uint8")
        }

        runOtb -Args @("BandMath", "-il", $classmap, "-exp", "(im1b1==1)?1:0", "-out", $channelwaterseed, "uint8")
        dilateBin -inputbinary $channelwaterseed -outputbinary $channelwaterseeddil -r $channelwaterr

        $channelsplitexpr = "(im1b1==3 and im2b1==1 and im6b1==0 and im7b1==1 and im3b1<$inchannelsedimentadjndvimx and im4b1<$inchannelsedimentadjmndwimx and im5b1>$inchannelsedimentbsimn and im5b1<$inchannelsedimentadjbsimx and (((im8b1+im8b2+im8b3)/3.0)/$reflectancescale)<$inchannelsedimentadjvismeanmx)?5:im1b1"
        if ($allowsedimentsplitwithoutwateradjacency) {
            $channelsplitexpr = "(im1b1==3 and im2b1==1 and im6b1==0 and ((im7b1==1 and im3b1<$inchannelsedimentadjndvimx and im4b1<$inchannelsedimentadjmndwimx and im5b1>$inchannelsedimentbsimn and im5b1<$inchannelsedimentadjbsimx and (((im8b1+im8b2+im8b3)/3.0)/$reflectancescale)<$inchannelsedimentadjvismeanmx) or (im7b1==0 and im3b1<$inchannelsedimentnoadjndvimx and im4b1<$inchannelsedimentnoadjmndwimx and im5b1>$inchannelsedimentnoadjbsimn and im5b1<$inchannelsedimentnoadjbsimx and (((im8b1+im8b2+im8b3)/3.0)/$reflectancescale)<$inchannelsedimentnoadjvismeanmx)))?5:im1b1"
        }

        runOtb -Args @("BandMath", "-il", $classmap, $channelpriordil, $ndvi, $mndwi, $bsi, $cloud, $channelwaterseeddil, $scene.FullName, "-exp", $channelsplitexpr, "-out", $classchannelsplit, "uint8")
        Move-Item -Path $classchannelsplit -Destination $classmap -Force
        Remove-Item -Path $channelpriorraw, $channelpriordil, $channelwaterseed, $channelwaterseeddil, $classchannelsplit -Force
    }

    #checks single pixels say one pixel of water in a sea of vegetation to more agressively check it against its surroundings
    #specifically in the channel
    if ($applysinglepixelcleanup) {
        $cleanuprad = [Math]::Max(1, $cleanupr)
        $waterseed = Join-Path $sceneout ("{0}_cleanup_water_seed.tif" -f $datelabel)
        $waterseeddil = Join-Path $sceneout ("{0}_cleanup_water_seed_dil.tif" -f $datelabel)
        $channelseed = Join-Path $sceneout ("{0}_cleanup_channel_seed.tif" -f $datelabel)
        $channelseeddil = Join-Path $sceneout ("{0}_cleanup_channel_seed_dil.tif" -f $datelabel)
        $classclean = Join-Path $sceneout ("{0}_class_map_cleanup.tif" -f $datelabel)
        runOtb -Args @("BandMath", "-il", $classmap, "-exp", "(im1b1==1)?1:0", "-out", $waterseed, "uint8")
        runOtb -Args @("BandMath", "-il", $classmap, "-exp", "(im1b1==5)?1:0", "-out", $channelseed, "uint8")
        dilateBin -inputbinary $waterseed -outputbinary $waterseeddil -r $cleanuprad
        dilateBin -inputbinary $channelseed -outputbinary $channelseeddil -r $cleanuprad
        runOtb -Args @("BandMath", "-il", $classmap, $cloud, $ndvi, $mndwi, $ndwi, $bsi, $waterseeddil, $channelseeddil, "-exp", "(im1b1==255 or im1b1==4)?im1b1:((im1b1==0 and im2b1==0 and im7b1==1 and im3b1<$wateredgendvimx and (im4b1>$wateredgemndwimn or im5b1>$wateredgendwimn))?1:((im1b1==0 and im2b1==0 and im8b1==1 and im3b1<$sedimentpriorndvimx and im4b1<$sedimentpriormndwimx and im6b1>$sedimentpriorbsimn and im6b1<$sedimentpriorbsimx)?5:im1b1))", "-out", $classclean, "uint8")
        Move-Item -Path $classclean -Destination $classmap -Force
        Remove-Item -Path $waterseed, $waterseeddil, $channelseed, $channelseeddil, $classclean -Force
    }
    #same as water/sediment but for unclassified pixels notably more agressive than the prior two post thresholding
    if ($applyunclassifiedrcvy) {
        $unclwaterr = [Math]::Max(1, $unclassifiedwateradjacencyr)
        $unclpriorr = [Math]::Max(1, $unclassifiedchannelpriorr)
        $unclwaterseed = Join-Path $sceneout ("{0}_uncl_water_seed.tif" -f $datelabel)
        $unclwaterseeddil = Join-Path $sceneout ("{0}_uncl_water_seed_dil.tif" -f $datelabel)
        $unclchannelpriorraw = Join-Path $sceneout ("{0}_uncl_channel_prior_raw.tif" -f $datelabel)
        $unclchannelpriordil = Join-Path $sceneout ("{0}_uncl_channel_prior_dil.tif" -f $datelabel)
        $classrecovered0 = Join-Path $sceneout ("{0}_class_map_unclassified_recovery.tif" -f $datelabel)
        runOtb -Args @("BandMath", "-il", $classmap, "-exp", "(im1b1==1)?1:0", "-out", $unclwaterseed, "uint8")
        dilateBin -inputbinary $unclwaterseed -outputbinary $unclwaterseeddil -r $unclwaterr

        if ($usestreamp) {
            runOtb -Args @("Rasterization", "-in", $streampvector, "-im", $scene.FullName, "-background", "0", "-mode", "binary", "-mode.binary.foreground", "1", "-out", $unclchannelpriorraw, "uint8")
            dilateBin -inputbinary $unclchannelpriorraw -outputbinary $unclchannelpriordil -r $unclpriorr
        }
        else {
            runOtb -Args @("BandMath", "-il", $classmap, "-exp", "1", "-out", $unclchannelpriordil, "uint8")
        }

        runOtb -Args @("BandMath", "-il", $classmap, $cloud, $ndvi, $mndwi, $bsi, $unclwaterseeddil, $unclchannelpriordil, $scene.FullName, "-exp", "(im1b1==0 and im2b1==0 and im6b1==1 and im7b1==1 and im3b1<$inchannelsedimentndvimx and im4b1<$inchannelsedimentmndwimx and im5b1>$inchannelsedimentbsimn and (((im8b1+im8b2+im8b3)/3.0)/$reflectancescale)<$inchannelsedimentvismeanmx)?5:((im1b1==0 and im2b1==0 and im3b1<$unclassifiedbarendvimx and im5b1>$unclassifiedbarebsimn)?3:im1b1)", "-out", $classrecovered0, "uint8")
        Move-Item -Path $classrecovered0 -Destination $classmap -Force
        Remove-Item -Path $unclwaterseed, $unclwaterseeddil, $unclchannelpriorraw, $unclchannelpriordil, $classrecovered0 -Force
    }
    #same as above for sediment single pixs
    if ($applywaterspksedimentcleanup) {
        $spkr = [Math]::Max(1, $waterspkopeningr)
        $spkpriorr = [Math]::Max(1, $waterspkchannelpriorr)
        $spkwater = Join-Path $sceneout ("{0}_speckle_water.tif" -f $datelabel)
        $spkwateropen = Join-Path $sceneout ("{0}_speckle_water_open.tif" -f $datelabel)
        $spkmask = Join-Path $sceneout ("{0}_speckle_mask.tif" -f $datelabel)
        $spkpriorraw = Join-Path $sceneout ("{0}_speckle_prior_raw.tif" -f $datelabel)
        $spkpriordil = Join-Path $sceneout ("{0}_speckle_prior_dil.tif" -f $datelabel)
        $classspk = Join-Path $sceneout ("{0}_class_map_speckle_cleanup.tif" -f $datelabel)
        runOtb -Args @("BandMath", "-il", $classmap, "-exp", "(im1b1==1)?1:0", "-out", $spkwater, "uint8")
        runOtb -Args @("BinaryMorphologicalOperation", "-in", $spkwater, "-channel", "1", "-structype", "box", "-xradius", $spkr, "-yradius", $spkr, "-foreval", "1", "-backval", "0", "-filter", "opening", "-out", $spkwateropen, "uint8")
        runOtb -Args @("BandMath", "-il", $spkwater, $spkwateropen, "-exp", "(im1b1==1 and im2b1==0)?1:0", "-out", $spkmask, "uint8")

        if ($usestreamp) {
            runOtb -Args @("Rasterization", "-in", $streampvector, "-im", $scene.FullName, "-background", "0", "-mode", "binary", "-mode.binary.foreground", "1", "-out", $spkpriorraw, "uint8")
            dilateBin -inputbinary $spkpriorraw -outputbinary $spkpriordil -r $spkpriorr
        }
        else {
            runOtb -Args @("BandMath", "-il", $classmap, "-exp", "0", "-out", $spkpriordil, "uint8")
        }

        runOtb -Args @("BandMath", "-il", $classmap, $spkmask, $spkpriordil, $cloud, $ndvi, $mndwi, $bsi, $scene.FullName, "-exp", "(im2b1==1 and im4b1==0 and im6b1<$waterspksedimentndvimx and im7b1<$waterspksedimentmndwimx and im8b1>$waterspksedimentbsimn and (((im9b1+im9b2+im9b3)/3.0)/$reflectancescale)<$waterspksedimentvismeanmx)?((im3b1==1)?5:3):im1b1", "-out", $classspk, "uint8")
        Move-Item -Path $classspk -Destination $classmap -Force
        Remove-Item -Path $spkwater, $spkwateropen, $spkmask, $spkpriorraw, $spkpriordil, $classspk -Force
    }
    #same as above on bank interfaces (water and sediment)
    if ($applybankclass0rcvy) {
        $bankwaterr = [Math]::Max(1, $bankrcvywaterr)
        $bankchannelr = [Math]::Max(1, $bankrcvychannelr)
        $bankwaterseed = Join-Path $sceneout ("{0}_bank_water_seed.tif" -f $datelabel)
        $bankwaterseeddil = Join-Path $sceneout ("{0}_bank_water_seed_dil.tif" -f $datelabel)
        $bankchannelseed = Join-Path $sceneout ("{0}_bank_channel_seed.tif" -f $datelabel)
        $bankchannelseeddil = Join-Path $sceneout ("{0}_bank_channel_seed_dil.tif" -f $datelabel)
        $bankpriorraw = Join-Path $sceneout ("{0}_bank_prior_raw.tif" -f $datelabel)
        $bankpriordil = Join-Path $sceneout ("{0}_bank_prior_dil.tif" -f $datelabel)
        $classbankrecovered = Join-Path $sceneout ("{0}_class_map_bank_recovery.tif" -f $datelabel)
        runOtb -Args @("BandMath", "-il", $classmap, "-exp", "(im1b1==1)?1:0", "-out", $bankwaterseed, "uint8")
        runOtb -Args @("BandMath", "-il", $classmap, "-exp", "(im1b1==5)?1:0", "-out", $bankchannelseed, "uint8")
        dilateBin -inputbinary $bankwaterseed -outputbinary $bankwaterseeddil -r $bankwaterr
        dilateBin -inputbinary $bankchannelseed -outputbinary $bankchannelseeddil -r $bankchannelr

        if ($usestreamp) {
            runOtb -Args @("Rasterization", "-in", $streampvector, "-im", $scene.FullName, "-background", "0", "-mode", "binary", "-mode.binary.foreground", "1", "-out", $bankpriorraw, "uint8")
            dilateBin -inputbinary $bankpriorraw -outputbinary $bankpriordil -r $finalfallbackchannelpriorr
        }
        else {
            runOtb -Args @("BandMath", "-il", $classmap, "-exp", "0", "-out", $bankpriordil, "uint8")
        }

        runOtb -Args @("BandMath", "-il", $classmap, $cloud, $ndvi, $mndwi, $bsi, $bankwaterseeddil, $bankchannelseeddil, $bankpriordil, $scene.FullName, "-exp", "((im1b1==0 or im1b1==3) and im2b1==0 and (im6b1==1 or im7b1==1 or im8b1==1) and im3b1<$bankrcvyndvimx and im4b1<$bankrcvymndwimx and im5b1>$bankrcvybsimn and (((im9b1+im9b2+im9b3)/3.0)/$reflectancescale)<$bankrcvyvismeanmx)?5:im1b1", "-out", $classbankrecovered, "uint8")
        Move-Item -Path $classbankrecovered -Destination $classmap -Force
        Remove-Item -Path $bankwaterseed, $bankwaterseeddil, $bankchannelseed, $bankchannelseeddil, $bankpriorraw, $bankpriordil, $classbankrecovered -Force
    }
    #failsafe essentially
    if ($applyfinalclass0fallback) {
        $finalpriorr = [Math]::Max(1, $finalfallbackchannelpriorr)
        $finalpriorraw = Join-Path $sceneout ("{0}_final0_channel_prior_raw.tif" -f $datelabel)
        $finalpriordil = Join-Path $sceneout ("{0}_final0_channel_prior_dil.tif" -f $datelabel)
        $classfinal0 = Join-Path $sceneout ("{0}_class_map_final0_fill.tif" -f $datelabel)

        if ($usestreamp) {
            runOtb -Args @("Rasterization", "-in", $streampvector, "-im", $scene.FullName, "-background", "0", "-mode", "binary", "-mode.binary.foreground", "1", "-out", $finalpriorraw, "uint8")
            dilateBin -inputbinary $finalpriorraw -outputbinary $finalpriordil -r $finalpriorr
        }
        else {
            runOtb -Args @("BandMath", "-il", $classmap, "-exp", "0", "-out", $finalpriordil, "uint8")
        }

        runOtb -Args @("BandMath", "-il", $classmap, $finalpriordil, $cloud, "-exp", "(im1b1==0 and im3b1==0 and im2b1==1)?5:im1b1", "-out", $classfinal0, "uint8")
        Move-Item -Path $classfinal0 -Destination $classmap -Force
        Remove-Item -Path $finalpriorraw, $finalpriordil, $classfinal0 -Force
    }
    #water continuity check, basically triple checks where water appears to fragment, most common on nighttime imagery to be needed !
    if ($applywatercntyrcvy) {
        $contr = [Math]::Max(1, $watercntyr)
        $contpriorr = [Math]::Max(1, $watercntypriorr)
        $contwater = Join-Path $sceneout ("{0}_cont_water_seed.tif" -f $datelabel)
        $contwaterdil = Join-Path $sceneout ("{0}_cont_water_seed_dil.tif" -f $datelabel)
        $contpriorraw = Join-Path $sceneout ("{0}_cont_prior_raw.tif" -f $datelabel)
        $contpriordil = Join-Path $sceneout ("{0}_cont_prior_dil.tif" -f $datelabel)
        $classcont = Join-Path $sceneout ("{0}_class_map_water_continuity.tif" -f $datelabel)
        runOtb -Args @("BandMath", "-il", $classmap, "-exp", "(im1b1==1)?1:0", "-out", $contwater, "uint8")
        dilateBin -inputbinary $contwater -outputbinary $contwaterdil -r $contr

        if ($watercntyrecoverbare -and $usestreamp) {
            runOtb -Args @("Rasterization", "-in", $streampvector, "-im", $scene.FullName, "-background", "0", "-mode", "binary", "-mode.binary.foreground", "1", "-out", $contpriorraw, "uint8")
            dilateBin -inputbinary $contpriorraw -outputbinary $contpriordil -r $contpriorr
        }
        else {
            runOtb -Args @("BandMath", "-il", $classmap, "-exp", "0", "-out", $contpriordil, "uint8")
        }

        $watercntyexpr = "(im1b1==5 and im2b1==0 and im6b1==1 and im3b1<$watercntyndvimx and (im4b1>$watercntymndwimn or im5b1>$watercntyndwimn))?1:im1b1"
        if ($watercntyrecoverbare) {
            $watercntyexpr = "((im1b1==5 and im2b1==0 and im6b1==1 and im3b1<$watercntyndvimx and (im4b1>$watercntymndwimn or im5b1>$watercntyndwimn)) or (im1b1==3 and im2b1==0 and im6b1==1 and im7b1==1 and im3b1<$watercntybarendvimx and im8b1<$watercntybarebsimx and (((im9b1+im9b2+im9b3)/3.0)/$reflectancescale)<$watercntybarevismeanmx and (im4b1>$watercntybaremndwimn or im5b1>$watercntybarendwimn)))?1:im1b1"
        }
        if ($watercntyrecoverclass0) {
            $watercntyexpr = "((im1b1==5 and im2b1==0 and im6b1==1 and im3b1<$watercntyndvimx and (im4b1>$watercntymndwimn or im5b1>$watercntyndwimn)) or (im1b1==3 and im2b1==0 and im6b1==1 and im7b1==1 and im3b1<$watercntybarendvimx and im8b1<$watercntybarebsimx and (((im9b1+im9b2+im9b3)/3.0)/$reflectancescale)<$watercntybarevismeanmx and (im4b1>$watercntybaremndwimn or im5b1>$watercntybarendwimn)) or (im1b1==0 and im2b1==0 and im6b1==1 and im7b1==1 and im3b1<$watercntyclass0ndvimx and im8b1<$watercntyclass0bsimx and (((im9b1+im9b2+im9b3)/3.0)/$reflectancescale)<$watercntyclass0vismeanmx and (im4b1>$watercntyclass0mndwimn or im5b1>$watercntyclass0ndwimn)))?1:im1b1"
        }

        runOtb -Args @("BandMath", "-il", $classmap, $cloud, $ndvi, $mndwi, $ndwi, $contwaterdil, $contpriordil, $bsi, $scene.FullName, "-exp", $watercntyexpr, "-out", $classcont, "uint8")
        Move-Item -Path $classcont -Destination $classmap -Force
        Remove-Item -Path $contwater, $contwaterdil, $contpriorraw, $contpriordil, $classcont -Force
    }

    #same as above but more so for channels rather than what could be pooling
    if ($applywaterchannelclosing) {
        $closer = [Math]::Max(1, $waterchannelclosingr)
        $closepriorr = [Math]::Max(1, $waterchannelclosingpriorr)
        $closewaterseed = Join-Path $sceneout ("{0}_close_water_seed.tif" -f $datelabel)
        $closewaterclosed = Join-Path $sceneout ("{0}_close_water_closed.tif" -f $datelabel)
        $closepriorraw = Join-Path $sceneout ("{0}_close_prior_raw.tif" -f $datelabel)
        $closepriordil = Join-Path $sceneout ("{0}_close_prior_dil.tif" -f $datelabel)
        $classclosed = Join-Path $sceneout ("{0}_class_map_channel_closing.tif" -f $datelabel)
        runOtb -Args @("BandMath", "-il", $classmap, "-exp", "(im1b1==1)?1:0", "-out", $closewaterseed, "uint8")
        runOtb -Args @("BinaryMorphologicalOperation", "-in", $closewaterseed, "-channel", "1", "-structype", "box", "-xradius", $closer, "-yradius", $closer, "-foreval", "1", "-backval", "0", "-filter", "closing", "-out", $closewaterclosed, "uint8")

        if ($usestreamp) {
            runOtb -Args @("Rasterization", "-in", $streampvector, "-im", $scene.FullName, "-background", "0", "-mode", "binary", "-mode.binary.foreground", "1", "-out", $closepriorraw, "uint8")
            dilateBin -inputbinary $closepriorraw -outputbinary $closepriordil -r $closepriorr
        }
        else {
            runOtb -Args @("BandMath", "-il", $classmap, "-exp", "1", "-out", $closepriordil, "uint8")
        }

        runOtb -Args @("BandMath", "-il", $classmap, $cloud, $closewaterclosed, $closepriordil, "-exp", "(im2b1==0 and im3b1==1 and im4b1==1 and (im1b1==0 or im1b1==3 or im1b1==5))?1:im1b1", "-out", $classclosed, "uint8")
        Move-Item -Path $classclosed -Destination $classmap -Force
        Remove-Item -Path $closewaterseed, $closewaterclosed, $closepriorraw, $closepriordil, $classclosed -Force
    }
    if ($applydrychannelbridgercvy -and $usestreamp) {
        $bridgecloser = [Math]::Max(1, $drychannelbridgewatercloser)
        $bridgepriorr = [Math]::Max(1, $drychannelbridgepriorr)
        $bridgewaterseed = Join-Path $sceneout ("{0}_bridge_water_seed.tif" -f $datelabel)
        $bridgewaterclosed = Join-Path $sceneout ("{0}_bridge_water_closed.tif" -f $datelabel)
        $bridgepriorraw = Join-Path $sceneout ("{0}_bridge_prior_raw.tif" -f $datelabel)
        $bridgepriordil = Join-Path $sceneout ("{0}_bridge_prior_dil.tif" -f $datelabel)
        $classbridge = Join-Path $sceneout ("{0}_class_map_bridge_recovery.tif" -f $datelabel)
        runOtb -Args @("BandMath", "-il", $classmap, "-exp", "(im1b1==1)?1:0", "-out", $bridgewaterseed, "uint8")
        runOtb -Args @("BinaryMorphologicalOperation", "-in", $bridgewaterseed, "-channel", "1", "-structype", "box", "-xradius", $bridgecloser, "-yradius", $bridgecloser, "-foreval", "1", "-backval", "0", "-filter", "closing", "-out", $bridgewaterclosed, "uint8")
        runOtb -Args @("Rasterization", "-in", $streampvector, "-im", $scene.FullName, "-background", "0", "-mode", "binary", "-mode.binary.foreground", "1", "-out", $bridgepriorraw, "uint8")
        dilateBin -inputbinary $bridgepriorraw -outputbinary $bridgepriordil -r $bridgepriorr

        $bridgeclasscondition = "(im1b1==3)"
        if ($drychannelbridgeincludeclass0) { $bridgeclasscondition = "($bridgeclasscondition or im1b1==0)" }
        if ($drychannelbridgeconvertsediment) { $bridgeclasscondition = "($bridgeclasscondition or im1b1==5)" }

        $bridgeexpr = "(im2b1==0 and im3b1==1 and im4b1==1 and $bridgeclasscondition and im5b1<$drychannelbridgendvimx and im8b1<$drychannelbridgebsimx and (((im9b1+im9b2+im9b3)/3.0)/$reflectancescale)<$drychannelbridgevismeanmx and (im6b1>$drychannelbridgemndwimn or im7b1>$drychannelbridgendwimn))?1:im1b1"
        runOtb -Args @("BandMath", "-il", $classmap, $cloud, $bridgewaterclosed, $bridgepriordil, $ndvi, $mndwi, $ndwi, $bsi, $scene.FullName, "-exp", $bridgeexpr, "-out", $classbridge, "uint8")
        Move-Item -Path $classbridge -Destination $classmap -Force
        Remove-Item -Path $bridgewaterseed, $bridgewaterclosed, $bridgepriorraw, $bridgepriordil, $classbridge -Force
    }

    runOtb -Args @("BandMath", "-il", $classmap, "-exp", "(im1b1==4)?255:((im1b1==1)?1:0)", "-out", $water, "uint8")
    runOtb -Args @("BandMath", "-il", $classmap, "-exp", "(im1b1==4)?255:((im1b1==2)?1:0)", "-out", $vegetation, "uint8")
    runOtb -Args @("BandMath", "-il", $classmap, "-exp", "(im1b1==4)?255:((im1b1==3)?1:0)", "-out", $bare, "uint8")
    runOtb -Args @("BandMath", "-il", $classmap, "-exp", "(im1b1==4)?255:((im1b1==5)?1:0)", "-out", $channelsediment, "uint8")
    runOtb -Args @("BandMath", "-il", $classmap, "-exp", "(im1b1==4)?1:0", "-out", $cloud, "uint8")
    runOtb -Args @("BandMath", "-il", $classmap, "-exp", "(im1b1==4)?255:((im1b1==1 or im1b1==5)?1:0)", "-out", $active, "uint8")
}
#
#Ultimately it reads as a lot but it's just a series of recovery steps applied to a class map to try "fix" classification
#Classification itself is only the first few otb calls its then re-classifying itself
#As stated at the top it's far more thresholds than necessary but to preserve my "end state" i felt I couldn't remove them in refactoring or condense them otherwise risk checking a completely different class map on re-run
#
Write-Output "classification set to $outputroot"
