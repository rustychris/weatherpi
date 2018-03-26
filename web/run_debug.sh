#!/bin/sh
export PYTHONPATH=stompy
export FLASK_APP=weather_app2.py
export FLASK_DEBUG=1
flask run --host=0.0.0.0
