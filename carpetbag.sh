#!/bin/sh -x
# this script is executed on the guest

pwd
echo $@

# avoid output colourization
export TERM=dumb

# SRCPKG names the SRCPKG
SRCPKG=$1

BUILDDIR=/build
ARCH=x86

#
# given a src package
#
# - unpack the src package
# - if it's cygport has DEPENDS
# -- install it's build-deps
# -- otherwise we have to guess, or rely on an external database of build-deps
# - build the package
# - verify the build binary packages contain the same filelist as the supplied ones ?
#

rm -rf ${BUILDDIR}
mkdir ${BUILDDIR}
tar -C ${BUILDDIR} --strip-components=1 -xvf ${SRCPKG} || exit

CYGPORT=$(ls ${BUILDDIR}/*.cygport)
if [ -z "${CYGPORT}" ] ; then
    echo "No cygport file found"
    exit
fi
# XXX: there must be exactly one cygport file

DEPENDS=$(grep '^DEPENDS=' ${CYGPORT})

if [ -z "${DEPENDS}" ] ; then
    echo "No DEPENDS in cygport file, using guesses"
    DEPENDS=$(cat guessed_depends)
fi

//necker/download/cygwin-${ARCH}/setup-${ARCH} \
    -q -P ${DEPENDS} \
    -l "\\\\necker\download\cygwin-packages" \
    -s http://mirrors.kernel.org/sourceware/cygwin/

cd ${BUILDDIR}

# cygport ${CYGPORT} download || exit
# XXX: all fetchable files should be present in the source package
cygport ${CYGPORT} prep || exit
cygport ${CYGPORT} compile || exit
cygport ${CYGPORT} install || exit
cygport ${CYGPORT} package || exit
