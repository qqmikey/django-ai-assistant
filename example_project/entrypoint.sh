#!/usr/bin/env sh
set -e

cd /workspace/example_project/app

echo "Applying migrations..."
python manage.py migrate --noinput

echo "Bootstrapping demo data..."
python manage.py bootstrap_demo

echo "Starting Django dev server on 0.0.0.0:8000"
python manage.py runserver 0.0.0.0:8000
