#!/bin/bash
# Instalează scriptul Subtitrări RO pentru DaVinci Resolve (macOS).
set -e
DEST="$HOME/Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Scripts/Utility"
mkdir -p "$DEST"
rm -f "$HOME/Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Scripts/Edit/Subtitrari RO.py"
cp "$(cd "$(dirname "$0")" && pwd)/davinci_resolve/Subtitrari RO.py" "$DEST/"
echo "Gata. În DaVinci Resolve: Workspace > Scripts > Subtitrari RO"
