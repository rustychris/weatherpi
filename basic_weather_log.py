# coding: utf-8

import os
import smbus
from RPiSensors import htu21d
import requests
import logging
import time
import logging.handlers

# settings
if 0: # old phant setup
    # Publishing to data.sparkfun.com
    public_url="http://data.sparkfun.com/streams/MGvanEzE4vsZRlEj1Ygw"
    public_key="MGvanEzE4vsZRlEj1Ygw"
    private_key="nzombegeDoIgbZdnPGwM"
    delete_key="3ZlLrdgd1lcVQaW6wY1x"
else:
    public_url="http://rustyholleman.com/cgi/weather2.fcgi/data/rockridge/input"
    private_key="nzombegeDoIgbZdnPGwM"

bus_num=1 # some boards it's 0.


# Set up logging
log=logging.getLogger('weather')
log.setLevel(logging.INFO)
log.handlers=[] # log is persistent!
fh=logging.handlers.RotatingFileHandler('weather.log',maxBytes=1024**3,
                                        backupCount=3)

fh.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
fh.setFormatter(formatter)
log.addHandler(fh)


import mpl3115a2
log.info('Testing MPL3115a2')
mpl3115=mpl3115a2.Mpl3115A2()
for i in range(2):
    press,temp=mpl3115.press_temp()
    log.info('Pressure=%.2f temp=%.3f'%(press,temp))

log.info('Initializing HTU21D')
sensor = htu21d.Htu21d(bus_num,use_temperature=True)
log.info('Humidity %.3f'%sensor.humidity)
log.info('Temp %.3f'%sensor.temperature)

from ads1115 import ADS1115

class LightSensor(object):
    def __init__(self):
        self.adc=ADS1115()
    def light_raw(self):
        return self.adc.read_adc(channel=0)
    def light_lux(self):
        # total fiction!
        # figure that the saturation level 3.3V  - 0.4 = 2.9V
        # that's something like 10,000 lux.
        # what's the reference for the ADC? 
        return self.light_raw() / 10. 
    
# first it read 661
# with an extra light on, gets 700.
log.info('Initialize light sensor')
light=LightSensor()
log.info('Light level: %.3f'%light.light_lux())


def Tconv(degc):
    return 32.0 + 9./5*degc

def maybe_reboot():
    hostname="192.168.1.1"
    response = os.system("ping -c 5 -q " + hostname + " > /dev/null 2>&1")
    if response==0:
        log.info("Pinged 192.168.1.1 successfully, not rebooting")
    else:
        log.warning("Rebooting")
        os.system("sync")
        os.system("sync")
        os.system("sudo shutdown -r now")
        log.warning("Reboot should be coming - pausing for 20 seconds.")
        time.sleep(20)
        log.warning("This shouldn't be reached!")
    
def publish():
    params=dict(private_key=private_key)
    try:
        params['humidity']=sensor.humidity
        params['temp1']=Tconv(sensor.temperature)
        params['pressure'],temp2=mpl3115.press_temp()
        params['temp2']=Tconv(temp2)
        params['lux']=light.light_lux()
    except Exception as exc:
        log.error('Failed to read sensor(s)')
        log.error(str(exc))
        return
    # url=("http://data.sparkfun.com/input/" + public_key)
    url=("http://rustyholleman.com/cgi/weather2.fcgi/data/rockridge/input")
    try:
        resp=requests.get(url,params=params)
    except Exception as exc:
        log.error('Failed to publish data')
        log.error(str(exc))
        maybe_reboot()
        return
    log.info('Read/publish successful %.1f %.1f %.0f %.1f %.1f'%(params['humidity'],
                                                                 params['temp1'],
                                                                 params['pressure'],
                                                                 params['temp2'],
                                                                 params['lux']))


publish()


while 1:
    try:
        publish()
    except Exception as exc:
        print "Got an exception"
        print exc
    time.sleep(120)

