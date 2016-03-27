#!/bin/sh -x

VBM="/cygdrive/c/Program Files/Oracle/VirtualBox/VBoxManage"

# this is the base VM image we clone for each build
# user 'carpetbag' should be able to log on with an password 'carpetbag'
BASE_VMID=Carpetbag_test
BASE_SNAPSHOT=Snapshot

# this is the VM ID, which should change for every build
VMID=CBS_1

"${VBM}" clonevm ${BASE_VMID} --snapshot ${BASE_SNAPSHOT} --options link --name ${VMID} --register

"${VBM}" modifyvm $(VMID} --vrde on
"${VBM}" startvm ${VMID} --type headless

"${VBM}" guestcontrol ${VMID} mkdir --username carpetbag --password carpetbag --parents 'C:\carpetbag'
"${VBM}" guestcontrol ${VMID} copyto --username carpetbag --password carpetbag --target-directory 'C:\carpetbag' $(cygpath -wa carpetbag.sh)

"${VBM}" guestcontrol ${VMID} run _-verbose --username carpetbag --password carpetbag --exe C:\\cygwin\\bin\\bash.exe -- bash.exe -c /cygdrive/c/carpetbag/carpetbag.sh

"${VBM}" controlvm ${VMID} poweroff

# need to wait while vbox process exits
sleep 1

"${VBM}" unregistervm ${VMID} --delete
