#  simplify life a bit by having just a single ledger,
#  hardcoded with the sensors which actually exist

import os
import datetime
from matplotlib.dates import date2num,num2date
import pandas as pd
import numpy as np
import utils
import re
from flask import (Flask, request, session, g, redirect, url_for, abort, 
                   render_template, flash )

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import UniqueConstraint

root_dir=os.path.dirname(__file__)

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(root_dir,'volatile','sensors.db')
db = SQLAlchemy(app)

# 

class Site(db.Model):
    id=db.Column(db.Integer, primary_key=True)
    name=db.Column(db.String(50))

    def __init__(self,name):
        self.name=name
    def __repr__(self):
        return '<Site %s>'%self.name

    def import_dataframe(self,df):
        # map columns of the dataframe to sensors:
        # nonmatches set to None (i.e. timestamp)
        sensors=[Sensor.query.filter_by(name=col).first()
                 for col in df.columns]

        reci=0
        for tstamp,rec in df.iterrows():
            reci+=1
            if reci % 500 == 0:
                print "%d/%d"%(reci,len(df))
                
            frame=Frame(tstamp,self)
            db.session.add(frame)
            for sensor,value in zip(sensors,rec):
                if sensor:
                    if sensor.units=='degree C':
                        value=(value-32) * 5/9.
                    samp=Sample(sensor,frame,value)
                    db.session.add(samp)

        db.session.commit()        
    def all_samples(self):
        query=db.session.query(Sample.value,Sample.flag,
                               Sensor.name,
                               Frame.timestamp).\
               filter(Sample.frame_id==Frame.id).\
               filter(Sample.sensor_id==Sensor.id).\
               filter(Frame.site_id == self.id)

        # faster than constructing the objects 
        rows=db.session.execute(query).fetchall()
        return rows
    def all_samples_dataframe(self):
        rows=self.all_samples()
        df=pd.DataFrame( rows, columns=['value','flag','parameter','timestamp'])
        # loses flag.  oh well.
        df=df.pivot('timestamp','parameter','value')
        return df
    def data_path(self,create=True):
        path=os.path.join( 'volatile',self.name)
        if create and not os.path.exists(path):
            os.makedirs(path)
        return path
        
    def update_h5_raw(self):
        df=self.all_samples_dataframe()
        df=df.reset_index()
        t0=pd.Timestamp('1970-01-01 00:00:00') # unix epoch
        df['timestamp']=(df.timestamp-t0)/np.timedelta64(1,'s')

        df.to_hdf(os.path.join(self.data_path(),'weather.h5'),
                  'raw',format='t',data_columns=True)
        
    
class Frame(db.Model): # when
    id=db.Column(db.Integer, primary_key=True)
    timestamp=db.Column(db.DateTime)
    site_id=db.Column(db.Integer,db.ForeignKey('site.id'))
    site=db.relationship('Site',backref=db.backref('frames',lazy='dynamic'))

    __table_args__ = (
        UniqueConstraint("timestamp", "site_id"),
    ) 

    def __init__(self,timestamp,site):
        self.timestamp=timestamp
        self.site=site
    def __repr__(self):
        return '<Frame %s %s>'%(self.site.name,self.timestamp)
    
class Sensor(db.Model): # what is being measured
    id=db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(20))
    units = db.Column(db.String(20))

    def __init__(self, name, units):
        self.name=name
        self.units=units
    def __repr__(self):
        return '<Sensor %s>'%self.name
    
class Sample(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sensor_id = db.Column(db.Integer,db.ForeignKey('sensor.id'))
    sensor = db.relationship('Sensor',backref=db.backref('samples',lazy='dynamic'))
    
    frame_id =  db.Column(db.Integer,db.ForeignKey('frame.id'))
    frame = db.relationship('Frame',backref=db.backref('samples',lazy='dynamic'))
    
    value = db.Column(db.Float)
    flag = db.Column(db.Integer)

    def __init__(self, sensor, frame, value, flag=None):
        self.sensor=sensor
        self.frame=frame
        self.value=value
        self.flag=flag

    def __repr__(self):
        return '<Sample %r:%g>' % (self.sensor,self.value)


    
class WeatherPi(db.Model):
    timestamp=db.Column(db.DateTime,primary_key=True)
    humidity= db.Column(db.Float)
    lux=db.Column(db.Float)
    temp1=db.Column(db.Float)
    temp2=db.Column(db.Float)
    pressure=db.Column(db.Float)

    def __init__(self,timestamp,**kws):
        self.timestamp=timestamp
        self.__dict__.update(kws)
    def __repr__(self):
        return '<WeatherPi %s>'%(self.timestamp)


@app.route('/')
def landing():
    return render_template('landing.html')

time_format='%Y-%m-%dT%H:%M:%S'
volatile=os.path.join(os.path.dirname(__file__),
                      'volatile')
class BadStream(Exception):
    pass
def clean_stream(stream):
    if re.match('^[-_a-zA-Z0-9]+$',stream):
        return stream
    raise BadStream(stream)
    
    

# data fetching
@app.route('/data/<stream>/get')
def fetch(stream):
    default_interval=datetime.timedelta(hours=24)
    
    # build up some default query parameters:
    start_s = request.args.get('start',None)
    stop_s = request.args.get('stop',None)

    if start_s is not None:
        start=datetime.datetime.strptime(start_s,time_format)
    else:
        start=None
    if stop_s is not None:
        stop=datetime.datetime.strptime(stop_s,time_format)
    else:
        stop=None

    if start is not None and stop is not None:
        if start>=stop:
            stop=None
            
    if start is None and stop is None:
        start=datetime.datetime.now() - default_interval
        stop=datetime.datetime.now()
    elif start is None:
        start=stop - default_interval
    elif stop is None:
        stop=start + default_interval

    stream=clean_stream(stream)

    store=pd.HDFStore('volatile/%s/weather.h5'%stream)

    raw=store['raw'] # to be configured...
    result=raw[ (raw.timestamp>=utils.to_unix(start)) &
                (raw.timestamp<=utils.to_unix(stop)) ]

    # easy conversion from unix to np.datetime64?
    t0=np.datetime64('1970-01-01 00:00:00')
   
    result['time']=t0 + result.timestamp.values.astype('i8') * np.timedelta64(1,'s')
    # to_json() returns something like {"timestamp":{"<i>":12341234,"<i+1>":12341234,...},
    #                                   "lux":{"<i>":321321,"<i+1>":321322,...} ...
    #                                  }

    fmt='csv'

    columns=(['time'] +
             [c
              for c in result.columns
              if c not in ['timestamp','time']] )
    
    if fmt is 'json':
        return result.to_json(index=False,columns=columns)
    elif fmt is 'csv':
        return result.to_csv(index=False,columns=columns)

                                                                          
@app.route('/graph')
def graph1():
    return render_template('dygraph1.html')

# So that's working - pretty snappy.
# In rough order:
#    posting of new data, to regerate the h5 raw and overviews
#      -- add route to receive data
#      -- have that add data to sqlite
#      -- update h5 files.
#      -- allow for pages to poll or somehow get notification (
#         maybe announce how often to check back?)
#    on pan, update the data
#      -- better handled by new csv request, GViz source, custom JS array handling?
#         => short-term fix - if the overlap with the original date range is smaller
#            than some threshold, request a new range.
#    multiple levels of detail
#      -- display hourly data with the range bars
#      -- on zoom, can switch to different level of detail.
#    deal with timezone display - may not be that hard if we just make sure the
#    data being sent includes +00:00 at the end

