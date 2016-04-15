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

import datetime
import errno
import logging
import os
import shutil
import sqlite3
import tempfile
import time

from dirq.QueueSimple import QueueSimple
from analyze import analyze, PackageKind
from builder import build
from verify import verify

#
debug = True
test = False

#
#
#

class colors:
    reset='\033[0m'
    class fg:
        red='\033[31m'
        green='\033[32m'

def color_result(success):
    if success:
        return colors.fg.green + 'succeeded' + colors.reset
    else:
        return colors.fg.red + 'failed' + colors.reset

#
#
#

# initialize logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
os.makedirs('/var/log/carpetbag', exist_ok=True)

# initialize work queue
carpetbag_root = '/var/lib/carpetbag'
q_root = os.path.join(carpetbag_root, 'dirq')
UPLOADS = os.path.join(carpetbag_root, 'uploads')
QUEUE = 'package_queue'

# initialize persistent jobid
jobid_file = os.path.join(carpetbag_root, 'jobid')
jobid = 0
try:
    with open(jobid_file) as f:
        jobid = int(f.read())
except IOError:
    pass
with open(jobid_file, 'w') as f:
    f.write(str(jobid))

# initialize database
def adapt_datetime(ts):
    return time.mktime(ts.timetuple())

sqlite3.register_adapter(datetime.datetime, adapt_datetime)

conn = sqlite3.connect(os.path.join(carpetbag_root, 'carpetbag.db'))
conn.execute('''CREATE TABLE IF NOT EXISTS jobs
                (id integer primary key, srcpkg text, status text, log text, buildlog text, built integer, valid integer, start_timestamp integer, end_timestamp integer)''')

logging.info('waiting for work on queue %s in %s' % (QUEUE, q_root))
logging.info('uploaded files will be in %s' % (UPLOADS))

dirq = QueueSimple(os.path.join(q_root, QUEUE))

# purge any stale elements, unlock any locked elements
dirq.purge(1, 1)

while True:
    # pull queues
    logging.info('pulling')

    if test:
        remote='jon@tambora:/sourceware/cygwin-staging/queue/'
    else:
        # key should be restricted in authorized_keys with:
        #  'command="$HOME/bin/rrsync /sourceware/cygwin-staging/queue,no-agent-forwarding,no-port-forwarding,no-pty,no-user-rc,no-X11-forwardingh'
        #
        # the key needs to belong to an account which has permissions to remove
        # files from that directory
        remote='cygwin-admin@sourceware.org:'

    rsync_cmd="rsync --recursive --times --itemize-changes --exclude='*.tmp' --remove-source-files"
    os.system('%s %suploads/ %s' % (rsync_cmd, remote, UPLOADS))
    os.system('%s %sdirq/ %s' % (rsync_cmd, remote, q_root))

    # look for work in queue
    logging.info('scanning queue for work')
    for work in dirq:
        if not dirq.lock(work):
            continue

        # increment jobid
        with open(jobid_file) as f:
            jobid = int(f.read())
        jobid = jobid + 1
        with open(jobid_file, 'w') as f:
            f.write(str(jobid))

        # the queue item is the relative path of the srcpkg file
        name = dirq.get(work).decode()
        logging.info('jobid %d: queueing %s' % (jobid, name))

        # store in database
        conn.execute("INSERT INTO jobs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                     (jobid, name, 'pending', '', '', None, None, None, None))
        conn.commit()

        # remove item from queue
        dirq.remove(work)

    # clean up queue
    dirq.purge()

    # look for pending items in database
    pending = list(conn.execute("SELECT id, srcpkg FROM jobs WHERE status = 'pending'"))
    for jobid, name in pending:
        built = False
        valid = None

        # start logging to job logfile
        job_logfile = os.path.join('/var/log/carpetbag', '%d.log' % jobid)
        fh = logging.FileHandler(job_logfile)
        logging.getLogger().addHandler(fh)

        logging.info('jobid %d: processing %s' % (jobid, name))

        #
        reldir = os.path.dirname(name)
        outdir = tempfile.mkdtemp(prefix='carpetbag_')
        indir = os.path.join(UPLOADS, reldir)

        # update in database
        conn.execute("UPDATE jobs SET status = ?, log = ?, start_timestamp = ? WHERE id = ?",
                     ('processing', job_logfile, datetime.datetime.now(), jobid))
        conn.commit()

        status = 'exception'
        try:
            arch = name.split(os.sep)[0]

            srcpkg = os.path.join(UPLOADS, name)

            # examine the source package
            package = analyze(srcpkg, indir)

            if package.kind:
                # build the packages
                build_logfile = os.path.join('/var/log/carpetbag', 'build_%d.log' % jobid)
                built = build(srcpkg, os.path.join(outdir, arch, 'release'), package, jobid, build_logfile, arch)
                if built:
                    # verify built package
                    valid = verify(indir, os.path.join(outdir, reldir))

            # one line summary of this job
            logging.info('jobid %d: processed %s, build %s, verify %s' % (jobid, name, color_result(built), color_result(valid)))

            # clean up
            if not debug:
                logging.info('removing %s' % outdir)
                shutil.rmtree(outdir)
                logging.info('removing %s' % indir)
                shutil.rmtree(indir)

            status = 'processed'
        finally:
            # stop logging to job logfile
            logging.getLogger().removeHandler(fh)

            # update in database
            conn.execute("UPDATE jobs SET status = ?, buildlog = ?, built = ?, valid = ?, end_timestamp = ? WHERE id = ?",
                      (status, build_logfile, built, valid, datetime.datetime.now(), jobid))
            conn.commit()

    # wait a while
    logging.info('waiting')
    if test:
        time.sleep(60)
    else:
        time.sleep(60*60)
