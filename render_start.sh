#!/usr/bin/env bash
# Exit on error
set -o errexit

# Run database migrations
echo "Running database migrations..."
python manage.py migrate


# Start the gunicorn server
echo "Starting Gunicorn server..."
exec gunicorn MindMend.wsgi:application
