#!/bin/sh
# this script is executed on the guest
base_dir=$(dirname "$0")
cd $base_dir
exec $base_dir/build.sh "$@" >output 2>&1
