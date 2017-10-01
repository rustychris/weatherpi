#!/bin/sh
export PYTHONPATH=/home/rusty/src/weatherpi/web/stompy
export FLASK_APP=weather_app2.py
export FLASK_DEBUG=1
flask run
