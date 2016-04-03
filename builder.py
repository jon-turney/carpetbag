#!/usr/bin/env python3
#
# Copyright (c) 2016 Jon Turney
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#

import os
import libvirt
import subprocess
import time
from datetime import timedelta

from libvirt_qemu_ga_utils import guestFileCopyFrom, guestFileCopyTo, guestFileRead, guestFileWrite, guestExec, guestPing

# this is the base VM image we clone for each build
#
# base cygwin installed
# package cygport installed
#
BASE_VMID='Carpetbag'

# initialize persistent jobid
jobid = 0
try:
    with open('.jobid') as f:
        jobid = int(f.read())
except IOError:
    pass


#
# clone a fresh VM, build the given |srcpkg| in it, retrieve the build products
# to |outdir|, and discard the VM
#

def build(srcpkg, outdir):
    global jobid
    jobid = jobid + 1
    with open('.jobid', 'w') as f:
        f.write(str(jobid))

    print('jobid %d: building %s to %s' % (jobid, srcpkg, outdir))

    start_time = time.time()
    vmid = 'buildvm_%d' % jobid

    # XXX: create depends, which can be produced by guessing heuristic or an
    # external database of build-deps

    # create VM
    # XXX: use --reflink if btrfs is available
    # XXX: programmatically do this...
    os.system("virt-clone --original %s --name %s --auto-clone --replace" % (BASE_VMID, vmid))

    # open a libvirt connection to hypervisor
    conn = libvirt.open(None)
    if conn == None:
        print('Failed to open connection to the hypervisor')
        return False

    domain = conn.lookupByName(vmid)

    # start vm, automatically clean up when we are done
    domain.createWithFlags(libvirt.VIR_DOMAIN_START_AUTODESTROY)

    # wait for the VM to start up and get into a state where guest-agent can
    # respond... XXX: timeout
    time.sleep(60*5)
    while True:
        if guestPing(domain):
            break

        time.sleep(15)

    # ensure directory exists and is empty
    guestExec(domain, 'cmd', ['/C', 'rmdir', '/S', '/Q', r'C:\\vm_in\\'])
    guestExec(domain, 'cmd', ['/C', 'mkdir', r'C:\\vm_in\\'])

    # install build instructions and source
    for f in ['carpetbag.sh', 'wrapper.sh', 'guessed_depends', srcpkg]:
        guestFileCopyTo(domain, f, r'C:\\vm_in\\' + os.path.basename(f))

    # attempt the build
    success = guestExec(domain, r'C:\\cygwin64\\bin\\bash.exe', ['-l','/cygdrive/c/vm_in/wrapper.sh', os.path.basename(srcpkg), r'C:\\vm_out'])

    # XXX: guest-agent doesn't seem to be capable of capturing output of cygwin
    # process (for some strange reason), so we arrange to redirect it to a file
    # and collect it here...
    print(guestFileRead(domain, r'C:\\vm_in\\output').decode())

    # if the build was successful, fetch build products from VM
    if success:
        manifest = os.path.join(outdir, 'manifest')
        guestFileCopyFrom(domain, r'C:\\vm_out\\manifest', manifest)

        with open(manifest) as f:
            for l in f:
                l = l.strip()
                # print(l)
                fn = os.path.join(outdir, l)
                os.makedirs(os.path.dirname(fn), exist_ok=True)
                winpath = l.replace('/',r'\\')
                guestFileCopyFrom(domain, r'C:\\vm_out\\' + winpath, fn)

    # terminate the VM.  Don't bother giving it a chance to shut down cleanly
    # since we won't be using it again
    domain.destroy()

    # clean up VM
    domain.undefineFlags(libvirt.VIR_DOMAIN_UNDEFINE_MANAGED_SAVE |
                         libvirt.VIR_DOMAIN_UNDEFINE_SNAPSHOTS_METADATA |
                         libvirt.VIR_DOMAIN_UNDEFINE_NVRAM)

    end_time = time.time()
    elapsed_time = round(end_time-start_time+0.5)
    status = 'succeeded' if success else 'failed'
    print('jobid %d: %s, elapsed time %s' % (jobid, status, timedelta(seconds=elapsed_time)))

    return success
