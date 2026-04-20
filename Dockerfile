# Base python image
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Upgrade pip
RUN pip install --no-cache-dir --upgrade pip

# Install OS dependencies if needed (e.g. for psycopg2)
RUN apt-get update && apt-get install -y libpq-dev gcc && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Collect static files
# RUN python manage.py collectstatic --noinput

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV DJANGO_SETTINGS_MODULE=MindMend.settings.production

# Run the render script natively
CMD ["gunicorn", "MindMend.wsgi:application", "--bind", "0.0.0.0:8000"]
