#!/bin/bash
# Instalează scriptul Subtitrări RO pentru DaVinci Resolve (macOS).
set -e
DEST="$HOME/Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Scripts/Edit"
mkdir -p "$DEST"
cp "$(cd "$(dirname "$0")" && pwd)/davinci_resolve/Subtitrari RO.py" "$DEST/"
echo "Gata. În DaVinci Resolve: Workspace > Scripts > Edit > Subtitrari RO"
