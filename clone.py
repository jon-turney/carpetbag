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

from lxml import etree
import difflib
import libvirt
import os
import stat
import uuid

#
# We want to efficiently make a thin clone, which will not be long-lived
#
# This is hopefully equivalent to doing 'virt-clone --original base_id --name
# clone_id -f clone_image --preserve-data --replace', where clone_image is a
# qcow2 disk image linked to the base disk image, to avoid copying it.
# Obviously, this can't work if the underlying disk image isn't qcow2.
#
# Ideally we would also resume from a paused state, rather than boot the VM from
# scratch...   I'm not sure of the best way to do that with libvirt.
#
# some bits based on modify-domain.py from
# http://www.greenhills.co.uk/2013/03/24/cloning-vms-with-kvm.html
#

def clone(conn, base_id, clone_id):
    # get the XML description of the base_id VM
    base = conn.lookupByName(base_id)
    xmldesc = base.XMLDesc(libvirt.VIR_DOMAIN_XML_SECURE)

    tree = etree.fromstring(xmldesc)
    inxmldesc = etree.tostring(tree, encoding='unicode', pretty_print=True)

    # change name, uuid, device-path, mac-address
    name_el = tree.xpath('/domain/name')[0]
    name_el.text = clone_id

    uuid_el = tree.xpath('/domain/uuid')[0]
    uuid_el.text = str(uuid.uuid1())

    driver_el = tree.xpath("/domain/devices/disk[@device='disk']/driver")[0]
    if driver_el.get('type') != 'qcow2':
        raise Exception("base VM not using qcow2, don't know what to do")

    source_el = tree.xpath("/domain/devices/disk[@device='disk']/source")[0]
    base_file = source_el.get('file')
    clone_file = os.path.join(os.path.dirname(base_file), clone_id + '.qcow2')

    # check that base_file is be read-only, to ensure it isn't being written to
    # by another VM.
    #
    # (This is a more to ensure that people are informed about the risk than a
    # rigorous check.  For example, it should also check any linked base images
    # are read-only)
    if os.stat(base_file).st_mode & stat.S_IWRITE:
        raise Exception("base VM image %s is writeable, too dangerous!" % (base_file))

    os.system('qemu-img create -f qcow2 -b %s %s' % (base_file, clone_file))
    source_el.set('file', clone_file)

    # XXX: how to generate a new mac-address ? what does virt-clone do?
    #mac_el = tree.xpath("/domain/devices/interface[@type='bridge']/mac")[0]
    #mac_el.set('address', options.mac_address)

    outxmldesc = etree.tostring(tree, encoding='unicode', pretty_print=True)
    #print('\n'.join(difflib.ndiff( inxmldesc.splitlines(), outxmldesc.splitlines())))

    conn.defineXML(etree.tostring(tree, encoding='unicode'))

    # return the cloned image filename, to be cleaned up
    return clone_file


def declone(conn, clone_id):
    clone = conn.lookupByName(clone_id)
    clone.undefineFlags(libvirt.VIR_DOMAIN_UNDEFINE_MANAGED_SAVE |
                        libvirt.VIR_DOMAIN_UNDEFINE_SNAPSHOTS_METADATA |
                        libvirt.VIR_DOMAIN_UNDEFINE_NVRAM)
    # XXX: how does virsh undefine --remove-all-storage find the volumes to
    # remove???


if __name__ == "__main__":
    BASE_VMID='Carpetbag'
    conn = libvirt.open(None)
    clone(conn, BASE_VMID, 'clonetest')
    declone(conn, 'clonetest')
