#!/bin/bash
# Cross-platform build script for Encrypted Messaging
# Run on Linux/macOS to build executables with PyInstaller

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DIST_DIR="$PROJECT_DIR/dist"
BUILD_DIR="$PROJECT_DIR/build"

echo "=========================================="
echo "Encrypted Messaging - Cross-Platform Build"
echo "=========================================="
echo "Project: $PROJECT_DIR"
echo "Dist: $DIST_DIR"
echo "Build: $BUILD_DIR"
echo ""

# Check Python version
python3 --version
pip --version

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt
pip install pyinstaller

# Clean previous builds
echo "Cleaning previous builds..."
rm -rf "$BUILD_DIR"
rm -rf "$DIST_DIR"

# Common hidden imports
HIDDEN_IMPORTS=(
    --hidden-import=crypto
    --hidden-import=identity
    --hidden-import=storage
    --hidden-import=networking
    --hidden-import=messaging
    --hidden-import=config
    --hidden-import=cryptography
    --hidden-import=cryptography.hazmat.primitives.asymmetric.x25519
    --hidden-import=cryptography.hazmat.primitives.asymmetric.ed25519
    --hidden-import=cryptography.hazmat.primitives.ciphers.aead
    --hidden-import=cryptography.hazmat.primitives.kdf.hkdf
    --hidden-import=cryptography.x509
    --hidden-import=cryptography.x509.oid
    --hidden-import=sqlite3
    --hidden-import=json
    --hidden-import=logging
    --hidden-import=threading
    --hidden-import=asyncio
    --hidden-import=tempfile
    --hidden-import=shutil
    --hidden-import=pathlib
    --hidden-import=typing
    --hidden-import=datetime
    --hidden-import=secrets
    --hidden-import=hashlib
    --hidden-import=websockets
)

# Build GUI
echo ""
echo "Building GUI executable..."
pyinstaller \
    --name encrypted-messaging-gui \
    --noconsole \
    --clean \
    "${HIDDEN_IMPORTS[@]}" \
    --hidden-import=customtkinter \
    --hidden-import=darkdetect \
    --hidden-import=tkinter \
    --hidden-import=matplotlib \
    --add-data "config.json:." \
    gui.py

# Build TUI
echo ""
echo "Building TUI executable..."
pyinstaller \
    --name encrypted-messaging-tui \
    --console \
    --clean \
    "${HIDDEN_IMPORTS[@]}" \
    --hidden-import=textual \
    --hidden-import=textual.widgets._tab_pane \
    --hidden-import=rich \
    --hidden-import=customtkinter \
    --hidden-import=darkdetect \
    --add-data "config.json:." \
    tui.py

# Build Server (same as TUI but different name)
echo ""
echo "Building Server executable..."
pyinstaller \
    --name encrypted-messaging-server \
    --console \
    --clean \
    "${HIDDEN_IMPORTS[@]}" \
    --hidden-import=textual \
    --hidden-import=textual.widgets._tab_pane \
    --hidden-import=rich \
    --hidden-import=customtkinter \
    --hidden-import=darkdetect \
    --add-data "config.json:." \
    tui.py

echo ""
echo "=========================================="
echo "Build complete!"
echo "=========================================="
echo "Executables created in: $DIST_DIR"
ls -la "$DIST_DIR"/

# Test executables
echo ""
echo "Testing executables..."
for exe in "$DIST_DIR"/encrypted-messaging-*/encrypted-messaging-*; do
    if [[ -f "$exe" && -x "$exe" ]]; then
        echo "Testing: $exe --help"
        timeout 10 "$exe" --help 2>&1 | head -5
        echo "  -> OK"
    fi
done

echo ""
echo "All builds successful!"