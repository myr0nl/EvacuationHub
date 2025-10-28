#!/bin/bash

# Start script for Disaster Alert System Frontend

# Kill any process using port 3000 (React frontend)
echo "🔍 Checking for processes on port 3000..."
lsof -ti:3000 | xargs kill -9 2>/dev/null && echo "✓ Killed existing process on port 3000" || echo "✓ Port 3000 is free"

cd "$(dirname "$0")/frontend"

echo "🚀 Starting Disaster Alert System Frontend..."

# Check and install dependencies
if [ ! -d "node_modules" ]; then
    echo "📦 Dependencies not found. Installing..."
    npm install

    if [ $? -ne 0 ]; then
        echo "❌ Failed to install dependencies!"
        exit 1
    fi

    echo "✓ Dependencies installed successfully"
fi

# Start React dev server
echo "✅ Starting React app on http://localhost:3000"
npm start
