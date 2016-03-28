#!/bin/sh -x

VBM="/cygdrive/c/Program Files/Oracle/VirtualBox/VBoxManage"

# this is the base VM image we clone for each build
#
# user 'carpetbag' should be able to log on with an password 'carpetbag'
# user 'carpetbag' should have adminstrator rights
# base cygwin installed
# package unix2dos installed
# package cygport installed
#
BASE_VMID=Carpetbag_test
BASE_SNAPSHOT=Snapshot

# this is the VM ID, which should change for every build
VMID=CBS_1

# XXX: some test data
SRCPKG='dmalloc-5.5.2-2-src.tar.xz'

"${VBM}" clonevm ${BASE_VMID} --snapshot ${BASE_SNAPSHOT} --options link --name ${VMID} --register
"${VBM}" startvm ${VMID} --type headlessxo

# currently broken in virtualbox 5.0, use 4.3
"${VBM}" guestcontrol ${VMID} mkdir --username carpetbag --password carpetbag --parents 'C:\carpetbag'
for i in carpetbag.sh u2d_wrapper.sh ${SRCPKG} guessed_depends ; do
    "${VBM}" guestcontrol ${VMID} copyto --username carpetbag --password carpetbag $(cygpath -wa $i) 'C:\carpetbag\'$i
done
"${VBM}" guestcontrol ${VMID} execute --username carpetbag --password carpetbag --wait-exit --wait-stdout --wait-stderr --image C:\\cygwin\\bin\\bash.exe -- '-l' '/cygdrive/c/carpetbag/u2d_wrapper.sh' ${SRCPKG} >vm.log


cat vm.log
echo

"${VBM}" controlvm ${VMID} poweroff
# need to wait while vbox process exits
sleep 1
"${VBM}" unregistervm ${VMID} --delete
