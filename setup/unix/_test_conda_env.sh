#!/bin/sh
if test -z "$CONDA_DEFAULT_ENV" || test "$CONDA_DEFAULT_ENV" = base; then
    echo "The user's Conda environment is not active!" >&2
    echo "Activate a Conda environment (not 'base') with 'conda activate <<env>>' first,"
    echo "or use 'conda run --live-stream --name <<env>> $1'"
    exit 1
fi
exit 0
