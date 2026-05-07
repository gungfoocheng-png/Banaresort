#!/bin/bash

# Exit on error
set -e

echo "Starting deployment..."

# 1. Activate virtual environment
if [ -d "venv" ]; then
    source venv/bin/activate
    echo "Virtual environment activated."
else
    echo "Creating virtual environment..."
    python3 -m venv venv
    source venv/bin/activate
fi

# 2. Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

# 3. Restart the service
echo "Restarting bannaresort service..."
sudo systemctl restart bannaresort

echo "Deployment finished successfully!"
