#!/bin/sh -x
# this script is executed on the guest

#
# given a src package, this will
#
# - unpack the src packagez
# - install it's build-deps
# - build the package
# - copy the built dist files into OUTDIR
#

# SRCPKG names the source package filename
SRCPKG=$1
# OUTDIR names the directory where output is placed
OUTDIR=$(cygpath -ua $2)
# SCRIPT names the build script to invoke
SCRIPT=$3
# KIND is the kind of build we do
KIND=$4

# extract PVR
PVR=${SRCPKG%-src.tar.*}

# this is the directory we will work in
BUILDDIR=/build

#
ARCH=$(uname -m)
SETUP_ARCH=${ARCH/i686/x86}

# unpack the src package into work directory
rm -rf ${BUILDDIR}
mkdir ${BUILDDIR}
tar -C ${BUILDDIR} -xvf ${SRCPKG} || exit 1

# install the build dependencies
case ${KIND} in
    'g-b-s'|'cygbuild'|\
    'cygport-guessed-depends')
        DEPENDS=$(cat depends)
    ;;
    'cygport-with-depends')
        # evaluate the DEPENDS variable defined by the cygport script
        DEPENDS=$(source ${SCRIPT} ; echo ${DEPENDS})
    ;;
esac

if [ -n "${DEPENDS}" ] ; then
    //polidori/public/setup/setup-${SETUP_ARCH} \
                             -q -P ${DEPENDS} \
                             -s 'file:////polidori/public/cygwin'
fi

# move to the directory containing the build script
cd ${BUILDDIR}
cd $(dirname ${SCRIPT})
SCRIPT=$(basename ${SCRIPT})

case ${KIND} in
    'cygport-with-depends'|\
    'cygport-guessed-depends')
        # We don't do 'cygport ${SCRIPT} download' as all fetchable files should
        # already be present in the source package
        cygport ${SCRIPT} prep || exit 1
        # XXX: magically handle postinstall/preremove.sh
        cygport ${SCRIPT} compile || exit 1
        cygport ${SCRIPT} install || exit 1
        cygport ${SCRIPT} package || exit 1
        # this is where build products are found
        if [ -d "${PVR}.${ARCH}/dist" ] ; then
            PRODUCT=${PVR}.${ARCH}/dist
        else
            PRODUCT=${PVR}.noarch/dist
        fi
        ;;
    'g-b-s'|'cygbuild')
        ./${SCRIPT} almostall || exit 1
        # XXX: Doesn't set PRODUCT because I don't know how to separate source
        # and products of g-b-s or cygbuild
        ;;
esac

# copy build products to OUTDIR and write a file manifest
rm -rf ${OUTDIR}
mkdir -p ${OUTDIR}

if [ -n "${PRODUCT}" ] ; then
    cp -aT ${PRODUCT} ${OUTDIR}
fi

cd ${OUTDIR}
find * -type f >manifest
