param (
    [string]$Deps,
    [string]$CondaEnvName,
    [string]$Editable
)

# Change to the directory where the script is located
Set-Location -Path (Split-Path -Parent $MyInvocation.MyCommand.Definition)

if ([string]::IsNullOrEmpty($Deps)) {
    Write-Error "No dependencies specified. Please provide a dependencies argument (e.g., 'prod' or 'dev')."
    exit 1
}

# Check if a conda environment name was provided
if (-not [string]::IsNullOrEmpty($CondaEnvName)) {
    # Activate the conda environment
    Write-Host "Activating conda environment: $CondaEnvName"
    conda activate $CondaEnvName
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Failed to activate conda environment: $CondaEnvName. Please ensure the environment exists and conda is in your PATH."
        exit 1
    }
}


uv pip install --force-reinstall $Editable ../..[$Deps]

if ($Deps -eq "dev") {
    pre-commit install
}
