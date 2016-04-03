#!/usr/bin/env python3
#
# adapted from http://m11.iteye.com/blog/2112324
#

import libvirt
import libvirt_qemu
import os
import sys
import time

from libvirt_qemu_ga_utils import guestFileCopyFrom, guestFileCopyTo, guestFileRead, guestFileWrite, guestExec, guestPing


#
#
#
outdir ='/tmp'

conn = libvirt.open(None)
if conn == None:
    print('Failed to open connection to the hypervisor')
    sys.exit(1)

try:
    dom0 = conn.lookupByName("buildvm_85")
except:
    print('Failed to find the domain')
    sys.exit(1)

#dom0.createWithFlags(libvirt.VIR_DOMAIN_START_AUTODESTROY)

# wait for the VM to start up and get into a state where guest-agent can
# respond... XXX: timeout
while True:
    if guestPing(dom0):
        break

    time.sleep(15)

# ensure directory exists and is empty
guestExec(dom0, 'cmd', ['/C','rmdir','/S','/Q', r'C:\\vm_in\\'])
guestExec(dom0, 'cmd', ['/C','mkdir',r'C:\\vm_in\\'])

# install build instructions and source
srcpkg='tzcode-2016c-1-src.tar.xz'
for f in ['carpetbag.sh', 'wrapper.sh', 'guessed_depends', srcpkg]:
    guestFileCopyTo(dom0, f, r'C:\\vm_in\\' + os.path.basename(f))

# attempt the build
success = guestExec(dom0, r'C:\\cygwin64\\bin\\bash.exe', ['-l','/cygdrive/c/vm_in/wrapper.sh', os.path.basename(srcpkg), r'C:\\vm_out'])

# XXX: guest-agent doesn't seem to be capable of capturing output of cygwin
# process (for some strange reason), so we arrange to redirect it to a file and
# collect it here...
print(guestFileRead(dom0, r'C:\\vm_in\\output').decode())

# if the build was successful, fetch build products from VM
if success:
    manifest = os.path.join(outdir, 'manifest')
    guestFileCopyFrom(dom0, r'C:\\vm_out\\manifest', manifest)

    with open(manifest) as f:
        for l in f:
            l = l.strip()
            print(l)
            fn = os.path.join(outdir, l)
            os.makedirs(os.path.dirname(fn), exist_ok=True)
            winpath = l.replace('/',r'\\')
            guestFileCopyFrom(dom0, r'C:\\vm_out\\' + winpath, fn)

#dom0.destroy()
