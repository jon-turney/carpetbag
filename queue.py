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

import errno
import os
import shutil
import tempfile

import fsq
from builder import build

carpetbag_root = '/carpetbag'
fsq_root = os.path.join(carpetbag_root, 'fsq')
UPLOADS = os.path.join(carpetbag_root, 'uploads')

fsq.set_const('FSQ_ROOT', fsq_root)
QUEUE = 'package_build_q'

# ensure FSQ_ROOT directory exists
try:
    os.makedirs(fsq_root)
except OSError as e:
    if e.errno == errno.EEXIST:
        pass
    else:
        raise

# ensure our queue exists
try:
    fsq.install(QUEUE, is_triggered=True)
except fsq.exceptions.FSQInstallError as e:
    if e.errno == errno.ENOTEMPTY:
        # queue already exists
        pass
    else:
        raise

print('waiting for work on queue %s in %s' % (QUEUE, fsq_root))
print('uploaded files will be in %s' % (UPLOADS))

# look for work in queue
for work in fsq.scan_forever(QUEUE):
    # only argument is the relative path of the srcpkg file
    srcpkg = os.path.join(UPLOADS, work.arguments[0])
    outdir = tempfile.mkdtemp(prefix='carpetbag')

    if build(srcpkg, outdir):
        fsq.done(work)

        # XXX:
        # verify the set of built binary packages is the same
        # verify each built binary package contain the same filelist

        # XXX: clean up by removing srcpkg from uploads
    else:
        fsq.fail(work)

    shutil.rmtree(outdir)
