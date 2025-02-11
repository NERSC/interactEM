#!/bin/bash

THIS_DIR=$(dirname $0)
dotenv -f $THIS_DIR/../tests/.env run pytest -s -vv ./tests