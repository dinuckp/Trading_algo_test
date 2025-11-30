#!/bin/bash
# Complete Setup Script for Real Data Backtesting
# Run this script to set up everything automatically

echo "=================================="
echo "REAL DATA BACKTESTING SETUP"
echo "=================================="
echo ""

# Step 1: Check if .env exists
echo "Step 1: Checking for .env file..."
if [ ! -f .env ]; then
    echo "⚠️  No .env file found. Creating from template..."
    cp .sample.env .env
    echo "✅ Created .env file"
    echo ""
    echo "📝 IMPORTANT: Edit .env file with your broker credentials!"
    echo "   Open .env and fill in:"
    echo "   - BROKER_NAME (zerodha or fyers)"
    echo "   - BROKER_API_KEY"
    echo "   - BROKER_API_SECRET"
    echo "   - Other required fields"
    echo ""
    echo "Press Enter after you've updated .env..."
    read -r
else
    echo "✅ .env file exists"
fi

# Step 2: Verify Python environment
echo ""
echo "Step 2: Setting up Python environment..."
if command -v uv &> /dev/null; then
    echo "✅ UV package manager found"
    echo "Installing dependencies..."
    uv sync
else
    echo "⚠️  UV not found. Using pip..."
    pip install -r requirements.txt 2>/dev/null || echo "Note: requirements.txt not found, continuing..."
fi

# Step 3: Test broker connection
echo ""
echo "Step 3: Testing broker connection..."
python3 << 'EOF'
import os
import sys
from dotenv import load_dotenv

load_dotenv()

broker_name = os.getenv("BROKER_NAME")
api_key = os.getenv("BROKER_API_KEY")

if not broker_name or not api_key:
    print("❌ Broker credentials not found in .env")
    print("   Please edit .env file and add your credentials")
    sys.exit(1)
else:
    print(f"✅ Found credentials for: {broker_name}")
    print("   Ready to download data!")
EOF

if [ $? -ne 0 ]; then
    echo ""
    echo "⚠️  Please configure .env file first!"
    echo "   1. Open .env"
    echo "   2. Add your broker credentials"
    echo "   3. Run this script again"
    exit 1
fi

# Step 4: Create necessary directories
echo ""
echo "Step 4: Creating directories..."
mkdir -p historical_data
mkdir -p backtest_results
echo "✅ Directories created"

# Step 5: Download sample data
echo ""
echo "Step 5: Ready to download historical data"
echo ""
echo "Choose data download option:"
echo "  1) Download NIFTY data (last 3 months) - Recommended"
echo "  2) Download NIFTY + Bank NIFTY data (last 3 months)"
echo "  3) Download custom date range (you'll be prompted)"
echo "  4) Skip download (use existing data)"
echo ""
read -p "Enter choice (1-4): " choice

case $choice in
    1)
        echo "Downloading NIFTY data..."
        python3 download_historical_data.py
        ;;
    2)
        echo "Downloading NIFTY + Bank NIFTY data..."
        python3 download_historical_data.py --all
        ;;
    3)
        read -p "Start date (YYYY-MM-DD): " start_date
        read -p "End date (YYYY-MM-DD): " end_date
        echo "Downloading data from $start_date to $end_date..."
        python3 download_historical_data.py --start "$start_date" --end "$end_date"
        ;;
    4)
        echo "Skipping download..."
        ;;
esac

# Step 6: Verify downloaded data
echo ""
echo "Step 6: Checking downloaded data..."
if [ "$(ls -A historical_data 2>/dev/null)" ]; then
    echo "✅ Data files found:"
    ls -lh historical_data/*.csv 2>/dev/null | awk '{print "   - " $9 " (" $5 ")"}'
else
    echo "⚠️  No data files found in historical_data/"
fi

# Step 7: Ready to run backtest
echo ""
echo "=================================="
echo "SETUP COMPLETE! 🎉"
echo "=================================="
echo ""
echo "Next steps:"
echo "  1. Run backtest with real data:"
echo "     python run_backtest_with_real_data.py"
echo ""
echo "  2. Or download more data:"
echo "     python download_historical_data.py"
echo ""
echo "  3. View results:"
echo "     ls -lh backtest_results/"
echo ""
echo "=================================="
