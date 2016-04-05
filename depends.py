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
import re

# XXX: use sets ?!?

def depends(srcpkg, indir):
    runtime_deps = {}

    # scan for setup.hint files, pull out requires:
    for (dirpath, subdirs, files) in os.walk(indir):
        if 'setup.hint' in files:
            with open(os.path.join(dirpath, 'setup.hint')) as fh:
                for l in fh:
                    match = re.match('^requires:(.*)$', l)
                    if match:
                        for d in match.group(1).split():
                            runtime_deps[d] = runtime_deps.get(d, 0) + 1

    print('runtime dependencies: %s' % (','.join(sorted(runtime_deps))))

    build_deps = {}
    # try some heuristics to transform runtime dependencies to build time
    # dependencies
    for d in runtime_deps:
        bd = None

        # libfoosoversion -> libfoo-devel
        match = re.match(r'^lib(.*?)(|\d*)$', d)
        if match:
            bd = 'lib' + match.group(1) + '-devel'

        # libraries with irregular package names
        if d.startswith('zlib'):
            bd = 'zlib-devel'

        # runtime deps which are also build time deps
        if d in ['python', 'python3']:
            bd = d

        if bd:
            build_deps[bd] = build_deps.get(bd, 0) + 1

    # XXX: force gettext-devel to be installed, as cygport currently has a bug
    # which causes it to silently exit if it's not present...
    build_deps['gettext-devel'] = 1

    # if it uses autotools, it will want pkg-config
    build_deps['pkg-config'] = 1

    print('build dependencies (guessed): %s' % (','.join(sorted(build_deps))))

    return ','.join(sorted(build_deps))
