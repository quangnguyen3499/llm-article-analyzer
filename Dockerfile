FROM python:3.9-slim

ENV RUN_MIGRATIONS=1

# Set the working directory
WORKDIR /app

COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app/

RUN chmod +x ./bin/migrate.sh ./bin/start_dev.sh

ENTRYPOINT ["sh", "./bin/migrate.sh"]
CMD ["sh", "./bin/start_dev.sh"]
