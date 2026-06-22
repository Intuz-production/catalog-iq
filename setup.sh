#!/bin/bash
set -e

echo "============================================"
echo " Setting up CatalogIQ"
echo " AI Catalog Intelligence Platform"
echo "============================================"
echo ""

# Create virtual environment
echo "[1/5] Creating Python virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
echo "[2/5] Installing Python dependencies..."
pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet

# Create .env from example if not exists
if [ ! -f .env ]; then
    cp .env.example .env
    echo ""
    echo "[INFO] Created .env file from template."
    echo "       Please edit .env and add your GROQ_API_KEY and DATABASE_URL."
    echo ""
fi

# Setup React frontend
echo "[3/5] Setting up React frontend..."
cd ui
npm install --silent
cd ..

# Create data directory
echo "[4/5] Creating data directory..."
mkdir -p data

# Final instructions
echo "[5/5] Verifying setup..."
echo ""
echo "============================================"
echo " Setup complete!"
echo "============================================"
echo ""
echo " Next steps:"
echo ""
echo "   1. Edit .env with your configuration:"
echo "      - GROQ_API_KEY  (from https://console.groq.com/keys)"
echo "      - DATABASE_URL  (PostgreSQL connection string)"
echo ""
echo "   2. Create the database:"
echo "      createdb catalogiq"
echo ""
echo "   3. Start the backend:"
echo "      source venv/bin/activate"
echo "      python -m app.main"
echo ""
echo "   4. Start the frontend (new terminal):"
echo "      cd ui && npm run dev"
echo ""
echo "============================================"
