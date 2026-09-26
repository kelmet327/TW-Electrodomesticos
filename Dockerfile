FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APACHE_RUN_DIR=/var/run/apache2 \
    APACHE_LOCK_DIR=/var/lock/apache2 \
    APACHE_RUN_USER=app \
    APACHE_RUN_GROUP=app \
    PATH=/opt/venv/bin:$PATH

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        apache2 \
        gcc \
        libapache2-mod-wsgi-py3 \
        libpq-dev \
        python3-venv \
    && rm -rf /var/lib/apt/lists/* \
    && python3 -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir --upgrade pip \
    && useradd --system --home /app --shell /usr/sbin/nologin app \
    && mkdir -p /app /var/run/apache2 /var/lock/apache2 /var/log/apache2 \
    && chown -R app:app /var/run/apache2 /var/lock/apache2 /var/log/apache2 /app

WORKDIR /app
COPY requirements.txt ./
RUN /opt/venv/bin/pip install --no-cache-dir -r requirements.txt

COPY . .
COPY deploy/apache/ports.conf /etc/apache2/ports.conf
COPY deploy/apache/bears_scourge.conf /etc/apache2/sites-available/000-default.conf
RUN a2enmod wsgi headers \
    && chown -R app:app /app /etc/apache2/sites-available/000-default.conf

USER app
EXPOSE 8080
CMD ["apache2ctl", "-D", "FOREGROUND"]
