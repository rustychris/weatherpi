import weather_app2

import pandas as pd
import netCDF4

from weather_app2 import db, Site, Sensor, Frame, Sample

## 

# Create a setup for home weather station:
home=Site('rock_feather') 

#temp1=Sensor('temp1','degrees C')
#humid=Sensor('humidity','percent')
#press=Sensor('pressure','Pa')
#light=Sensor('lux','pseudolux')
part1=Sensor('pm1.0','ug m-3')
part2=Sensor('pm2.5','ug m-3')
part3=Sensor('pm10','ug m-3')

for obj in [home,part1,part2,part3]:
    db.session.add(obj)
db.session.commit()

