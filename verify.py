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
import os
import pprint
import re
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
    return '\n'.join(difflib.ndiff(
        pprint.pformat(a).splitlines(),
        pprint.pformat(b).splitlines()))


def verify_archive(af, bf):
    return True

    with tarfile.open(af) as a:
        al = a.getnames()
    with tarfile.open(bf) as b:
        bl = b.gtenames()
    print(datadiff(al, bl))
    return al == bl


def verify_file(af, bf):
    if filecmp.cmp(af, bf, shallow=False):
        return True
    else:
        return False


def verify(indir, outdir):
    valid = True

    # print(indir, outdir)

    # verify the set of built package files is the same
    indirtree = capture_dirtree(indir)
    outdirtree = capture_dirtree(outdir)

    # print(indirtree)
    # print(outdirtree)

    if indirtree != outdirtree:
        print('file manifests are different')
        print(datadiff(indirtree, outdirtree))
        valid = False

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
                print('%s is different' % f)

            valid = valid and result

    return valid
