#!/bin/sh
set -e

if [ "$RUN_MIGRATIONS" = '1' ]
then
  echo "Migrating..."
  python3 manage.py migrate
  echo "Collecting static..."
  python3 manage.py collectstatic --no-input
fi

exec "$@"
