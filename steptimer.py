#!/usr/bin/env python3
#
# Utility for timing the steps of the build process
#

import time
from datetime import timedelta

steptimes = []

def mark(name):
    steptimes.append((name, time.time()))

def start():
    mark('start')

def format_delta(e):
    e = round(e+0.5)
    return timedelta(seconds=e)

def report():
    mark('end')

    out = []
    for (n,t) in steptimes:
        print(n, t)
        if n == 'start':
            start_time = t
            prev_time = t
            continue
        elif n == 'end':
            end_time = t

        e = t-prev_time
        if e > 1:
            out.append('%s %s' % (n, format_delta(e)))

        prev_time = t

    total_time = end_time-start_time
    return 'total time %s (%s)' % (format_delta(total_time), ', '.join(out))



start()
time.sleep(1)
mark('clone')
time.sleep(2)
mark('startup')
time.sleep(3)
mark('build')
print(report())
