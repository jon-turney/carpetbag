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
import subprocess
import time
from datetime import timedelta

# path to invoke VBoxManage
VBM="/cygdrive/c/Program Files/Oracle/VirtualBox/VBoxManage"

# this is the base VM image we clone for each build
#
# user 'carpetbag' should be able to log on with an password 'carpetbag'
# user 'carpetbag' should have adminstrator rights
# base cygwin installed
# package unix2dos installed
# package cygport installed
#
BASE_VMID='Carpetbag'
BASE_SNAPSHOT='Snapshot'

# initialize persistent jobid
jobid = 0
try:
    with open('.jobid') as f:
        jobid = int(f.read())
except IOError:
    pass


def abswinpath(path):
    return subprocess.check_output(["cygpath", "-wa", path]).decode().strip()

#
# clone a fresh VM, build the given |srcpkg| in it, retrieve the build products
# to |outdir|, and discard the VM
#
# Note that guestcontrol seems to have various bugs in VirtualBox 5.0 which
# currently make this unworkable, so use VirtualBox 4.3

def build(srcpkg, outdir):
    global jobid
    jobid = jobid + 1
    with open('.jobid', 'w') as f:
        f.write(str(jobid))

    print('jobid %d: building %s to %s' % (jobid, srcpkg, outdir))

    start_time = time.time()
    vmid = 'buildvm_%d' % jobid
    credentials = "--username carpetbag --password carpetbag"

    # XXX: create depends, which can be produced by guessing heuristic or an
    # external database of build-deps

    # create VM
    vbm("clonevm " + BASE_VMID + " --snapshot " + BASE_SNAPSHOT + " --options link --name " + vmid + " --register")
    vbm("startvm " + vmid + " --type headless")

    # install build instructions and source
    vbm("guestcontrol " + vmid + " mkdir " + credentials + " --parents C:\\vm_in")
    for f in ['carpetbag.sh', 'u2d_wrapper.sh', 'guessed_depends', srcpkg]:
        vbm("guestcontrol " + vmid + " copyto " + credentials + " " + abswinpath(f) + " C:\\vm_in\\" + os.path.basename(f))

    # attempt the build
    success = vbm("guestcontrol " + vmid + " execute " + credentials + " --wait-exit --wait-stdout --wait-stderr --image C:\\cygwin\\bin\\bash.exe -- -l /cygdrive/c/vm_in/u2d_wrapper.sh " + os.path.basename(srcpkg) + " C:\\vm_out")

    # if the build was successful, fetch build products from VM
    if success:
        manifest = os.path.join(outdir, 'manifest')
        vbm("guestcontrol " + vmid + " copyfrom " + credentials + " C:\\vm_out\\manifest " + abswinpath(manifest))

        with open(manifest) as f:
            for l in f:
                l = l.strip()
                # print(l)
                fn = os.path.join(outdir, l)
                winpath = subprocess.check_output(["cygpath", "-w", l]).strip()
                vbm("guestcontrol " + vmid + " copyfrom " + credentials + " C:\\vm_out\\" + winpath + " " + abswinpath(fn))

    # clean up VM
    vbm("controlvm " + vmid + " poweroff")
    # XXX it seems we need to wait while vbox process exits
    time.sleep(1)
    vbm("unregistervm " + vmid + " --delete")

    end_time = time.time()
    elapsed_time = round(end_time-start_time+0.5)
    status = 'succeeded' if success else 'failed'
    print('jobid %d: %s, elapsed time %s' % (jobid, status, timedelta(seconds=elapsed_time)))

    return success


def vbm(subcommand):
    print(subcommand)
    result = False

    try:
        log = subprocess.check_output([VBM] + subcommand.split(), stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as e:
        log = e.output
    else:
        result = True

    print(log)
    return result
