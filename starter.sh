#!/bin/bash

# Start the first process
python delay_checker.py &

# Start the second process
gunicorn --workers 3 --bind 0.0.0.0:5000 wsgi:app

# Wait for any process to exit
wait -n

# Exit with status of process that exited first
exit $?