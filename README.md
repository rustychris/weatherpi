# weatherpi

Temp1 errors:

 After a year or so, temp1 began showing an error increasingly often of about 26.47 deg
 (39.64 instead of 66.11, based on adjacent measurements)
 
 That's 14.71 degC error

temp2 is from the pressure sensor, temp1 from HTU21D humidity sensor.
When temp1 is bad, humidity is also reported maxed out high.  When
temp1 has a single good reading, humidity is bad, but if temp1 is good
for a handful of samples, then seems that humidity will be okay, too.

The HTU21D could employ some caching, but it appears disabled.
Code calls self._update() twice, once for humidity, once for temp.
CRC is read but not used in current source.  Could switch to
https://github.com/vitiral/linsensors/blob/master/linsensors/htu21d.py
which does include crc check.


ADS1115 has 10k pullups for SDA and SCL.  Also ferrite beads on GND
and Vdd, with some corrosion visible on the Vdd ferrite.

Looks like the weather shield has 4.7k pullups on both, combined
with some 3.3V => 5V conversion circuitry.

