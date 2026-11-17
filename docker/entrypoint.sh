#!/bin/sh
# Entrada do contêiner de DESENVOLVIMENTO/DEMONSTRAÇÃO.
# Para produção, troque o runserver por: gunicorn config.wsgi:application -b 0.0.0.0:8000
set -e

python manage.py makemigrations --noinput
python manage.py migrate --noinput

if [ "${SEED_DEMO:-1}" = "1" ]; then
    python manage.py seed_demo
fi

exec python manage.py runserver 0.0.0.0:8000
