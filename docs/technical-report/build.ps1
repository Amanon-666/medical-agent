$ErrorActionPreference = "Stop"

$reportRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$buildRoot = Join-Path $reportRoot "build"
$repositoryRoot = Resolve-Path (Join-Path $reportRoot "..\..")
$outputRoot = Join-Path $repositoryRoot "output\pdf"

New-Item -ItemType Directory -Force -Path $buildRoot | Out-Null
New-Item -ItemType Directory -Force -Path $outputRoot | Out-Null

function Invoke-ReportCommand {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Program,
        [Parameter(ValueFromRemainingArguments = $true)]
        [string[]]$Arguments
    )

    & $Program @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Report build command failed: $Program"
    }
}

Push-Location $reportRoot
try {
    Invoke-ReportCommand xelatex -interaction=nonstopmode -halt-on-error -output-directory="$buildRoot" main.tex
    Invoke-ReportCommand biber --input-directory="$buildRoot" --output-directory="$buildRoot" main
    Invoke-ReportCommand xelatex -interaction=nonstopmode -halt-on-error -output-directory="$buildRoot" main.tex
    Invoke-ReportCommand xelatex -interaction=nonstopmode -halt-on-error -output-directory="$buildRoot" main.tex
    Copy-Item -Force (Join-Path $buildRoot "main.pdf") (Join-Path $outputRoot "MediFlow-Technical-Report.pdf")
}
finally {
    Pop-Location
}
