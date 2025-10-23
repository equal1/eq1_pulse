
# Define the environment name
$envName = "eq1_pulse-dev"

Push-Location -Path (Split-Path -Parent $MyInvocation.MyCommand.Definition)
try {

    # Create the conda environment
    & conda env create --name $envName --file ../conda_envs/conda_env.yaml

    # Run the install_eq1lab.ps1 script (PowerShell invocation)
    & conda run --live-stream -n $envName powershell -File ".\install_eq1_pulse.ps1" dev $envName

}
finally {
    Pop-Location
}
