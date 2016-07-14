# from https://gist.github.com/pepijndevos/c3646ef6652e0f0342dd
from smbus import SMBus

class Mpl3115A2(object):
    #I2C ADDRESS/BITS
    ADDRESS = (0x60)

    #REGISTERS
    REGISTER_STATUS = (0x00)
    REGISTER_STATUS_TDR = 0x02
    REGISTER_STATUS_PDR = 0x04
    REGISTER_STATUS_PTDR = 0x08

    REGISTER_PRESSURE_MSB = (0x01)
    REGISTER_PRESSURE_CSB = (0x02)
    REGISTER_PRESSURE_LSB = (0x03)

    REGISTER_TEMP_MSB = (0x04)
    REGISTER_TEMP_LSB = (0x05)

    REGISTER_DR_STATUS = (0x06)

    OUT_P_DELTA_MSB = (0x07)
    OUT_P_DELTA_CSB = (0x08)
    OUT_P_DELTA_LSB = (0x09)

    OUT_T_DELTA_MSB = (0x0A)
    OUT_T_DELTA_LSB = (0x0B)

    BAR_IN_MSB = (0x14)
    BAR_IN_LSB = (0x15)

    WHOAMI = (0x0C)

    #BITS

    PT_DATA_CFG = 0x13
    PT_DATA_CFG_TDEFE = 0x01
    PT_DATA_CFG_PDEFE = 0x02
    PT_DATA_CFG_DREM = 0x04

    CTRL_REG1 = (0x26)
    CTRL_REG1_SBYB = 0x01
    CTRL_REG1_OST = 0x02
    CTRL_REG1_RST = 0x04
    CTRL_REG1_OS1 = 0x00
    CTRL_REG1_OS2 = 0x08
    CTRL_REG1_OS4 = 0x10
    CTRL_REG1_OS8 = 0x18
    CTRL_REG1_OS16 = 0x20
    CTRL_REG1_OS32 = 0x28
    CTRL_REG1_OS64 = 0x30
    CTRL_REG1_OS128 = 0x38
    CTRL_REG1_RAW = 0x40
    CTRL_REG1_ALT = 0x80
    CTRL_REG1_BAR = 0x00
    CTRL_REG2 = (0x27)
    CTRL_REG3 = (0x28)
    CTRL_REG4 = (0x29)
    CTRL_REG5 = (0x2A)

    REGISTER_STARTCONVERSION = (0x12)

    def __init__(self):
        self.bus = SMBus(1)
        self.verify_device()
        self.initialize()

    def verify_device(self):
        whoami = self.bus.read_byte_data(self.ADDRESS, self.WHOAMI)
        if whoami != 0xc4:
            # 0xc4 is a default value, but it can be programmed to other
            # values.  Mine reports 0xee.
            print "Device not active: %x != %x"%(whoami,0xc4)
            return False
        return True

    def initialize(self):
        self.bus.write_byte_data(
            self.ADDRESS,
            self.CTRL_REG1,
            self.CTRL_REG1_SBYB |
            self.CTRL_REG1_OS128 |
            self.CTRL_REG1_ALT)

        self.bus.write_byte_data(
            self.ADDRESS,
            self.PT_DATA_CFG, 
            self.PT_DATA_CFG_TDEFE |
            self.PT_DATA_CFG_PDEFE |
            self.PT_DATA_CFG_DREM)

    def poll(self,flag=None):
        if flag is None:
            flag=self.REGISTER_STATUS_PDR
        sta = 0
        while not (sta & self.REGISTER_STATUS_PDR):
            sta = self.bus.read_byte_data(self.ADDRESS, self.REGISTER_STATUS)

    def altitude():
        self.bus.write_byte_data(
            self.ADDRESS,
            self.CTRL_REG1, 
            self.CTRL_REG1_SBYB |
            self.CTRL_REG1_OS128 |
            self.CTRL_REG1_ALT)

        self.poll()

        msb, csb, lsb = self.bus.read_i2c_block_data(self.ADDRESS,
                                                     self.REGISTER_PRESSURE_MSB,3)
        alt = ((msb<<24) | (csb<<16) | (lsb<<8)) / 65536.

        # correct sign
        if alt > (1<<15):
            alt -= 1<<16

        return alt

    def temperature(self):
        self.bus.write_byte_data(
            self.ADDRESS,
            self.CTRL_REG1,
            self.CTRL_REG1_SBYB |
            self.CTRL_REG1_OS128 |
            self.CTRL_REG1_BAR)
        self.poll()
        return self.read_temperature()
    
    def read_temperature(self):
        msb, lsb = self.bus.read_i2c_block_data(self.ADDRESS,
                                                self.REGISTER_TEMP_MSB,2)
        # 12 bit, 2s-complement in degrees C.
        return ( (msb<<8) | lsb) / 256.0 

    def pressure(self):
        self.bus.write_byte_data(
            self.ADDRESS,
            self.CTRL_REG1, 
            self.CTRL_REG1_SBYB |
            self.CTRL_REG1_OS128 |
            self.CTRL_REG1_BAR)

        self.poll()
        return self.read_pressure()
    
    def press_temp(self):
        self.bus.write_byte_data(
            self.ADDRESS,
            self.CTRL_REG1, 
            self.CTRL_REG1_SBYB |
            self.CTRL_REG1_OS128 |
            self.CTRL_REG1_BAR)

        self.poll(self.REGISTER_STATUS_PDR|self.REGISTER_STATUS_TDR)
        press=self.read_pressure()
        temp=self.read_temperature()
        return press,temp
    def read_pressure(self):
        msb, csb, lsb = self.bus.read_i2c_block_data(self.ADDRESS,
                                                     self.REGISTER_PRESSURE_MSB,3)
        return ((msb<<16) | (csb<<8) | lsb) / 64.

    def calibrate(self):
        pa = int(self.pressure()/2)
        self.bus.write_i2c_block_data(self.ADDRESS, 
                                      self.BAR_IN_MSB, 
                                      [pa>>8 & 0xff, pa & 0xff])
