#!/bin/bash
set -e

echo "=================================================="
echo "         VoteApp — Django Setup Script"
echo "=================================================="

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is required. Please install it first."
    exit 1
fi

# Create virtual environment
echo ""
echo "📦 Creating virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Install dependencies
echo "📥 Installing dependencies..."
pip install -r requirements.txt --quiet

# Run migrations
echo "🗃️  Running database migrations..."
python manage.py makemigrations accounts
python manage.py makemigrations elections
python manage.py makemigrations
python manage.py migrate

# Seed demo data
echo "🌱 Seeding demo data..."
python manage.py seed_demo

echo ""
echo "=================================================="
echo "✅  Setup complete!"
echo "=================================================="
echo ""
echo "To start the server:"
echo "  source venv/bin/activate"
echo "  python manage.py runserver"
echo ""
echo "Then open: http://127.0.0.1:8000"
echo ""
echo "Demo Accounts:"
echo "  Admin:  admin@voteapp.com  / admin123"
echo "  Voter:  alice@example.com  / voter123"
echo "  Voter:  bob@example.com    / voter123"
echo "=================================================="
