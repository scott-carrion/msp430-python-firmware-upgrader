#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (c) 2011 Chris Liechti <cliechti@gmx.net>
# All Rights Reserved.
# Simplified BSD License (see LICENSE.txt for full text)

"""\
Simple MSP430 BSL implementation using the USB HID interface.
"""

"""
TODO SCC PUT LICENSING AND ALTERATION MESSAGE HERE LATER!!
"""
import tkinter.ttk  # Changed from ttk in Python 2.x
import sys
import os
from msp430.bsl5 import bsl5
import struct
import logging
import time
import pkgutil

from optparse import OptionGroup
import msp430.target
import msp430.memory
from io import StringIO  # Changed from cStringIO in Python 2.x


class HIDBSL5Base(bsl5.BSL5):
    """\
    Implementation of the BSL protocol over HID.

    A subclass needs to implement open(), close(), read_report() and
    write_report().
    """

    def __init__(self):
        bsl5.BSL5.__init__(self)
        self.hid_device = None
        self.logger = logging.getLogger('BSL5')

    def __del__(self):
        self.close()

    def bsl(self, cmd, message='', expect=None, receive_response=True):
        """\
        Low level access to the HID communication.

        This function sends a command and waits until it receives an answer
        (including timeouts). It will return a string with the data part of
        the answer. The first byte will be the response code from the BSL

        If the parameter "expect" is not None, "expect" bytes are expected in
        the answer, an exception is raised if the answer length does not match.
        If "expect" is None, the answer is just returned.

        Frame format:
        +------+-----+-----------+
        | 0x3f | len | D1 ... DN |
        +------+-----+-----------+
        """
        # first synchronize with slave
        print("[bsl()] Control entered bsl()...")

        self.logger.debug('Command 0x%02x (%d bytes)' % (cmd, 1+len(message)))
        print('[bsl()] Command 0x%02x (%d bytes)' % (cmd, 1+len(message)))
        #~ self.logger.debug('Command 0x%02x %s (%d bytes)' % (cmd, message.encode('hex'), 1+len(message)))
        # FIXME SCC: In Python2, struct.pack() returned a string. In Python3, it returns a bytes object
        txdata = bytearray(struct.pack('<BBB', 0x3f, 1+len(message), cmd).decode("utf8") + message, encoding="utf8")
        txdata += b'\xac'*(64 - len(txdata)) # pad up to block size

        print('Sending command: %r %d Bytes' % (txdata, len(txdata)))
        #~ self.logger.debug('Sending command: %r %d Bytes' % (txdata.encode('hex'), len(txdata)))
        # transmit command
        self.write_report(txdata)
        
        if receive_response:
            self.logger.debug('Reading answer...')
            print('Reading answer...')
            report = self.read_report()
            
            if sys.platform == 'darwin':
                
                self.logger.debug('report = %r' % report)
                print('report = %r' % report)
 
            else:
                # self.logger.debug('report = %r' % report.encode('hex'))
                self.logger.debug('report = %r' % report)
                print('report = %r' % report)
                
            pi = report[0]
            # XXX FIXME SCC This is a bad comparison because pi is of type bytes (and subscripting it is of type int) and the comparison is with a string literal (not the same!) 
            # Fixing this by comparing with integer 0x3f instead
            if pi == 0x3f:
                length = report[1]
                data = report[2:2+length]
                #~ if expect is not None and len(data) != expect:
                    #~ raise bsl5.BSL5Error('expected %d bytes, got %d bytes' % (expect, len(data)))
                return data
            else:
                if pi: raise bsl5.BSL5Error('received bad PI, expected 0x3f (got 0x%02x)' % (pi,))
                raise bsl5.BSL5Error('received bad PI, expected 0x3f (got empty response)')


# some platform specific code follows
if sys.platform == 'win32':
    from pywinusb import hid
    import ctypes
    import Queue

    class HIDBSL5(HIDBSL5Base):
        """\
        HID support for running on Windows.
        """
        def open(self, device=None):
            if device is None:
                filter = hid.HidDeviceFilter(vendor_id = 0x2047, product_id = 0x0200)
                all_devices = filter.get_devices()
                try:
                    self.hid_device = all_devices[0]
                except IndexError:
                    raise ValueError('USB VID:PID 2047:0200 not found (not in BSL mode? or try --device)')
            else:
                #~ ... by serial number?
                raise ValueError("don't (yet) know how to handle --device")
            self.logger.info('Opening HID device %r' % (self.hid_device,))
            self.hid_device.open()
            self.hid_device.set_raw_data_handler(self._data_input_handler)
            self.receiving_queue = Queue.Queue()

        def close(self):
            """Close port"""
            if self.hid_device is not None:
                self.logger.info('closing HID device')
                try:
                    self.hid_device.close()
                except:
                    self.logger.exception('error closing device:')
                self.hid_device = None

        def _data_input_handler(self, data):
            #~ print "Raw data: %r" % data
            self.receiving_queue.put(''.join(chr(x) for x in data))

        def write_report(self, data):
            # clear input queue. we can do this because we expect at most one
            # answer per written report and no spontaneous messages
            while self.receiving_queue.qsize():
                self.receiving_queue.get_nowait()
            # write report
            self.hid_device.send_output_report([ctypes.c_ubyte(x) for x in data])

        def read_report(self):
            return self.receiving_queue.get()



elif sys.platform == 'darwin':
    import hid

    class HIDBSL5(HIDBSL5Base):
        """\
        HID support for running on Mac
        """
        def open(self, device=None):
            if device is None:
                try:
                    self.hid_device = hid.device(0x2047, 0x200)
                 
                except IndexError:
                    raise ValueError('USB VID:PID 2047:0200 not found (not in BSL mode? or try --device)')
            else:
                #~ ... by serial number?
                raise ValueError("don't (yet) know how to handle --device")
            self.logger.info('Opening HID device %r' % (self.hid_device,))
    
       
        def close(self):
            """Close port"""
            if self.hid_device is not None:
                self.logger.info('closing HID device')
                try:
                    self.hid_device.close()
                except:
                    self.logger.exception('error closing device:')
                self.hid_device = None
                
        
        def write_report(self, data):
                       
            # write report
            return self.hid_device.write(data)

        def read_report(self):
            
            result = list()
            temp_buf = list()
            size = 64
            while size > 0:
                count = min(size, 64)
                buf = self.hid_device.read(count)
                
                if len(buf) < count:
                    raise IOError("reading from device failed")
                temp_buf += buf
                
                size -= count
                #convert items in list to ascii values
                for i in range(len(temp_buf)):
                    result += str(chr(temp_buf[i]))
            
            return result
            
        
else:
    import glob
    class HIDBSL5(HIDBSL5Base):
        """\
        HID support for running on Linux (systems with /dev/hidraw*).
        """

        def open(self, device=None):
            if device is None:
                # try to auto detect device
                self.logger.debug('HID device auto detection using sysfs')
                for path in glob.glob('/sys/class/hidraw/hidraw*'):
                    try:
                        #~ self.logger.debug('trying %r' % (path,))
                        for line in open(os.path.join(path, 'device/uevent')):
                            if 'HID 2047:0200' in line:
                                device = os.path.join('/dev', os.path.basename(path))
                                break
                    except IOError:
                        pass # file could not be opened
            if device is None: raise ValueError('USB VID:PID 2047:0200 not found (not in BSL mode? or try --device)')

            self.logger.info('Opening HID device %r' % (device,))
            self.hid_device = os.open(device, os.O_RDWR)

        def close(self):
            """Close port"""
            if self.hid_device is not None:
                self.logger.info('closing HID device')
                try:
                    os.close(self.hid_device)
                except:
                    self.logger.exception('error closing device:')
                self.hid_device = None

        def write_report(self, data):
            os.write(self.hid_device, data)

        def read_report(self):
            return os.read(self.hid_device, 64)


# and now back to multi-platform code

class HIDBSL5Target(HIDBSL5, msp430.target.Target):
    """Combine the HID BSL5 backend and the common target code."""
    def __init__(self):
        msp430.target.Target.__init__(self)
        HIDBSL5.__init__(self)

    def add_extra_options(self):
                
        group = OptionGroup(self.parser, "Communication settings")

        group.add_option("-d", "--device",
                dest="device",
                help="device name (default: auto detection)",
                default=None)

        self.parser.add_option_group(group)

        group = OptionGroup(self.parser, "BSL settings")

        group.add_option("--password",
                dest="password",
                action="store",
                help="transmit password before doing anything else, password is given in given (TI-Text/ihex/etc) file",
                default=None,
                metavar="FILE")

        self.parser.add_option_group(group)


    def close_connection(self):
        self.close()


    def open_connection(self):
        self.logger = logging.getLogger('BSL')
        self.open(self.options.device)

        # only fast mode supported by USB boot loader
        self.use_fast_mode = True
        self.buffer_size = 48

        if self.options.do_mass_erase:
            self.logger.info("Mass erase...")
            try:
                self.BSL_RX_PASSWORD('\xff'*30 + '\0'*2)
            except bsl5.BSL5Error:
                pass # it will fail - that is our intention to trigger the erase
            time.sleep(1)
            # after erase, unlock device
            self.BSL_RX_PASSWORD('\xff'*32)
            # remove mass_erase from action list so that it is not done
            # twice
            self.remove_action(self.mass_erase)
        else:
            if self.options.password is not None:
                password = msp430.memory.load(self.options.password).get_range(0xffe0, 0xffff)
                self.logger.info("Transmitting password: %s" % (password.encode('hex'),))
                self.BSL_RX_PASSWORD(password)

        # download full BSL
        if self.verbose:
            sys.stderr.write('Download full BSL...\n')
        bsl_version_expected = (0x00, 0x08, 0x08, 0x39)
        basedir = os.path.dirname(__file__)
        full_bsl_txt = open(os.path.join(basedir, 'RAM_BSL_00.08.08.39.txt'), 'rb').read()
        full_bsl = msp430.memory.load('BSL', StringIO(full_bsl_txt), format='titext')
        self.program_file(full_bsl, quiet=True)
        self.BSL_LOAD_PC(0x2504)


        # must re-initialize communication, BSL or USB system needs some time
        # to be ready
        self.logger.info("Waiting for BSL...")
        time.sleep(3)
        """
        The ttk progress bar update is required for MAC in order for application to find the HID device after
        closing it.  If this call is not there, then the call to open HID device fails.
        """
        if sys.platform == 'darwin':
            self.updateBar()
                 
        self.close()
        self.open(self.options.device)

        # checking version, this is also a connection check
        # This does not work in Linux. os.read(self.hid_device, 64) will hang forever
        # waiting for a response...
        if sys.platform == 'win32' or sys.platform == 'cygwin':
                bsl_version = self.BSL_VERSION()
                if bsl_version_expected !=  bsl_version:
                        self.logger.error("BSL version mismatch (continuing anyway)")
                else:
                        self.logger.debug("BSL version OK")

        #~ # Switch back to mode where we get ACKs
        #~ self.use_fast_mode = False
 
    """
    This function call is provided for application to find HID device after closing it.  If this call is not made
    detection of HID device fails after time.sleep(3) is called.
    """
                        
    def updateBar(self):
         ttk.Progressbar().update()
        
     

def main():
    # run the main application
    bsl_target = HIDBSL5Target()
    bsl_target.main()

if __name__ == '__main__':
    main()
