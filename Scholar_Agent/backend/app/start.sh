#!/bin/bash
set -e

echo "=== Starting application ==="

echo "Waiting for database connection..."
python -c "
import os
import time

import psycopg2
from psycopg2 import OperationalError

max_retries = 30
retry_count = 0

while retry_count < max_retries:
    try:
        conn = psycopg2.connect(os.environ['DATABASE_URL'])
        conn.close()
        print('Database connection successful')
        break
    except OperationalError:
        retry_count += 1
        print(f'Waiting for database... ({retry_count}/{max_retries})')
        time.sleep(2)
else:
    print('Database connection failed')
    raise SystemExit(1)
"

echo "Checking database migrations..."
python -c "
import os

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

alembic_cfg = Config('alembic.ini')

try:
    engine = create_engine(os.environ['DATABASE_URL'])
    with engine.connect() as conn:
        result = conn.execute(text(\"SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'alembic_version')\"))
        table_exists = result.scalar()

    if not table_exists:
        print('First deployment, stamping baseline...')
        command.stamp(alembic_cfg, '980b32f130df')
        print('Baseline stamp complete')

    print('Running database migrations...')
    command.upgrade(alembic_cfg, 'head')
    print('Database migrations complete')
except Exception as e:
    print(f'Migration failed: {e}')
    print('Warning: continuing application startup')
"

echo "Checking NLTK resources..."
python -c "
import nltk

resources = [
    ('tokenizers/punkt', 'punkt'),
    ('tokenizers/punkt_tab/english', 'punkt_tab'),
    ('corpora/wordnet', 'wordnet'),
    ('corpora/omw-1.4', 'omw-1.4'),
]

for resource, package in resources:
    try:
        nltk.data.find(resource)
        print(f'NLTK resource already available: {resource}')
    except LookupError:
        print(f'Downloading NLTK resource: {package}')
        nltk.download(package, download_dir='/usr/local/nltk_data', quiet=True)
"

echo "Starting application service..."
exec "$@"
