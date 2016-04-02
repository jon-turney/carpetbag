#!/bin/sh -x
# this script is executed on the guest

pwd
echo $@

# SRCPKG names the source package filename
SRCPKG=$1
# OUTDIR names the directory where output is placed
OUTDIR=$(cygpath -ua ${2:-/carpetbag.out})

# extract PVR
PVR=${SRCPKG%-src.tar.*}

BUILDDIR=/build

#
ARCH=$(uname -m)
SETUP_ARCH=${ARCH/i686/x86}

#
# given a src package
#
# - unpack the src package
# - if it's cygport has DEPENDS
# -- install it's build-deps
# -- otherwise used guess_depends, which can be produced by guessing heuristic or an external database of build-deps
# - build the package
# - move the built dist files into OUTDIR
#

rm -rf ${BUILDDIR}
mkdir ${BUILDDIR}
tar -C ${BUILDDIR} --strip-components=1 -xvf ${SRCPKG} || exit 1

CYGPORT=$(ls ${BUILDDIR}/*.cygport)
if [ -z "${CYGPORT}" ] ; then
    echo "No cygport file found"
    exit 1
fi
# XXX: there must be exactly one cygport file
# XXX: if there's no cygport file, in theory we could look for a g-b-s style
# .sh file instead

DEPENDS=$(grep '^DEPENDS=' ${CYGPORT})

if [ -z "${DEPENDS}" ] ; then
    echo "No DEPENDS in cygport file, using guesses"
    DEPENDS=$(cat guessed_depends)
fi

if [ -n "${DEPENDS}" ] ; then
    //necker/download/cygwin-${SETUP_ARCH}/setup-${SETUP_ARCH} \
                             -q -P ${DEPENDS} \
                             -l "\\\\necker\download\cygwin-packages" \
                             -s http://mirrors.kernel.org/sourceware/cygwin/
fi

#
cd ${BUILDDIR}

# cygport ${CYGPORT} download || exit 1
# XXX: all fetchable files should be present in the source package
cygport ${CYGPORT} prep || exit 1
# XXX: magically handle postinstall/preremove.sh
cygport ${CYGPORT} compile || exit 1
cygport ${CYGPORT} install || exit 1
cygport ${CYGPORT} package || exit 1

# copy build products to OUTDIR and write a file manifest
rm -rf ${OUTDIR}
mkdir -p ${OUTDIR}
cp -aT ${PVR}.${ARCH}/dist ${OUTDIR}
cd ${OUTDIR}
find * -type f >manifest
