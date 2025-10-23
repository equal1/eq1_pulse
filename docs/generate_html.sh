ENV_NAME=eq1_pulse-dev
cd $(dirname $0)
conda run --live-stream -n $ENV_NAME make html
