#!/bin/bash
# Build Lambda deployment package for GreenTrack backend
# Usage: ./scripts/build-lambda.sh

set -e  # Exit on error

echo "🏗️  Building Lambda deployment package..."

# Navigate to repository root
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# Configuration
APP_DIR="app"
BUILD_DIR="build/lambda-package"
OUTPUT_ZIP="build/lambda.zip"
REQUIREMENTS_FILE="app/requirements.txt"

# Clean previous build
echo "🧹 Cleaning previous build..."
rm -rf "$BUILD_DIR"
rm -f "$OUTPUT_ZIP"
mkdir -p "$BUILD_DIR"

# Install Python dependencies
echo "📦 Installing Python dependencies..."
if [ -f "$REQUIREMENTS_FILE" ]; then
    pip install -r "$REQUIREMENTS_FILE" -t "$BUILD_DIR" --quiet
    echo "   ✅ Dependencies installed"
else
    echo "   ⚠️  No requirements.txt found, skipping dependencies"
fi

# Copy application code
echo "📂 Copying application code..."
cp -r "$APP_DIR/backend" "$BUILD_DIR/"
cp -r "$APP_DIR/adapters" "$BUILD_DIR/"
cp "$APP_DIR/__init__.py" "$BUILD_DIR/" 2>/dev/null || touch "$BUILD_DIR/__init__.py"

# Copy ML code (needed for forecasting)
if [ -d "ml" ]; then
    echo "🤖 Copying ML modules..."
    mkdir -p "$BUILD_DIR/ml"
    cp -r ml/forecasting "$BUILD_DIR/ml/"
    cp ml/__init__.py "$BUILD_DIR/ml/" 2>/dev/null || touch "$BUILD_DIR/ml/__init__.py"
fi

# Remove unnecessary files
echo "🗑️  Removing unnecessary files..."
find "$BUILD_DIR" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find "$BUILD_DIR" -type d -name "*.dist-info" -exec rm -rf {} + 2>/dev/null || true
find "$BUILD_DIR" -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
find "$BUILD_DIR" -type f -name "*.pyc" -delete 2>/dev/null || true
find "$BUILD_DIR" -type f -name "*.pyo" -delete 2>/dev/null || true
find "$BUILD_DIR" -type f -name ".DS_Store" -delete 2>/dev/null || true

# Create ZIP file
echo "📦 Creating deployment package..."
cd "$BUILD_DIR"
zip -r "../lambda.zip" . -q
cd "$REPO_ROOT"

# Get package size
PACKAGE_SIZE=$(du -h "$OUTPUT_ZIP" | cut -f1)

echo ""
echo "✅ Lambda package built successfully!"
echo "   📍 Location: $OUTPUT_ZIP"
echo "   📊 Size: $PACKAGE_SIZE"
echo ""
echo "💡 Next steps:"
echo "   1. Test locally: python -c 'import app.backend.consumption'"
echo "   2. Deploy: terraform apply"
echo ""
