#!/bin/bash -xe
cd $(dirname "$0")
conda env update --name eq1_pulse-dev --prune --file ../conda_envs/conda_env.yaml "$@"
conda run --live-stream -n eq1_pulse-dev ./install_eq1_pulse.sh dev
