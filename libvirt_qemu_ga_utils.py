#!/usr/bin/env python3
#
# Utility functions for file transfer to/from and process execution in a QEMU
# guest.
#
# These are operations supported by the QEMU Guest Agent since version 2.5
#
# These are implemented on top of libvirt_qemu.qemuAgentCommand(), by applying
# that to json sequences we construct here.
#
# Ideally, these operations would be supported by libvirt, but not yet...
#
# Thanks to http://m11.iteye.com/blog/2112324 for giving an example of how to
# use this
#

import base64
import json
import libvirt
import libvirt_qemu
import re
import time

#
#
#

# XXX: take care: an unescaped '\' in a path is not permitted in json
def execute_ga_command(instance, command):
    # print("command %s" % re.sub('"buf-b64":".*"', '"buf-b64":"..."', command))
    result = libvirt_qemu.qemuAgentCommand(instance, command, libvirt_qemu.VIR_DOMAIN_QEMU_AGENT_COMMAND_BLOCK, 0)
    json_result = json.loads(result)
    # print("result %s " % re.sub('"buf-b64":".*"', '"buf-b64":"..."', json.dumps(json_result, sort_keys=True, indent=4)))
    return json_result


#
# ping the guest agent
#

PING = """{"execute":"guest-ping"}"""
def guestPing(domain):
    # XXX: push exception handling into execute_ga_command
    try:
        result = execute_ga_command(domain, PING)
    except libvirt.libvirtError:
        return False

    return 'return' in result


#
# copy a file to or from the guest
#

FILE_OPEN = """{"execute":"guest-file-open", "arguments":{"path":"%s","mode":"%s"}}"""
FILE_READ = """{"execute":"guest-file-read", "arguments":{"handle":%s,"count":%d}}"""
FILE_WRITE = """{"execute":"guest-file-write", "arguments":{"handle":%s,"buf-b64":"%s"}}"""
FILE_CLOSE = """{"execute":"guest-file-close", "arguments":{"handle":%s}}"""

# It's a property of QMP that messages have some upper limit in size, but we
# aren't sure how much...  ; we also must allow for the overhead of the json
# structure the data is encapsulated in
CHUNK = 4096

def guestFileRead(instance, path):
    file_handle = -1
    try:
        file_handle = execute_ga_command(instance, FILE_OPEN % (path, 'r'))["return"]
        # XXX: hard-coded constant
        file_content = execute_ga_command(instance, FILE_READ % (file_handle, 1024000))["return"]["buf-b64"]
    except Exception as ex:
        print(Exception,":",ex)
        return None
    finally:
        execute_ga_command(instance, FILE_CLOSE % file_handle)
    return base64.standard_b64decode(file_content)


def guestFileCopyFrom(instance, guestPath, hostPath):
    file_handle = execute_ga_command(instance, FILE_OPEN % (guestPath, 'r'))['return']
    with open(hostPath, 'wb') as f:
        while True:
            result = execute_ga_command(instance, FILE_READ % (file_handle, CHUNK))["return"]
            if result['eof']:
                break

            encoded_content = result['buf-b64']
            content = base64.standard_b64decode(encoded_content)
            f.write(content)

    execute_ga_command(instance, FILE_CLOSE % file_handle)

def guestFileWrite(instance, path, content):
    content = base64.standard_b64encode(content).decode('ascii')
    file_handle = -1
    try:
        file_handle = execute_ga_command(instance, FILE_OPEN % (path, 'w+'))["return"]
        write_count = execute_ga_command(instance, FILE_WRITE % (file_handle, content))["return"]["count"]
    except Exception as ex:
        print(Exception,":",ex)
        return -1
    finally:
        execute_ga_command(instance, FILE_CLOSE % file_handle)
    return write_count


def guestFileCopyTo(instance, hostPath, guestPath):
    file_handle = execute_ga_command(instance, FILE_OPEN % (guestPath, 'w+'))["return"]
    with open(hostPath, 'rb') as f:
        while True:
            content = f.read(CHUNK)
            if not content:
                break

            encoded_content = base64.standard_b64encode(content).decode('ascii')
            write_count = execute_ga_command(instance, FILE_WRITE % (file_handle, encoded_content))["return"]["count"]

            # if write_count != content, there is some kind of error...
            if write_count != len(content):
                print("write error %d %d" % (write_count, len(content)))

    execute_ga_command(instance, FILE_CLOSE % file_handle)

#
# invoke a command in the guest
# capture it's exitstatus and output
#

GUEST_EXEC       ="""{"execute":"guest-exec", "arguments":{"path":"%s", "arg":[%s], "capture-output": true}}"""
GUEST_EXEC_STATUS="""{"execute":"guest-exec-status", "arguments":{"pid":%s}}"""

def guestExec(instance, command, params):
    print(command, ' '.join(params))
    paramlist = ','.join(['"%s"' % p for p in params])
    pid = execute_ga_command(instance, GUEST_EXEC % (command, paramlist))["return"]["pid"]

    # poll for "exited" to change from "false", to indicate process has
    # finished...  XXX: timeout
    while True:
        result = execute_ga_command(instance, GUEST_EXEC_STATUS % (pid))['return']

        if result['exited']:
            break

        time.sleep(1)

    exitcode = result['exitcode']
    print('exitcode %d' % exitcode)

    if 'out-data' in result:
        stdout = base64.standard_b64decode(result['out-data'])
        if 'out-truncated' in result:
            stdout += '(truncated)'
        print('stdout', stdout)

    if 'err-data' in result:
        stderr = base64.standard_b64decode(result['err-data'])
        if 'err-truncated' in result:
            stderr += '(truncated)'
        print('stderr', stderr)

    return (exitcode == 0)
