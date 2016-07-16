# Copyright (c) 2016 Adafruit Industries
# Author: Tony DiCola
# Modified by Rusty Holleman
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

import time
import smbus

class ADS1115(object):
    """Base functionality for ADS1x15 analog to digital converters."""
    # Register and other configuration values:
    DEFAULT_ADDRESS        = 0x48
    POINTER_CONVERSION     = 0x00
    POINTER_CONFIG         = 0x01
    POINTER_LOW_THRESHOLD  = 0x02
    POINTER_HIGH_THRESHOLD = 0x03
    CONFIG_OS_SINGLE       = 0x8000
    CONFIG_MUX_OFFSET      = 12
    # Mapping of gain values to config register values.
    CONFIG_GAIN = {
        2./3: 0x0000,
        1:   0x0200,
        2:   0x0400,
        4:   0x0600,
        8:   0x0800,
        16:  0x0A00
    }
    CONFIG_MODE_CONTINUOUS  = 0x0000
    CONFIG_MODE_SINGLE      = 0x0100
    # Mapping of data/sample rate to config register values for ADS1115 (slower).
    CONFIG_DR = {
        8:    0x0000,
        16:   0x0020,
        32:   0x0040,
        64:   0x0060,
        128:  0x0080,
        250:  0x00A0,
        475:  0x00C0,
        860:  0x00E0
    }
    CONFIG_COMP_WINDOW      = 0x0010
    CONFIG_COMP_ACTIVE_HIGH = 0x0008
    CONFIG_COMP_LATCHING    = 0x0004
    CONFIG_COMP_QUE = {
        1: 0x0000,
        2: 0x0001,
        4: 0x0002
    }
    CONFIG_COMP_QUE_DISABLE = 0x0003

    def __init__(self, address=None, bus_num=1, **kwargs):
        if address is None:
            address=self.DEFAULT_ADDRESS
        self.address=address
        self.bus=smbus.SMBus(bus_num)

    def _read(self, mux, gain, data_rate, mode):
        """Perform an ADC read with the provided mux, gain, data_rate, and mode
        values.  Returns the signed integer result of the read.
        """
        config = self.CONFIG_OS_SINGLE  # Go out of power-down mode for conversion.
        # Specify mux value.
        config |= (mux & 0x07) << self.CONFIG_MUX_OFFSET
        # Validate the passed in gain and then set it in the config.
        if gain not in self.CONFIG_GAIN:
            raise ValueError('Gain must be one of: 2./3, 1, 2, 4, 8, 16')
        config |= self.CONFIG_GAIN[gain]
        # Set the mode (continuous or single shot).
        config |= mode
        # Get the default data rate if none is specified (default differs between
        # ADS1015 and ADS1115).
        if data_rate is None:
            data_rate = self._data_rate_default()
        # Set the data rate (this is controlled by the subclass as it differs
        # between ADS1015 and ADS1115).
        config |= self._data_rate_config(data_rate)
        config |= self.CONFIG_COMP_QUE_DISABLE  # Disable comparator mode.
        # Send the config value to start the ADC conversion.
        # Explicitly break the 16-bit value down to a big endian pair of bytes.
        self._device_writeList(self.POINTER_CONFIG, 
                               [(config >> 8) & 0xFF, config & 0xFF])
        # Wait for the ADC sample to finish based on the sample rate plus a
        # small offset to be sure (0.1 millisecond).
        time.sleep(1.0/data_rate+0.0001)
        # Retrieve the result.
        result = self._device_readList(self.POINTER_CONVERSION, 2)
        return self._conversion_value(result[1], result[0])

    def _device_writeList(self,register,values):
        self.bus.write_i2c_block_data(self.address, register, values)
    def _device_readList(self,register,nbytes):
        return self.bus.read_i2c_block_data(self.address,register,nbytes)    
    def read_adc(self, channel, gain=1, data_rate=None):
        """Read a single ADC channel and return the ADC value as a signed integer
        result.  Channel must be a value within 0-3.
        """
        assert 0 <= channel <= 3, 'Channel must be a value within 0-3!'
        # Perform a single shot read and set the mux value to the channel plus
        # the highest bit (bit 3) set.
        return self._read(channel + 0x04, gain, data_rate, self.CONFIG_MODE_SINGLE)
    def _data_rate_default(self):
        # Default from datasheet page 16, config register DR bit default.
        return 128

    def _data_rate_config(self, data_rate):
        if data_rate not in self.CONFIG_DR:
            raise ValueError('Data rate must be one of: 8, 16, 32, 64, 128, 250, 475, 860')
        return self.CONFIG_DR[data_rate]

    def _conversion_value(self, low, high):
        # Convert to 16-bit signed value.
        value = ((high & 0xFF) << 8) | (low & 0xFF)
        # Check for sign bit and turn into a negative value if set.
        if value & 0x8000 != 0:
            value -= 1 << 16
        return value




