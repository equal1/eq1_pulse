#!/bin/bash  -xe
cd $(dirname $0)
conda env create --name eq1_pulse-dev --file ../conda_envs/conda_env.yaml "$@"
conda run --live-stream -n eq1_pulse-dev ./install_eq1_pulse.sh dev
