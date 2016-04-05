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

from collections import namedtuple
import logging
import os
import re
import tarfile


PackageKind = namedtuple('PackageKind', 'kind script depends')

#
# analyze the source package
#

def analyze(srcpkg, indir):
    try:
        with tarfile.open(srcpkg) as tf:
            cygports = [m for m in tf.getmembers() if re.search(r'\.cygport$', m.name)]

            # more than one cygport!
            if len(cygports) > 1:
                logging.error('srcpkg %s contains multiple .cygport files' % srcpkg)
                return PackageKind(None, '', '')

            # exactly one cygport file
            if len(cygports) == 1:
                fn = cygports[0].name
                f = tf.extractfile(cygports[0])
                content = f.read().decode()
                # does it have a DEPENDS line?
                if re.search('^DEPENDS', content, re.MULTILINE):
                    logging.info('srcpkg contains cygport %s, with DEPENDS' % fn)
                    return PackageKind('cygport-with-depends', script=fn)
                else:
                    logging.info('srcpkg contains cygport %s' % fn)
                    depends = set.union(depends_from_hints(srcpkg, indir),
                                        depends_from_cygport(content),
                                        depends_from_database(srcpkg))
                    return PackageKind('cygport-guessed-depends', script=fn, depends= ','.join(sorted(depends)))

            # if there's no cygport file, we look for a g-b-s style .sh file instead
            scripts = [m for m in tf.getmembers() if re.search(r'\.sh$', m.name)]
            if len(scripts) == 1:
                fn = scripts[0].name
                f = tf.extractfile(scripts[0])

                # analyze it's content to classify as cygbuild or g-b-s
                # (some copies of cygbuild contain a latin1 encoded 'í' i-acute)
                content = f.read().decode(errors='replace')
                if re.search('^CYGBUILD', content, re.MULTILINE):
                    kind = 'cygbuild'
                else:
                    kind = 'g-b-s'

                depends = set.union(depends_from_hints(srcpkg, indir),
                                    depends_from_database(srcpkg))

                logging.info('%s script %s' % (kind, fn))
                return PackageKind(kind, script=fn, depends=depends)
            elif len(scripts) > 1:
                logging.error('too many scripts in srcpkg %s', srcpkg)
                return PackageKind(None, '', '')

        logging.error("couldn't find build instructions in srcpkg %s" % srcpkg)
        return PackageKind(None, '', '')
    except tarfile.ReadError:
        logging.error("couldn't read srcpkg %s" % srcpkg)
        return PackageKind(None, '', '')

#
# guess at build depends, by looking at setup.hints
#

def depends_from_hints(srcpkg, indir):
    runtime_deps = set()
    packages = [os.path.split(indir)[1]]

    # scan for setup.hint files, pull out requires:
    for (dirpath, subdirs, files) in os.walk(indir):
        if 'setup.hint' in files:
            with open(os.path.join(dirpath, 'setup.hint')) as fh:
                for l in fh:
                    match = re.match('^requires:(.*)$', l)
                    if match:
                        for d in match.group(1).split():
                            runtime_deps.add(d)

        packages.extend(subdirs)

    # provided packages will be excluded from guessed dependencies
    logging.info('excluded: %s' % (','.join(sorted(packages))))
    logging.info('runtime dependencies: %s' % (','.join(sorted(runtime_deps))))

    build_deps = set()
    # try some heuristics to transform runtime dependencies to build time
    # dependencies
    for d in runtime_deps:
        bd = None

        # ignore anything provided from this source package
        if d in packages:
            continue

        # anything -devel gets passed straight through
        if re.match(r'^.*-devel$', d):
            build_deps.add(d)
            continue

        # libfoosoversion -> libfoo-devel
        match = re.match(r'^lib(.*?)(?!devel)([\d_.]*)$', d)
        if match:
            bd = 'lib' + match.group(1) + '-devel'

        # libraries with irregular package names
        if d.startswith('zlib'):
            bd = 'zlib-devel'

        # runtime deps which are also build time deps
        if d in ['python', 'python3']:
            bd = d

        if bd:
            build_deps.add(bd)

    # XXX: force gettext-devel to be installed, as cygport currently has a bug
    # which causes it to silently exit if it's not present...
    build_deps.add('gettext-devel')

    logging.info('build dependencies (guessed): %s' % (','.join(sorted(build_deps))))

    return build_deps



#
# guess at build depends, by looking at the cygport
#

def depends_from_cygport(content):
    build_deps = set()
    inherits = set()

    for l in content.splitlines():
        match = re.match('^inherit(.*)', l)
        if match:
            inherits.update(match.group(1).split())

    logging.info('cygport inherits: %s' % ','.join(sorted(inherits)))

    if 'xfce4' in inherits:
        build_deps.add('xfce4-dev-tools')

    # if it uses autotools, it will want pkg-config
    if ('autotools' in inherits) or (len(inherits) == 0):
        build_deps.add('pkg-config')

    logging.info('build dependencies (deduced from inherits): %s' % (','.join(sorted(build_deps))))

    return build_deps


#
# look up build depends in a list we keep
#

def depends_from_database(srcpkg):
    return frozenset()
