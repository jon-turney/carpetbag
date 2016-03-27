#!/bin/sh -x
# this script is executed on the guest
base_dir=$(dirname "$0")
cd $base_dir
$base_dir/carpetbag.sh "$@" 2>&1 | u2d -f
