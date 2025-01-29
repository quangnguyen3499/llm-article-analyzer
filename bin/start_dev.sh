#!/bin/sh
gunicorn --reload --bind 0.0.0.0:8000 config.wsgi:application
