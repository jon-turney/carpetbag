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
import logging
import libvirt
import time

from libvirt_qemu_ga_utils import guestFileCopyFrom, guestFileCopyTo, guestFileRead, guestFileWrite, guestExec, guestPing
from clone import clone
import steptimer

#
debug = False

# this is the base VM image for each arch that we clone for each build
#
# base cygwin installed
# package cygport installed
#
BASE_VMID = {
    'x86_64': 'virtio',
    'x86':    'virtio',
    'noarch': 'virtio',
}

# path to bash, for each arch
bash_path = {
    'x86_64': r'C:\\cygwin64\\bin\\bash.exe',
    'x86':    r'C:\\cygwin\\bin\\bash.exe',
    'noarch': r'C:\\cygwin64\\bin\\bash.exe',
}

#
# clone a fresh VM, build the given |srcpkg| in it, retrieve the build products
# to |outdir|, and discard the VM
#

def build(srcpkg, outdir, package, jobid, logfile, arch):
    logging.info('building %s to %s' % (os.path.basename(srcpkg), outdir))

    steptimer.start()
    vmid = 'buildvm_%d' % jobid

    # open a libvirt connection to hypervisor
    libvirt.virInitialize()
    libvirt.virEventRegisterDefaultImpl()
    conn = libvirt.open('qemu:///system')
    if conn == None:
        logging.error('Failed to open connection to the hypervisor')
        return False

    # create VM
    clone_storage = clone(conn, BASE_VMID[arch], vmid)
    steptimer.mark('clone vm')

    domain = conn.lookupByName(vmid)

    # start vm, automatically clean up when we are done, unless debugging
    domain.createWithFlags(libvirt.VIR_DOMAIN_START_AUTODESTROY if not debug else 0)

    # wait for vm to boot up
    wait_for_guest_agent(conn, domain, 5*60)
    guestPing(domain)

    steptimer.mark('boot')

    # ensure directory exists and is empty
    guestExec(domain, 'cmd', ['/C', 'rmdir', '/S', '/Q', r'C:\\vm_in\\'])
    guestExec(domain, 'cmd', ['/C', 'mkdir', r'C:\\vm_in\\'])

    # install build instructions and source
    for f in ['build.sh', 'wrapper.sh', srcpkg]:
        guestFileCopyTo(domain, f, r'C:\\vm_in\\' + os.path.basename(f))

    if package.depends:
        guestFileWrite(domain, r'C:\\vm_in\\depends', bytes(package.depends, 'ascii'))

    steptimer.mark('put')

    # attempt the build
    success = guestExec(domain, bash_path[arch], ['-l','/cygdrive/c/vm_in/wrapper.sh', os.path.basename(srcpkg), r'C:\\vm_out', package.script, package.kind])
    steptimer.mark('build')

    # XXX: guest-agent doesn't seem to be capable of capturing output of cygwin
    # process (for some strange reason), so we arrange to redirect it to a file
    # and collect it here...
    guestFileCopyFrom(domain, r'C:\\vm_in\\output', logfile)
    logging.info('build logfile is %s' % (logfile))

    # if the build was successful, fetch build products from VM
    if success:
        os.makedirs(outdir, exist_ok=True)
        manifest = os.path.join(outdir, 'manifest')
        guestFileCopyFrom(domain, r'C:\\vm_out\\manifest', manifest)

        with open(manifest) as f:
            for l in f:
                l = l.strip()
                fn = os.path.join(outdir, l)
                os.makedirs(os.path.dirname(fn), exist_ok=True)
                winpath = l.replace('/',r'\\')
                guestFileCopyFrom(domain, r'C:\\vm_out\\' + winpath, fn)

    steptimer.mark('fetch')

    if not debug:
        # terminate the VM.  Don't bother giving it a chance to shut down
        # cleanly since we won't be using it again
        domain.destroy()

        # clean up VM
        domain.undefineFlags(libvirt.VIR_DOMAIN_UNDEFINE_MANAGED_SAVE |
                             libvirt.VIR_DOMAIN_UNDEFINE_SNAPSHOTS_METADATA |
                             libvirt.VIR_DOMAIN_UNDEFINE_NVRAM)
        os.remove(clone_storage)
        steptimer.mark('destroy vm')

    status = 'succeeded' if success else 'failed'
    logging.info('build %s, %s' % (status, steptimer.report()))

    return success

#
# wait for the VM to start up and get into a state where guest-agent can
# respond
#
# sometimes the guest agent seems to break and not start properly, so have a
# timeout to deal with that case...
#
# (XXX: really this is a bit inside-out; this module might be better rewritten
# as a state machine which responds to events from the domain)
#

def wait_for_guest_agent(conn, domain, timeout):
    done = False

    def timeoutEventCallback(timer, opaque):
        logging.info("timeout event:")
        nonlocal done
        done = True

    def domainEventAgentLifecycleCallback (conn, dom, state, reason, opaque):
        logging.info("agentLifecycle event: domain '%s' state %d reason %d" % (dom.name(), state, reason))
        if state == libvirt.VIR_CONNECT_DOMAIN_EVENT_AGENT_LIFECYCLE_STATE_CONNECTED:
            nonlocal done
            done = True

    timer_id = libvirt.virEventAddTimeout(timeout*1000, timeoutEventCallback, None)

    conn.domainEventRegisterAny(domain, libvirt.VIR_DOMAIN_EVENT_ID_AGENT_LIFECYCLE, domainEventAgentLifecycleCallback, None)

    while not done:
        libvirt.virEventRunDefaultImpl()

    libvirt.virEventRemoveTimeout(timer_id)
