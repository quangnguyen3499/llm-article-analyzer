#!/bin/sh
set -e

if [ "$RUN_MIGRATIONS" = '1' ]
then
  echo "Waiting for database to be ready..."
  ATTEMPTS=0
    until python3 -c "import os,sys,psycopg2;\ntry:\n conn=psycopg2.connect(dbname=os.getenv('DB_NAME'), user=os.getenv('DB_USER'), password=os.getenv('DB_PASSWORD'), host=os.getenv('DB_HOST'), port=os.getenv('DB_PORT') or '5432'); conn.close(); sys.exit(0)\nexcept Exception:\n sys.exit(1)" 2>/dev/null
    do
    ATTEMPTS=$((ATTEMPTS+1))
      if [ "$ATTEMPTS" -ge 60 ]; then
      echo "Database not ready after $ATTEMPTS attempts." >&2
      exit 1
    fi
    sleep 2
    echo "Retrying ($ATTEMPTS)..."
  done
  echo "Migrating..."
  python3 manage.py migrate
  echo "Collecting static..."
  python3 manage.py collectstatic --no-input
fi

exec "$@"
