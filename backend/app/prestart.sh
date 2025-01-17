#! /usr/bin/env bash

# Let the DB start
python /app/interactem/app/backend_pre_start.py

# Run migrations
alembic upgrade head

# Create initial data in DB
python /app/interactem/app/initial_data.py
