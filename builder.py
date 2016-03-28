#!/usr/bin/env python2
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
BASE_VMID='Carpetbag_test'
BASE_SNAPSHOT='Snapshot'

# initialize persistent jobid
jobid = 0
try:
    with open('.jobid') as f:
        jobid = int(f.read())
except IOError:
    pass

print(jobid)

#
#
#

def build(srcpkg):
    global jobid
    jobid = jobid + 1
    with open('.jobid', 'w') as f:
        f.write(str(jobid))

    vmid = 'buildvm_%d' % jobid
    credentials = "--username carpetbag --password carpetbag"

    vbm("clonevm " + BASE_VMID + " --snapshot " + BASE_SNAPSHOT + " --options link --name " + vmid + " --register")
    vbm("startvm " + vmid + " --type headless")
    vbm("guestcontrol " + vmid + " mkdir " + credentials + " --parents C:\carpetbag")
    for f in ['carpetbag.sh', 'u2d_wrapper.sh', 'guessed_depends', srcpkg]:
        print(f)
        abswinpath = subprocess.check_output(["cygpath", "-wa", f]).strip()
        vbm("guestcontrol " + vmid + " copyto " + credentials + " " + abswinpath + " C:\\carpetbag\\" + os.path.basename(f))

    vbm("guestcontrol " + vmid + " execute " + credentials + " --wait-exit --wait-stdout --wait-stderr --image C:\\cygwin\\bin\\bash.exe -- -l /cygdrive/c/carpetbag/u2d_wrapper.sh " + srcpkg)
    vbm("controlvm " + vmid + " poweroff")
    # XXX it seems we need to wait while vbox process exits
    time.sleep(1)
    vbm("unregistervm " + vmid + " --delete")

def vbm(subcommand):
    print(subcommand)
    # log = subprocess.check_output([VBM, subcommand], stderr=subprocess.STDOUT)
    # print(log)
