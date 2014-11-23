"""
The MIT License (MIT)

Copyright (c) 2014 Sergio Rubio <rubiojr@frameos.org>

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

Reading temperature from a Garmin Tempe sensor using a Suunto Movestick mini USB.

Requirements:

https://github.com/rubiojr/python-ant (fork form Johannes Bader that includes some fixes)
An ANT+ USB stick
A Garmin Tempe

Notes:

Get the "ANT message protocol and usage" document from:

  http://www.thisisant.com/developer/resources/downloads/#documents_tab

You'll also need the Environment device profile from (registration required):

  http://www.thisisant.com/developer/ant-plus/device-profiles


Based on Heart rate reading code from Martin Raul Villalba:

https://github.com/mvillalba/python-ant/blob/develop/demos/ant.core/04-processevents.py

"""

import sys
import time
import struct

from ant.core import driver
from ant.core import node
from ant.core import event
from ant.core import message
from ant.core.constants import *

# ANT+ network key
# From http://www.thisisant.com/developer/ant-plus/ant-plus-basics/network-keys
NETKEY = '\xB9\xA5\x21\xFB\xBD\x72\xC3\x45'

SERIAL = '/dev/ttyUSB0'

MANUFACTURERS = {
    1:  'Garmin',
    3:  'Zephyr',
    5:  'IDT',
    11: 'Tanita',
    15: 'Dynastream',
    23: 'Suunto',
    32: 'Wahoo Fitness',
    37: 'Magellan',
    68: 'CATEYE'
}

# A run-the-mill event listener
class TempeListener(event.EventCallback):
    def process(self, msg):
        if isinstance(msg, message.ChannelBroadcastDataMessage):
            try:
                page_id = ord(msg.payload[1])
                if page_id == 1:
                    # Data page 1, temperature info
                    # bytes 6,7 indicate temperature, LSB first
                        temp = struct.unpack("<h", "".join(msg.payload[-2:]))[0] * 0.01
                        print 'Temperature: %.2f C' % temp

                elif page_id == 80:
                    # Manufacturer identification received
                    mid = struct.unpack("h", "".join(msg.payload[-4:-2]))[0]
                    print 'Manufacturer ID: %i (%s)' % (mid, MANUFACTURERS[mid])

                elif page_id == 81:
                    # Product info received
                    print 'Device Serial: ', struct.unpack("i", "".join(msg.payload[-4:]))[0]
                elif page_id == 82:
                    # no idea what page 82 is for...
                    pass

            except Exception as e:
                print "Error reading temperature value"
                print e

# Initialize, USB2Driver uses libusb
stick = driver.USB2Driver(SERIAL, debug=False, log=None)
antnode = node.Node(stick)
antnode.start()

# Read (stick) capabilities
print 'Stick capabilities:'
capabilities = antnode.getCapabilities()
print 'Maximum channels:', capabilities[0]
print 'Maximum network keys:', capabilities[1]
print 'Standard options: %X' % capabilities[2][0]
print 'Advanced options: %X' % capabilities[2][1]

# Setup channel
key = node.NetworkKey('N:ANT+', NETKEY)
antnode.setNetworkKey(0, key)
channel = antnode.getFreeChannel()
channel.name = 'C:ENV'

# 0x00 Bidirectional Slave Channel
#
# The USB stick (slave) will primarily receive but can still transmit
# in the reverse direction.
channel.assign('N:ANT+', CHANNEL_TYPE_TWOWAY_RECEIVE)

# Channel ID
#
# device type, device number, transmission type
# 0 means wildcard, wildcards only allowed in the slave
#
# * Device type:
#   - 25 is for Environment sensors like the Tempe
#   - 119 is for weight scales
#   - 120 for Heart Rate sensors
#
channel.setID(25, 0, 0)

# Channel Extended Assignment?
#
# Background scanning among other things
channel.setSearchTimeout(0x2D)
#channel.setSearchTimeout(TIMEOUT_NEVER)

# Channel period (message rate)
#
# From 0.5Hz to above 200Hz, value is calculated from:
# 32768/Message Rate
#
# i.e. 32768/8192 = 4Hz
#
# The environment sensor transmits main data pages at a default
# 0.5Hz or 4Hz rate
channel.setPeriod(8192) # 4 Hz
#channel.setPeriod(65535) # 0.5 Hz

# Set the channel frequency
#
# From 2400Hz to 2524
# If we want to set the frequency to 2457, then:
# 2457 - 2400 = RF freq value
#
# RF Channel 57 (2457MHz) is used for the ANT+ environment device
#
channel.setFrequency(57)

print 'Opening the channel...'
channel.open()

channel.registerCallback(TempeListener())

# Wait
print "Listening for Tempe events..."
while True:
    try:
        time.sleep(120)
    except KeyboardInterrupt:
        print "\nClosing channel, wait please..."
        channel.close()
        channel.unassign()
        antnode.stop()
        sys.exit(0)
