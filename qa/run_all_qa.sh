#!/bin/sh -ex
CONDA_ENV="eq1_pulse-dev"
cd $(dirname $0)/..
conda run -n $CONDA_ENV --live-stream pyright src tests
conda run -n $CONDA_ENV --live-stream mypy src tests
conda run -n $CONDA_ENV --live-stream pytest tests
