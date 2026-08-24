set ENV_NAME=eq1_pulse-dev
cd %~dp0
conda run --live-stream -n %ENV_NAME% ./make.bat "LATEXMKOPTS=""-f -interaction=nonstopmode""" latexpdf
