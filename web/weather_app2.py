#  simplify life a bit by having just a single ledger,
#  hardcoded with the sensors which actually exist

# TODO:
# Permission management for volatile

from __future__ import print_function

import os
import datetime
from matplotlib.dates import date2num,num2date
import pandas as pd
import numpy as np
from stompy import utils
import re
import six
from flask import (Flask, request, session, g, redirect, url_for, abort, 
                   render_template, flash, Response )
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import UniqueConstraint
import keys
time_format='%Y-%m-%dT%H:%M:%S'

try:
    root_dir=os.path.dirname(__file__)
    app = Flask(__name__)
except NameError: # during dev:
    root_dir="."
    app = Flask("weather_app2")

volatile=os.path.join(root_dir,'volatile')
    
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(root_dir,'volatile','sensors.db')
app.config["APPLICATION_ROOT"] = "/weather2"
db = SQLAlchemy(app)


# post-process a dataframe result to a desired resolution in time
def downsample(raw,period_secs):
    """
    raw: pandas DataFrame, with a datetime64 time column
    """
    timestamp=utils.to_unix(raw.time.values)
    periods=timestamp//period_secs
    
    #agg=raw.groupby(periods).agg( [np.min,np.mean,np.max] )
    agg=raw.groupby(periods).agg( [np.mean] )

    # drop multiindex by compounding the names
    new_cols=[]
    for col in agg.columns:
        if col[1]=='mean':
            new_col=col[0]
        else:
            new_col='_'.join(col)
        new_cols.append(new_col)

    agg.columns=new_cols

    unix_time=agg.index.values*period_secs

    agg['time']=np.datetime64("1970-01-01 00:00")+np.timedelta64(1,'s')*unix_time

    # reorder to get time first
    new_cols=['time'] + list(agg.columns[:-1])
    agg=agg[new_cols]
    return agg

class Site(db.Model):
    id=db.Column(db.Integer, primary_key=True)
    name=db.Column(db.String(50))
    
    class BadStream(Exception):
        pass

    @staticmethod
    def by_name(name):
        name=Site.sanitize_name(name)
        return Site.query.filter_by(name=name).first() 

    @staticmethod
    def sanitize_name(name):
        if re.match('^[-_a-zA-Z0-9]+$',name):
            return name
        else:
            raise BadStream(stream)

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
                print("%d/%d"%(reci,len(df)))
                
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
        # about 2 seconds
        query=db.session.query(Sample.value,Sample.flag,
                               Sensor.name,
                               Frame.timestamp).\
               filter(Sample.frame_id==Frame.id).\
               filter(Sample.sensor_id==Sensor.id).\
               filter(Frame.site_id == self.id)

        # faster than constructing the objects 
        rows=db.session.execute(query).fetchall()
        return rows

    def fetch_date_range(self,start,stop,res=0):
        query=db.session.query(Sample.value,Sample.flag,
                               Sensor.name,
                               Frame.timestamp).\
                               filter(Sample.frame_id==Frame.id).\
                               filter(Sample.sensor_id==Sensor.id).\
                               filter(Frame.site_id == self.id).\
                               filter(Frame.timestamp>=start).\
                               filter(Frame.timestamp<=stop)

        # faster than constructing the objects 
        rows=db.session.execute(query).fetchall()
        
        # Each row is value, flag, name, timestamp
        df=pd.DataFrame.from_records(data=rows,columns=['value','flag','sensor','time'])
        df2=df.pivot(index='time',columns='sensor',values='value').reset_index()

        if res>0:
            df2=downsample(df2,res)

        # This is the expected format -- dataframe with a timestamp and each sensor
        # value on each row
        return df2
    
    def last_reading(self):
        res=0 # DBG -- only know how to do raw right now

        # Get the last frame:
        query=db.session.query(Frame.id).\
                               filter(Frame.site_id == self.id).\
                               order_by(Frame.timestamp.desc())
        res=db.session.execute(query).first()
        if res is None:
            return None
        
        frame_id=res[0]
        
        query=db.session.query(Sample.value,Sample.flag,
                               Sensor.name,
                               Frame.timestamp).\
                               filter(Sample.frame_id==Frame.id).\
                               filter(Sample.sensor_id==Sensor.id).\
                               filter(Frame.id == frame_id)

        # faster than constructing the objects
        rows=db.session.execute(query).fetchall()
        
        # Each row is value, flag, name, timestamp
        df=pd.DataFrame.from_records(data=rows,columns=['value','flag','sensor','timestamp'])
        df2=df.pivot(index='timestamp',columns='sensor',values='value').reset_index()

        # This is the expected format -- dataframe with a timestamp and each sensor
        # value on each row
        return df2
        
    def frame_count(self):
        # 0.5s
        query=db.session.query(Frame.id).filter(Frame.site_id==self.id)
        rows=db.session.execute(query).fetchall()
        return len(rows)
    
    def all_samples_dataframe(self):
        rows=self.all_samples()
        df=pd.DataFrame( rows, columns=['value','flag','parameter','timestamp'])
        # loses flag.  oh well.
        df=df.pivot('timestamp','parameter','value')
        return df
    def data_path(self,create=True):
        # added root_dir here.
        path=os.path.join(volatile,self.name)
        if create and not os.path.exists(path):
            os.makedirs(path)
        return path
    
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

# Some approaches to optimize access
#sql="""CREATE INDEX IF NOT EXISTS frame_time_idx ON frame (timestamp)"""
#res=conn.execute(sql)
#sql="""create index sample_frame_idx on sample (frame_id)"""
#sql="""analyze"""

##

# site=Site.by_name('rockridge')

## 

@app.route('/')
def landing():
    return render_template('landing.html')

# data fetching
@app.route('/data/<site_name>/get')
def fetch(site_name):
    site=Site.by_name(site_name)

    default_interval=datetime.timedelta(hours=24)

    # which time resolution to return - defaults to
    # raw
    res=int(request.args.get('res',"0"))
    param=request.args.get('param',None)

    # build up some default query parameters:
    def proc_date_arg(key):
        as_string=request.args.get(key,None)
        if as_string is not None:
            if '.' in as_string: # discard decimal seconds
                as_string = as_string[:as_string.index('.')]
            return datetime.datetime.strptime(as_string,time_format)
        return None

    start=proc_date_arg('start')
    stop =proc_date_arg('stop')

    if start is not None and stop is not None:
        if start>=stop:
            stop=None
            
    if start is None and stop is None:
        last_reading = site.last_reading()
        if last_reading is None:
            return Response("No data",content_type="text/plain; charset=utf-8")
        stop=site.last_reading().timestamp[0].to_pydatetime()
        start=stop - default_interval
    elif start is None:
        start=stop - default_interval
    elif stop is None:
        stop=start + default_interval

    result=site.fetch_date_range(start,stop,res)

    if param is not None:
        result=result.loc[:,['time',param]]
    
    csv_txt=result.to_csv(index=False,date_format="%Y-%m-%dT%H:%M:%SZ")

    return Response(csv_txt,content_type='text/plain; charset=utf-8')

@app.route('/data/<site_name>/last')
def fetch_last(site_name):
    site=Site.by_name(site_name)
    result=site.last_reading()
    json_txt=result.iloc[0].to_json()

    return Response(json_txt,content_type='text/plain; charset=utf-8')


@app.route('/data/<site_name>/manual')
def manual_record(site_name):
    site=Site.by_name(site_name)

    Nframes=site.frame_count()

    return render_template('manual_input.html',
                           site=site,
                           Nframes=Nframes)

@app.route('/data/<site_name>/input')
def record(site_name):
    # record an observation
    if request.args['private_key'] != keys.private_key:
        raise Exception("Private key doesn't match")

    # expecting humidity, temp1, pressure, temp2, lux
    # optional timestamp

    site=Site.by_name(site_name)

    if 'timestamp' in request.args:
        # needs something like
        # 2015-01-01 12:25:30+00:00
        tstamp=pd.Timestamp(request.args['timestamp'])
    else:
        tstamp=pd.Timestamp.now(tz='UTC')
        
    df=pd.DataFrame(index=[tstamp]) # initialize with single row
    for k,v in six.iteritems(request.args):
        if k!='timestamp':
            print("Adding to df: %s => %s"%( repr(k), v))
            df[k]=v

    site.import_dataframe(df)

    print("Saved dataframe: ")
    print(df)
    
    return redirect( url_for('manual_record',site_name=site_name) )

@app.route('/graph2')
def graph2():
    default_interval=datetime.timedelta(hours=96)
    site_name='rockridge'
    site=Site.by_name(site_name)
    last=site.last_reading()

    # stop=datetime.datetime.utcnow()
    stop=last.timestamp[0].to_pydatetime()
    start=stop - default_interval

    kwargs=dict(data_start_time=utils.to_unix(start),
                data_stop_time=utils.to_unix(stop))

    kwargs['last_json']=last.iloc[0].to_json()
    kwargs['site_name']=site_name
    return render_template('dygraph2.html',**kwargs)


@app.route('/graph/<site_name>/<field>')
def graph(site_name,field):
    default_interval=datetime.timedelta(hours=96)
    site=Site.by_name(site_name)
    last=site.last_reading()

    # stop=datetime.datetime.utcnow()
    stop=last.timestamp[0].to_pydatetime()
    start=stop - default_interval

    kwargs=dict(data_start_time=utils.to_unix(start),
                data_stop_time=utils.to_unix(stop))

    kwargs['last_json']=last.iloc[0].to_json()
    kwargs['site_name']=site_name
    kwargs['field']=field
    # really ought to get this from the database
    if field.startswith('temp1'):
        unit='&#176;F'
    elif field.startswith('press'):
        unit='Pa'
    elif field.startswith('pm'):
        unit='&mu;g/m<sup>3</sup>'
    else:
        unit="n/a"
        
    kwargs['unit']=unit

    kwargs['columns']=[ col for col in last.columns if col!='timestamp']

    return render_template('dygraph2.html',**kwargs)


