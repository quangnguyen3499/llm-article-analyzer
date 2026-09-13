#!/bin/sh
gunicorn --bind 0.0.0.0:8000 --workers 2 --timeout 120 --graceful-timeout 30 --keep-alive 5 config.wsgi:application
