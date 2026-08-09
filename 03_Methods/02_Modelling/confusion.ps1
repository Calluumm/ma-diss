#path heavy script, ive left paths non generic in git as it wouldnt super make anything more clear
#confusion matrix relies on the manual templates for classifications
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$classifiedroot = "c:/Users/Student/Desktop/Masters/Dissertation/02_Data/02_Processed/Sentinel2_Geomorphology_OTB"
$outputpath = ""
$mode = "Transition"
$validationcsv = ""
$validationdates = @()
$validationclasscodes = @(1, 2, 3, 4, 5)
$samplesperclass = 25
$randomseed = 42

function runOtb {
    param([Parameter(Mandatory = $true)][string[]]$args)

    & $script:otb @args
    if ($LASTEXITCODE -ne 0) {
        throw "OTB failed (${LASTEXITCODE}): $($args -join ' ')"
    }
}

function getTransitionOut {
    param(
        [Parameter(Mandatory = $true)][string]$root,
        [string]$path = ""
    )
    if (-not [string]::IsNullOrWhiteSpace($path)) {
        return $path
    }
    $name = Split-Path $root -Leaf
    $year = [regex]::Match($name, '_(\d{4})$')
    if ($year.Success) {
        return (Join-Path $script:repo ("04_Analysis/{0}/confusion.csv" -f $year.Groups[1].Value))
    }
    return (Join-Path $script:repo "04_Analysis/confusion.csv")
}
#make matching csv temp
function getValidationTemplateOut {
    param(
        [Parameter(Mandatory = $true)][string]$root,
        [string]$path = ""
    )
    if (-not [string]::IsNullOrWhiteSpace($path)) {
        return $path
    }
    $name = Split-Path $root -Leaf
    $year = [regex]::Match($name, '_(\d{4})$')
    if ($year.Success) {
        return (Join-Path $script:repo ("04_Analysis/{0}/cltemp.csv" -f $year.Groups[1].Value))
    }

    return (Join-Path $script:repo "04_Analysis/cltemp.csv")
}

function getValidationMetricsBase {
    param(
        [Parameter(Mandatory = $true)][string]$root,
        [string]$path = ""
    )
    if (-not [string]::IsNullOrWhiteSpace($path)) {
        return (Join-Path (Split-Path -Parent $path) ([System.IO.Path]::GetFileNameWithoutExtension($path)))
    }
    $name = Split-Path $root -Leaf
    $year = [regex]::Match($name, '_(\d{4})$')
    if ($year.Success) {
        return (Join-Path $script:repo ("04_Analysis/{0}/classification_validation" -f $year.Groups[1].Value))
    }
    return (Join-Path $script:repo "04_Analysis/classification_validation")
}

function classMap {
    param(
        [Parameter(Mandatory = $true)][string]$root,
        [Parameter(Mandatory = $true)][string]$date
    )

    return (Join-Path (Join-Path $root $date) ("{0}_class_map.tif" -f $date))
}

function pixelArea {
    param([Parameter(Mandatory = $true)]$data)

    $grid = @($data.geoTransform)
    $dx = [math]::Abs([double]$grid[1])
    $dy = [math]::Abs([double]$grid[5])
    $wkt = [string]$data.coordinateSystem.wkt
    if ($wkt -match '^(GEOGCRS|GEOGCS)\[') {
        $top = [double]$data.cornerCoordinates.upperLeft[1]
        $bot = [double]$data.cornerCoordinates.lowerLeft[1]
        $mid = ($top + $bot) / 2.0
        $mlat = 111132.92
        $mlon = 111320.0 * [math]::Cos($mid * [math]::PI / 180.0)
        return $dx * $dy * $mlon * $mlat
    }

    return $dx * $dy
}

function getTransitionLabels {
    return @{
        0 = "unclassified"
        1 = "water"
        2 = "vegetation"
        3 = "bare_sediment"
        4 = "cloud"
        5 = "channel_sediment"
        6 = "invalid"
    }
}

function getValidationLabels {
    return @{
        0 = "unclassified"
        1 = "water"
        2 = "vegetation"
        3 = "bare_sediment"
        4 = "cloud"
        5 = "channel_sediment"
        255 = "invalid"
    }
}

function getValidationCodes {
    return @(0, 1, 2, 3, 4, 5, 255)
}

function getValidationReverseMap {
    $reverse = @{}
    foreach ($entry in (getValidationLabels).GetEnumerator()) {
        $reverse[$entry.Value.ToLowerInvariant()] = [int]$entry.Key
    }
    return $reverse
}

function pairRows {
    param(
        [Parameter(Mandatory = $true)][string]$pre,
        [Parameter(Mandatory = $true)][string]$post,
        [Parameter(Mandatory = $true)][double]$area,
        [Parameter(Mandatory = $true)][int[]]$bins,
        [Parameter(Mandatory = $true)][hashtable]$labels
    )

    $rows = @()
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

    return $rows
}

function getRasterMetadata {
    param([Parameter(Mandatory = $true)][string]$path)

    $json = (& $script:gdal -json -nomd $path | Out-String)
    if ($LASTEXITCODE -ne 0) {
        throw "gdalinfo failed for $path"
    }

    return ($json | ConvertFrom-Json)
}

function pixelToWorld {
    param(
        [Parameter(Mandatory = $true)][double]$px,
        [Parameter(Mandatory = $true)][double]$py,
        [Parameter(Mandatory = $true)][double[]]$gt
    )

    $x = $gt[0] + ($px * $gt[1]) + ($py * $gt[2])
    $y = $gt[3] + ($px * $gt[4]) + ($py * $gt[5])
    return [pscustomobject]@{ X = $x; Y = $y }
}

function getSampledClassCode {
    param(
        [Parameter(Mandatory = $true)][string]$path,
        [Parameter(Mandatory = $true)][int]$x,
        [Parameter(Mandatory = $true)][int]$y
    )

    $raw = (& $script:gdallocationinfo -valonly $path $x $y | Out-String).Trim()
    $match = [regex]::Match($raw, '-?\d+(?:\.\d+)?')
    return [int][math]::Round([double]$match.Value)
}

function resolveValidationCode {
    param(
        [Parameter(Mandatory = $true)]$row,
        [Parameter(Mandatory = $true)][string]$codefield,
        [Parameter(Mandatory = $true)][string]$labelfield,
        [Parameter(Mandatory = $true)][hashtable]$reversemap
    )

    $codevalue = [string]$row.$codefield
    if (-not [string]::IsNullOrWhiteSpace($codevalue)) {
        $parsed = 0
        return $parsed
    }

    $labelvalue = [string]$row.$labelfield
    if (-not [string]::IsNullOrWhiteSpace($labelvalue)) {
        $key = $labelvalue.Trim().ToLowerInvariant()
        if ($reversemap.ContainsKey($key)) {
            return [int]$reversemap[$key]
        }
    }

}

function shouldIncludeRowInMetrics {
    param([Parameter(Mandatory = $true)]$row)

    $value = [string]$row.include_in_metrics
    if ([string]::IsNullOrWhiteSpace($value)) {
        return $true
    }

    switch ($value.Trim().ToLowerInvariant()) {
        "0" { return $false }
        "false" { return $false }
        "no" { return $false }
        "n" { return $false }
        default { return $true }
    }
}

function exportValidationTemplate {
    param(
        [Parameter(Mandatory = $true)][string]$root,
        [Parameter(Mandatory = $true)][string]$path,
        [Parameter(Mandatory = $true)][string[]]$dates,
        [Parameter(Mandatory = $true)][int[]]$classcodes,
        [Parameter(Mandatory = $true)][int]$countperclass,
        [Parameter(Mandatory = $true)][int]$seed
    )

    $labels = getValidationLabels
    $random = [System.Random]::new($seed)
    $rows = New-Object System.Collections.Generic.List[object]

    New-Item -ItemType Directory -Path (Split-Path $path -Parent) -Force | Out-Null

    foreach ($date in $dates) {
        $raster = classMap -root $root -date $date
        $meta = getRasterMetadata -path $raster
        $width = [int]$meta.size[0]
        $height = [int]$meta.size[1]
        $gt = @($meta.geoTransform | ForEach-Object { [double]$_ })
        $used = @{}

        foreach ($targetCode in $classcodes) {
            if (-not $labels.ContainsKey($targetCode)) {
            }

            $kept = 0
            $attempts = 0
            $maxAttempts = [Math]::Max(1000, $countperclass * 150)

            while ($kept -lt $countperclass -and $attempts -lt $maxAttempts) {
                $attempts += 1
                $x = $random.Next(0, $width)
                $y = $random.Next(0, $height)
                $key = "{0},{1}" -f $x, $y
                if ($used.ContainsKey($key)) {
                    continue
                }

                $used[$key] = $true
                $predicted = getSampledClassCode -path $raster -x $x -y $y
                if ($predicted -ne $targetCode) {
                    continue
                }

                $coord = pixelToWorld -px ($x + 0.5) -py ($y + 0.5) -gt $gt
                $kept += 1
                $rows.Add([pscustomobject]([ordered]@{
                    sample_id = ("{0}_{1}_{2:D3}" -f $date, $labels[$targetCode], $kept)
                    sample_date = $date
                    class_map = $raster
                    pixel_x = $x
                    pixel_y = $y
                    x_coord = [math]::Round($coord.X, 6)
                    y_coord = [math]::Round($coord.Y, 6)
                    predicted_code = $predicted
                    predicted_label = $labels[$predicted]
                    reference_code = ""
                    reference_label = ""
                    include_in_metrics = 1
                    notes = ""
                })) | Out-Null
            }
        }
    }

    $rows | Export-Csv -Path $path -NoTypeInformation
}

function writeValidationMetrics {
    param(
        [Parameter(Mandatory = $true)][string]$inputcsv,
        [Parameter(Mandatory = $true)][string]$basepath
    )

    $labels = getValidationLabels
    $codes = getValidationCodes
    $reverse = getValidationReverseMap
    $rows = @(Import-Csv -Path $inputcsv)
    $usable = @()

    foreach ($row in $rows) {
        if (-not (shouldIncludeRowInMetrics -row $row)) {
            continue
        }

        $hasReference = (-not [string]::IsNullOrWhiteSpace([string]$row.reference_code)) -or (-not [string]::IsNullOrWhiteSpace([string]$row.reference_label))
        if (-not $hasReference) {
            continue
        }

        $predicted = resolveValidationCode -row $row -codefield "predicted_code" -labelfield "predicted_label" -reversemap $reverse
        $reference = resolveValidationCode -row $row -codefield "reference_code" -labelfield "reference_label" -reversemap $reverse
        if (-not $labels.ContainsKey($predicted)) {
            throw "csv error 1"
        }
        if (-not $labels.ContainsKey($reference)) {
            throw "csv error 2"
        }

        $usable += [pscustomobject]@{
            predicted_code = $predicted
            reference_code = $reference
        }
    }

    $matrix = @{}
    foreach ($refCode in $codes) {
        $matrix[$refCode] = @{}
        foreach ($predCode in $codes) {
            $matrix[$refCode][$predCode] = 0
        }
    }

    foreach ($row in $usable) {
        $matrix[$row.reference_code][$row.predicted_code] += 1
    }

    $matrixRows = @()
    foreach ($refCode in $codes) {
        $rowTotal = 0
        $obj = [ordered]@{
            reference_code = $refCode
            reference_label = $labels[$refCode]
        }
        foreach ($predCode in $codes) {
            $count = [int]$matrix[$refCode][$predCode]
            $obj[$labels[$predCode]] = $count
            $rowTotal += $count
        }
        $obj["row_total"] = $rowTotal
        $matrixRows += [pscustomobject]$obj
    }

    $total = [double]$usable.Count
    $diag = 0.0
    $sumExpected = 0.0
    $summaryRows = @()

    foreach ($code in $codes) {
        $diagCount = [double]$matrix[$code][$code]
        $diag += $diagCount
        $rowTotal = 0.0
        $colTotal = 0.0
        foreach ($predCode in $codes) {
            $rowTotal += [double]$matrix[$code][$predCode]
        }
        foreach ($refCode in $codes) {
            $colTotal += [double]$matrix[$refCode][$code]
        }
        $sumExpected += $rowTotal * $colTotal

        $producer = if ($rowTotal -gt 0) { $diagCount / $rowTotal } else { [double]::NaN }
        $user = if ($colTotal -gt 0) { $diagCount / $colTotal } else { [double]::NaN }
        $f1 = if (($producer + $user) -gt 0) { (2.0 * $producer * $user) / ($producer + $user) } else { [double]::NaN }

        $summaryRows += [pscustomobject]([ordered]@{
            class_code = $code
            class_label = $labels[$code]
            support_reference = [int]$rowTotal
            support_predicted = [int]$colTotal
            true_positive = [int]$diagCount
            producers_accuracy = $producer
            users_accuracy = $user
            f1_score = $f1
            kappa = ""
            expected_agreement = ""
        })
    }

    $overall = if ($total -gt 0) { $diag / $total } else { [double]::NaN }
    $expected = if ($total -gt 0) { $sumExpected / ($total * $total) } else { [double]::NaN }
    $kappa = if ($total -gt 0 -and $expected -lt 1.0) { ($overall - $expected) / (1.0 - $expected) } else { [double]::NaN }

    $overallRow = [pscustomobject]([ordered]@{
        class_code = "all"
        class_label = "overall"
        support_reference = [int]$total
        support_predicted = [int]$total
        true_positive = [int]$diag
        producers_accuracy = $overall
        users_accuracy = $overall
        f1_score = $overall
        kappa = $kappa
        expected_agreement = $expected
    })

    New-Item -ItemType Directory -Path (Split-Path $basepath -Parent) -Force | Out-Null
    $matrixOut = "{0}_matrix.csv" -f $basepath
    $summaryOut = "{0}_summary.csv" -f $basepath
    $matrixRows | Export-Csv -Path $matrixOut -NoTypeInformation
    ($summaryRows + $overallRow) | Export-Csv -Path $summaryOut -NoTypeInformation
    Write-Output "wrote validation matrix $matrixOut"
    Write-Output "wrote validation summary $summaryOut"
}

$script:repo = "c:/Users/Student/Desktop/Masters/Dissertation"
$script:otb = "C:/Users/Student/Desktop/OTB/OTB-9.1.1-Win64/bin/otbApplicationLauncherCommandLine.exe"
$script:gdal = "C:/Users/Student/Desktop/OTB/OTB-9.1.1-Win64/bin/gdalinfo.exe"
$script:gdallocationinfo = "C:/Users/Student/Desktop/OTB/OTB-9.1.1-Win64/bin/gdallocationinfo.exe"
$env:OTB_APPLICATION_PATH = "C:/Users/Student/Desktop/OTB/OTB-9.1.1-Win64/lib/otb/applications"

$dates = @(
    Get-ChildItem -Path $classifiedroot -Directory |
        Where-Object { $_.Name -match '^\d{4}-\d{2}-\d{2}$' } |
        Sort-Object Name |
        Select-Object -ExpandProperty Name
)

switch ($mode) {
    "Transition" {
        $out = getTransitionOut -root $classifiedroot -path $outputpath
        New-Item -ItemType Directory -Path (Split-Path $out -Parent) -Force | Out-Null

        $labels = getTransitionLabels
        $rows = @()
        $all = New-Object System.Collections.Generic.List[int]
        foreach ($item in 0..48) {
            $all.Add(0)
        }

        for ($i = 0; $i -lt ($dates.Count - 1); $i++) {
            $pre = $dates[$i]
            $post = $dates[$i + 1]
            $one = classmap -root $classifiedroot -date $pre
            $two = classmap -root $classifiedroot -date $post

            $temp = Join-Path $env:TEMP ("cm_{0}_to_{1}.tif" -f $pre, $post)
            runOtb -args @(
                "BandMath",
                "-il", $one, $two,
                "-exp", "(((im1b1==255)?6:im1b1)*7)+((im2b1==255)?6:im2b1)",
                "-out", $temp, "uint8"
            )

            try {
                $json = (& $script:gdal -json -hist -nomd $temp | Out-String)
                $data = $json | ConvertFrom-Json
                $bins = @($data.bands[0].histogram.buckets)
                $area = pixelArea -data $data
                $rows += pairRows -pre $pre -post $post -area $area -bins $bins -labels $labels
                foreach ($item in 0..48) {
                    $all[$item] += [int]$bins[$item]
                }
            }
            finally {
                Remove-Item -Path $temp -Force -ErrorAction SilentlyContinue
            }
        }

        $rows += pairRows -pre "all" -post "all" -area ([double]$rows[0].pixelm2) -bins $all.ToArray() -labels $labels
        $rows | Export-Csv -Path $out -NoTypeInformation
        Write-Output "wrote confusion matrix $out"
    }

    "ExportValidationTemplate" {
        $out = getValidationTemplateOut -root $classifiedroot -path $outputpath
        $targetDates = if ($validationdates.Count -gt 0) { @($validationdates) } else { @($dates) }
        exportValidationTemplate -root $classifiedroot -path $out -dates $targetDates -classcodes $validationclasscodes -countperclass $samplesperclass -seed $randomseed
    }

    "ValidationMetrics" {
        $input = if (-not [string]::IsNullOrWhiteSpace($validationcsv)) { $validationcsv } else { getValidationTemplateOut -root $classifiedroot -path $outputpath }
        $base = getValidationMetricsBase -root $classifiedroot -path $outputpath
        writeValidationMetrics -inputcsv $input -basepath $base
    }
}