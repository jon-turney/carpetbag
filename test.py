#!/usr/bin/env python3

import os
import random
import re
import shutil
import sys

from dirq.QueueSimple import QueueSimple

carpetbag_root = '/var/lib/carpetbag'
q_root = os.path.join(carpetbag_root, 'dirq')
UPLOADS = os.path.join(carpetbag_root, 'uploads')

QUEUE = 'package_queue'
dirq = QueueSimple(os.path.join(q_root, QUEUE))

if len(sys.argv) > 1:
    # a package was specified on the command line
    p = sys.argv[1]

    if len(sys.argv) > 2:
        arch = sys.argv[2]
    else:
        arch = 'x86_64'
else:
    # otherwise, pick a random package
    package_list = []

    with open('cygwin-pkg-maint') as f:
        for l in f:
            match = re.match(r'^(\S+)\s+(.+)$', l)
            if match:
                pkg = match.group(1)
                package_list.append(pkg)

    p = random.choice(package_list)
    arch = random.choice(['x86_64', 'x86'])

# find srcpkg for the latest (according to mtime) version
mtime = 0
version = ''
filename = ''

packagedir = os.path.join('/var/ftp/pub/cygwin', arch, 'release', p)
for f in os.listdir(packagedir):
    if re.search(r'-src.tar.(bz2|gz|lzma|xz)$', f):
        check_mtime = os.path.getmtime(os.path.join(packagedir, f))
        if check_mtime > mtime:
            match = re.match(r'^' + re.escape(p) + r'-(.+)-(\d[0-9a-zA-Z.]*)(-src|)\.tar\.(bz2|gz|lzma|xz)$', f)
            version = match.group(1) + '-' + match.group(2)
            mtime = check_mtime
            filename = f

print('picked %s %s' % (p, version))

# copy files with matching version, and setup.hint, as if uploaded
for (dirpath, subdirs, files) in os.walk(packagedir):
    relpath = os.path.relpath(dirpath, packagedir)

    for f in files:
        match = re.match(r'^.*-' + re.escape(version) + r'(-src|)\.tar\.(bz2|gz|lzma|xz)$', f)
        if match or f == 'setup.hint':
            fr = os.path.join(dirpath, f)
            to = os.path.join(UPLOADS, arch, 'release', p, relpath, f)
            os.makedirs(os.path.dirname(to), exist_ok=True)
            print('copying %s to %s' % (fr, to))
            shutil.copy2(fr, to)

# add it to the queue
srcpkg = os.path.join(arch, 'release', p, filename)
print('enqueued %s' % (srcpkg))
dirq.add(srcpkg)
