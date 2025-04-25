#! /usr/bin/env bash

# Let the DB start
python /interactem/app/interactem/app/backend_pre_start.py

# Run migrations
alembic upgrade head

# Create initial data in DB
python /interactem/app/interactem/app/initial_data.py
