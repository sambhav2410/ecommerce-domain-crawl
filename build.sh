#!/usr/bin/env bash
# build.sh
echo "Installing dependencies..."
pip install -r requirements.txt

echo "Collecting static files..."
python manage.py collectstatic --no-input

echo "Applying migrations..."
python manage.py migrate

python manage.py runserver