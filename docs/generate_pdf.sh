ENV_NAME=eq1_pulse-dev
conda run --live-stream -n $ENV_NAME make LATEXMKOPTS="-f -interaction=nonstopmode" latexpdf
