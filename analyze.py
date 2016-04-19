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

# the mapping from cross-host target triples to package prefixes
cross_package_prefixes = {
    'i686-w64-mingw32'   : 'mingw64-i686-',
    'x86_64-w64-mingw32' : 'mingw64-x86_64-',
    'i686-pc-cygwin'     : 'cygwin32-',
    'x86_64-pc-cygwin'   : 'cygwin64-',
}

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
                # does it have a DEPEND line?
                match = re.search('^DEPEND=\s*"(.*?)"', content, re.MULTILINE | re.DOTALL)
                if match:
                    logging.info('srcpkg contains cygport %s, with DEPEND' % fn)
                    depends = set.union(depends_from_depend(match.group(1)),
                                        depends_from_database(srcpkg, indir))
                    return PackageKind('cygport-with-depends', script=fn, depends=','.join(sorted(depends)))
                else:
                    logging.info('srcpkg contains cygport %s' % fn)
                    depends = set.union(depends_from_hints(srcpkg, indir),
                                        depends_from_cygport(content),
                                        depends_from_database(srcpkg, indir))
                    return PackageKind('cygport-guessed-depends', script=fn, depends=','.join(sorted(depends)))

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

                logging.info('srcpkg contains a %s-style build script %s' % (kind, fn))
                depends = set.union(depends_from_hints(srcpkg, indir),
                                    depends_from_cygbuild(),
                                    depends_from_database(srcpkg, indir))
                return PackageKind(kind, script=fn, depends=','.join(sorted(depends)))
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

pkg_to_devel_pkg_map = eval(open('devel_package_map').read())

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
    logging.info('excluded dependencies: %s' % (','.join(sorted(packages))))
    logging.info('runtime dependencies: %s' % (','.join(sorted(runtime_deps))))

    build_deps = set()
    # try some heuristics to transform runtime dependencies to build time
    # dependencies
    for d in runtime_deps:

        # ignore anything provided from this source package
        if d in packages:
            continue

        # anything -devel gets passed straight through
        if d.endswith('-devel'):
            build_deps.add(d)
            continue

        # anything which appears to be a cross-package gets passed straight
        # through (as they don't usually have separate runtime and buildtime
        # packages)
        if any([d.startswith(p) for p in cross_package_prefixes.values()]):
            build_deps.add(d)
            continue

        # transform a dependency on a runtime package to a build-dep on all the
        # devel packages produced from the same source package
        if d in pkg_to_devel_pkg_map:
            devel_pkgs = pkg_to_devel_pkg_map[d]
            logging.info('mapping %s -> %s' % (d, ','.join(sorted(devel_pkgs))))
            for bd in devel_pkgs:
                build_deps.add(bd)

        # runtime deps which are also build time deps
        #
        # (note that due to the dynamic nature of the language, python
        # dependencies probably aren't needed at build time (if tests aren't
        # run), except for cygport to correctly discover them as
        # dependencies...)
        for i in ['perl', 'python', 'python3', 'ruby']:
            if d.startswith(i):
                build_deps.add(d)

    # In code which uses libgpgme-devel, it's possible to use libgpg-error-devel
    # in such a way that it is only a build-time dependency, and doesn't
    # introduce a run-time dependency on libgpg-error0
    if 'libgpgme-devel' in build_deps:
        build_deps.add('libgpg-error-devel')

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

    # if we have any of the inherits in the first list, add the second list to
    # depends
    for (pos, deps) in [
            (['gnome2'], ['gnome-common']),
            (['kf5'], ['cmake', 'extra-cmake-modules']),
            (['mate'], ['mate-common']),
            (['python','python-distutils'], ['python']),
            (['python3', 'python3-distutils'], ['python3']),
            (['texlive'], ['texlive-collection-basic']),  # to ensure correct run-time dependency generation
            (['xfce4'], ['xfce4-dev-tools']),
            (['xorg'], ['xorg-util-macros']),
    ]:
        for i in pos:
            if i in inherits:
                build_deps.update(deps)

    # if it uses autotools, it will want pkg-config
    if ('autotools' in inherits) or (len(inherits) == 0):
        build_deps.add('pkg-config')

    # for cross-packages, we need the appropriate cross-toolchain
    if 'cross' in inherits:
        cross_host = re.search(r'^CROSS_HOST\s*=\s*"?(.*?)"?\s*$', content, re.MULTILINE).group(1)
        pkg_prefix = cross_package_prefixes.get(cross_host, '')
        logging.info('cross_host: %s, pkg_prefix: %s' % (cross_host, pkg_prefix))

        for tool in ['binutils', 'gcc-core', 'gcc-g++', 'pkg-config']:
            build_deps.add('%s%s' % (pkg_prefix, tool))

    logging.info('build dependencies (deduced from inherits): %s' % (','.join(sorted(build_deps))))

    return build_deps


#
# look up build depends in a list we keep
#

# XXX: put this in a separate file
# XXX: should regex match on package name
per_package_deps = {
    'gcc': ['gcc-ada'],  # gnat is required to build gnat
    'git': ['bash-completion-devel'],   # needs updating for separate -devel package
    'gobject-introspection' : ['flex'],
    'maxima': ['recode', 'clisp'],
    'mingw64-i686-fftw3' : ['mingw64-i686-gcc-fortran'],
    'mingw64-x86_64-fftw3' : ['mingw64-x86_64-gcc-fortran'],
    'mutt': ['libxslt','docbook-xsl'],  # to build docbook documentation
    'perl-Unicode-LineBreak': ['libcrypt-devel'], # perl CORE dependency
}

def depends_from_database(srcpkg, indir):
    p = os.path.split(indir)[1]
    build_deps = per_package_deps.get(p, [])
    logging.info('build dependencies (hardcoded for this package): %s' % (','.join(sorted(build_deps))))
    return frozenset(build_deps)

#
# transform a cygport DEPEND atom list into a list of cygwin packages
#

pkgconfig_map = eval(open('pkgconfig-map').read())

def depends_from_depend(depend):
    build_deps = set()

    for atom in depend.split():
        # atoms of the form blah(foo) indicate a module foo of type blah
        match = re.match(r'(.*)\((.*)\)', atom)
        if match:
            deptype = match.group(1)
            module = match.group(2)
            if deptype == 'perl':
                # transform into a cygwin package name
                dep = deptype + '-' + module.replace('::', '-')
                build_deps.add(dep)
            elif deptype == 'pkgconfig':
                # a dependency on the package which contains module.pc
                module = module + '.pc'
                if module in pkgconfig_map:
                    dep = pkgconfig_map[module]
                    logging.info('mapping pkgconfig %s to %s' % (module, ','.join(sorted(dep))))
                    build_deps.update(dep)
                else:
                    logging.warning('could not map pkgconfig %s to a package' % (module))
                # also implies a dependency on pkg-config
                build_deps.add('pkg-config')
            else:
                logging.warning('DEPEND atom of unhandled type %s, module %s' % (deptype, module))
        # otherwise, it is simply a cygwin package name
        else:
            build_deps.add(atom)

    logging.info('build dependencies (from DEPEND): %s' % (','.join(sorted(build_deps))))
    return build_deps

#
# cygbuild style build scripts require quilt
#

def depends_from_cygbuild():
    build_deps = set()
    build_deps.add('quilt')
    logging.info('build dependencies (for cygbuild): %s' % (','.join(sorted(build_deps))))
    return build_deps
