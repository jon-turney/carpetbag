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

import errno
import os
import shutil
import tempfile
import time

from dirq.QueueSimple import QueueSimple
from builder import build
from verify import verify

carpetbag_root = '/var/lib/carpetbag'
q_root = os.path.join(carpetbag_root, 'dirq')
UPLOADS = os.path.join(carpetbag_root, 'uploads')

QUEUE = 'package_build_q'

print('waiting for work on queue %s in %s' % (QUEUE, q_root))
print('uploaded files will be in %s' % (UPLOADS))

dirq = QueueSimple(os.path.join(q_root, QUEUE))

# purge any stale elements, unlock any locked elements
dirq.purge(1, 1)

while True:
    # look for work in queue
    for work in dirq:
        if not dirq.lock(work):
            continue

        # the queue item is the relative path of the srcpkg file
        name = dirq.get(work).decode()

        srcpkg = os.path.join(UPLOADS, name)
        reldir = os.path.dirname(name)

        outdir = tempfile.mkdtemp(prefix='carpetbag_')
        indir = os.path.join(UPLOADS, reldir)

        if build(srcpkg, outdir):
            if verify(indir, os.path.join(outdir, reldir)):
                print('package verified')
            else:
                print('package not verified')

        dirq.remove(work)
        dirq.purge()
        # XXX: clean up by removing srcpkg from uploads

        shutil.rmtree(outdir)

    # wait a minute
    time.sleep(60)
