#!/bin/bash
# Instalează panoul Subtitrări RO pentru Premiere Pro (macOS).
set -e
SURSA="$(cd "$(dirname "$0")" && pwd)/premiere_pro/com.subtitrari.ro"
DEST="$HOME/Library/Application Support/Adobe/CEP/extensions/com.subtitrari.ro"
mkdir -p "$DEST"
cp -R "$SURSA/" "$DEST/"
for v in 9 10 11 12; do defaults write "com.adobe.CSXS.$v" PlayerDebugMode 1; done
echo "Gata. Repornește Premiere Pro, apoi deschide: Window > Extensions > Subtitrări RO"
