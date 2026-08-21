Set-StrictMode -Version Latest
#my paths
$classifiedroot = "c:/Users/Student/Desktop/Masters/Dissertation/02_Data/02_Processed/Sentinel2_Geomorphology_OTB"
$repo = "c:/Users/Student/Desktop/Masters/Dissertation"
$otb = "C:/Users/Student/Desktop/OTB/OTB-9.1.1-Win64/bin/otbApplicationLauncherCommandLine.exe"
$gdal = "C:/Users/Student/Desktop/OTB/OTB-9.1.1-Win64/bin/gdalinfo.exe"
$env:OTB_APPLICATION_PATH = "C:/Users/Student/Desktop/OTB/OTB-9.1.1-Win64/lib/otb/applications"

$labels = @{
    0 = "unclassified"
    1 = "water"
    2 = "vegetation"
    3 = "bare_sediment"
    4 = "cloud"
    5 = "channel_sediment"
    6 = "invalid"
}

#output csv path and date list
$out = Join-Path $repo "04_Analysis/confusion.csv"
$dates = @(
    Get-ChildItem -Path $classifiedroot -Directory |
    Where-Object { $_.Name -match '^\d{4}-\d{2}-\d{2}$' } |
    Sort-Object Name |
    Select-Object -ExpandProperty Name
)

$rows = @()
$all = @(0..48 | ForEach-Object { 0 })

#with each class a 7x7 confusion matrix is made for each scene pair then summed for a total
#its fairly straight fotwards just has to loop for each scene pair and makes sure to use correct pixel areas

for ($i = 0; $i -lt ($dates.Count - 1); $i++) {
    $pre = $dates[$i]
    $post = $dates[$i + 1]
    $one = Join-Path (Join-Path $classifiedroot $pre) ("{0}_class_map.tif" -f $pre)
    $two = Join-Path (Join-Path $classifiedroot $post) ("{0}_class_map.tif" -f $post)
    $temp = Join-Path $env:TEMP ("cm_{0}_to_{1}.tif" -f $pre, $post)

    & $otb "BandMath" "-il" $one $two "-exp" "(((im1b1==255)?6:im1b1)*7)+((im2b1==255)?6:im2b1)" "-out" $temp "uint8"

    $json = (& $gdal "-json" "-hist" "-nomd" $temp | Out-String)
    $data = $json | ConvertFrom-Json
    $bins = @($data.bands[0].histogram.buckets)

    $grid = @($data.geoTransform)
    $dx = [math]::Abs([double]$grid[1])
    $dy = [math]::Abs([double]$grid[5])
    $area = $dx * $dy
    $wkt = [string]$data.coordinateSystem.wkt
    if ($wkt -match '^(GEOGCRS|GEOGCS)\[') {
        $top = [double]$data.cornerCoordinates.upperLeft[1]
        $bot = [double]$data.cornerCoordinates.lowerLeft[1]
        $mid = ($top + $bot) / 2.0
        $mlat = 111132.92
        $mlon = 111320.0 * [math]::Cos($mid * [math]::PI / 180.0)
        $area = $dx * $dy * $mlon * $mlat
    }

    foreach ($from in 0..6) {
        $vals = [ordered]@{}
        $sum = 0
        foreach ($into in 0..6) {
            $code = ($from * 7) + $into
            $count = [int]$bins[$code]
            $vals[$labels[$into]] = $count
            $sum += $count
        }

        $rows += [pscustomobject]([ordered]@{
            pre_date = $pre
            post_date = $post
            from_code = $from
            label = $labels[$from]
            unclassified = $vals["unclassified"]
            water = $vals["water"]
            vegetation = $vals["vegetation"]
            bare_sediment = $vals["bare_sediment"]
            cloud = $vals["cloud"]
            channel_sediment = $vals["channel_sediment"]
            invalid = $vals["invalid"]
            rowtot = $sum
            rowtotm2 = $sum * $area
            rowtotkm = ($sum * $area) / 1000000.0
            pixelm2 = $area
        })
    }

    foreach ($item in 0..48) {
        $all[$item] += [int]$bins[$item]
    }

    Remove-Item -Path $temp -Force -ErrorAction SilentlyContinue
}

foreach ($from in 0..6) {
    $vals = [ordered]@{}
    $sum = 0
    foreach ($into in 0..6) {
        $code = ($from * 7) + $into
        $count = [int]$all[$code]
        $vals[$labels[$into]] = $count
        $sum += $count
    }

    $rows += [pscustomobject]([ordered]@{
        pre_date = "all"
        post_date = "all"
        from_code = $from
        label = $labels[$from]
        unclassified = $vals["unclassified"]
        water = $vals["water"]
        vegetation = $vals["vegetation"]
        bare_sediment = $vals["bare_sediment"]
        cloud = $vals["cloud"]
        channel_sediment = $vals["channel_sediment"]
        invalid = $vals["invalid"]
        rowtot = $sum
        rowtotm2 = $sum * [double]$rows[0].pixelm2
        rowtotkm = ($sum * [double]$rows[0].pixelm2) / 1000000.0
        pixelm2 = [double]$rows[0].pixelm2
    })
}

#output here

New-Item -ItemType Directory -Path (Split-Path $out -Parent) -Force | Out-Null
$rows | Export-Csv -Path $out -NoTypeInformation
Write-Output "wrote confusion matrix $out"
