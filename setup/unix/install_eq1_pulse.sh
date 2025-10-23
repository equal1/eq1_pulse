#!/bin/bash -ex
case "$1" in
    dev)
        variant='[dev]'
        pre_commit=true
        EDITABLE=--editable
        ;;
    site)
        variant=''
        pre_commit=false
        EDITABLE=
        ;;
    site-dev)
        variant='[dev]'
        pre_commit=true
        EDITABLE=
        ;;
    editable)
        variant=''
        pre_commit=true
        EDITABLE=--editable
        ;;
    *)
        echo "Expected 'dev', 'site', 'site-dev', 'editable', argument, got '$1'" 1>&2
        exit 1
esac
cd $(dirname $0)
./_test_conda_env.sh $0 || exit $?
uv pip install --force-reinstall $EDITABLE ../.."$variant"
if $pre_commit; then pre-commit install; fi
