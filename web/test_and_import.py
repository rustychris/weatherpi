import weather_app2
reload(weather_app2)

import requests
import pandas as pd
import netCDF4
import utils

from weather_app2 import db, Site, Sensor, Frame, Sample

## 

# fresh start:
db.drop_all()
db.create_all()

# Create a setup for home weather station:
home=Site('rockridge') # this is now failing??

temp1=Sensor('temp1','degrees C')
temp2=Sensor('temp2','degrees C')
humid=Sensor('humidity','percent')
press=Sensor('pressure','Pa')
light=Sensor('lux','pseudolux')

for obj in [home,temp1,temp2,humid,press,light]:
    db.session.add(obj)
db.session.commit()

## 

csv_path="volatile/rockridge/sparkfun-dump.csv"

# Import existing readings from data.sparkfun:
if 0:
    data_sf_url="http://data.sparkfun.com/output/MGvanEzE4vsZRlEj1Ygw"
    csv_url=data_sf_url+".csv"
    req=requests.get(csv_url)
    with open(csv_path,'wt') as fp:
        fp.write(req.text)

##      
# note that this is in reverse chrono, and temperatures are deg F
all_sf=pd.read_csv(csv_path,parse_dates=['timestamp'])

# coming soon
all_sf.sort_values('timestamp',inplace=True)

## 
site=Site.query.filter_by(name='rockridge').first()

if 1:
    # for 25k records, this takes ~60s...
    site.import_dataframe(all_sf.set_index('timestamp'))
    
## 

# dataframe with timestamp as index, and a column for each sensor reading
site.update_h5_raw()

## 

query_start=pd.Timestamp('2016-07-23 00:00')
query_end = pd.Timestamp('2016-07-31 00:00')

# in memory: 272us
# result=df[ (df.index>=query_start) & (df.index<=query_end) ]
# print result.shape

## 

# Write a decimated version
store=pd.HDFStore(os.path.join(site.data_path(),'weather.h5'))

raw=store['raw']

# 1ms.
result=raw[ (raw.timestamp>=utils.to_unix(query_start)) &
                    (raw.timestamp<=utils.to_unix(query_end)) ]


## hourly:

hours=raw.timestamp//3600

hourly=raw.groupby(hours).agg( [np.min,np.mean,np.max] )

# drop multiindex by compounding the names
new_cols=['_'.join(col) for col in hourly.columns]
hourly.columns=new_cols

# can't use a multiindex *and* have searchable data
hourly.to_hdf(os.path.join(site.data_path(),'weather.h5'),
              'd3600',format='t',data_columns=True)

# so basically have to make sure that the arrays written out
# are dense, and we cache some information like the starting, step, stop
# index.

##

# A bit annoying to carry around the H5 baggage in addition to
# the sqlite database.
# how painful would it be to just deal with the database directly,
# and automatically generate a compiled, semi-denormalized table?
# and how slow to query a timeseries from it?

# or maybe just add the code to the site object?
