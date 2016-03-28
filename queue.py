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

import fsq
from builder import build

#fsq.set_const('FSQ_ROOT', '/foo/fsq')
QUEUE = 'cpbq'
UPLOADS = '/uploads'

fsq_root = fsq.const('FSQ_ROOT')

# ensure FSQ_ROOT exists
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

# look for work in queue
for work in fsq.scan_forever(QUEUE):
    print(' '.join(work.arguments))
    # only argument is the relative path of the srckg file
    build(os.path.join(UPLOADS, work.arguments[0]))
    fsq.done(work)
