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

#
# Utility for timing the steps of the build process
#

import time
from datetime import timedelta

steptimes = []
# XXX: this is bad and I feel bad

def mark(name):
    steptimes.append((name, time.time()))

def start():
    steptimes = []
    mark('--start--')

def format_delta(e):
    e = round(e+0.5)
    return timedelta(seconds=e)

def report():
    end_time = time.time()

    out = []
    for (n,t) in steptimes:
        if n != '--start--':
            e = t - prev_time
            out.append('%s %s' % (n, format_delta(e)))
        else:
            start_time = t

        prev_time = t

    total_time = end_time - start_time
    return 'total time %s (%s)' % (format_delta(total_time), ', '.join(out))


if __name__ == "__main__":
    start()
    time.sleep(1)
    mark('clone')
    time.sleep(2)
    mark('startup')
    time.sleep(3)
    mark('build')
    print(report())
