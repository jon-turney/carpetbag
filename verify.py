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

import difflib
import filecmp
import logging
import os
import pprint
import re
import sys
import tarfile

#
# capture a directory tree as a dict 'tree', where each key is a directory path
# and the value is a sorted list of filenames
#

def capture_dirtree(basedir):
    tree = {}
    for dirpath, dirnames, filenames in os.walk(basedir):
        tree[os.path.relpath(dirpath, basedir)] = sorted(filenames)

    return tree


def datadiff(a, b):
    return '\n' + '\n'.join(difflib.unified_diff(
        pprint.pformat(a).splitlines(),
        pprint.pformat(b).splitlines(),
        fromfile='upload', tofile='built')).replace('\n\n','\n')


def verify_archive(af, bf):
    with tarfile.open(af) as a, tarfile.open(bf) as b:
        # we want to ignore .sig files in source packages...
        al = [f for f in a.getnames() if not f.endswith('.sig')]
        bl = b.getnames()
        if al != bl:
            logging.warning(datadiff(al, bl))
        return al == bl


def verify_file(af, bf):
    if filecmp.cmp(af, bf, shallow=False):
        return True
    else:
        with open(af) as a, open(bf) as b:
            logging.warning(datadiff(a.read(),b.read()))
        return False


def verify(indir, outdir):
    valid = True
    logging.info('comparing uploaded %s and built %s' % (indir, outdir))

    # verify the set of built package files is the same
    indirtree = capture_dirtree(indir)
    outdirtree = capture_dirtree(outdir)

    # make a copy of indirtree, but replace .bz|.gz|.lzma extensions with .xz,
    # the current compression
    canonindirtree = {}
    for p in indirtree:
        canonindirtree[p] = [re.sub('.(bz2|gz|lzma)$', '.xz', f) for f in indirtree[p]]

    if canonindirtree != outdirtree:
        logging.warning('file manifests are different')
        logging.warning(datadiff(canonindirtree, outdirtree))
        valid = False
    else:
        logging.info('file manifests match, %d files' % (sum([len(indirtree[p]) for p in indirtree])))

    # verify each built binary package contain the same filelist
    for dirpath, dirnames, filenames in os.walk(indir):
        relpath = os.path.relpath(dirpath, indir)

        for f in filenames:
            if not os.path.exists(os.path.join(outdir, relpath, f)):
                continue

            fn = os.path.join(relpath, f)
            # print(fn)

            inf = os.path.join(indir, relpath, f)
            outf = os.path.join(outdir, relpath, f)

            if re.search(r'.tar.(bz2|gz|lzma|xz)$', f):
                result = verify_archive(inf, outf)
            else:
                result = verify_file(inf, outf)

            if not result:
                logging.warning('contents of %s are different' % os.path.join(relpath, f))

            valid = valid and result

            # XXX: major difference in filesizes, modes should be detected ???

    status = 'succeeded' if valid else 'failed'
    logging.info('package contents verification %s' % (status))

    return valid
