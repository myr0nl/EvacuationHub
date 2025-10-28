#!/bin/bash

# Start script for Disaster Alert System Backend

# Kill any process using port 5001 (Flask backend)
echo "🔍 Checking for processes on port 5001..."
lsof -ti:5001 | xargs kill -9 2>/dev/null && echo "✓ Killed existing process on port 5001" || echo "✓ Port 5001 is free"

cd "$(dirname "$0")/backend"

echo "🚀 Starting Disaster Alert System Backend..."

# Check and setup virtual environment
if [ ! -d "venv" ]; then
    echo "📦 Virtual environment not found. Setting up..."
    python3 -m venv venv

    if [ $? -ne 0 ]; then
        echo "❌ Failed to create virtual environment!"
        exit 1
    fi

    echo "✓ Virtual environment created"
    source venv/bin/activate

    echo "📥 Installing dependencies..."
    pip install --upgrade pip
    pip install -r requirements.txt

    if [ $? -ne 0 ]; then
        echo "❌ Failed to install dependencies!"
        exit 1
    fi

    echo "✓ Dependencies installed successfully"
else
    source venv/bin/activate
fi

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "⚠️  Warning: .env file not found!"
    echo "Create backend/.env with your Firebase credentials"
    exit 1
fi

# Start Flask app
echo "✅ Starting Flask API on http://localhost:5001"
python app.py
