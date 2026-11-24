#!/bin/sh
# Export the Godot game for the browser and stage the files the artifact page uses.
# Needs Godot 4.4.1 with its export templates installed.
set -e
cd "$(dirname "$0")/.."
mkdir -p build/web
godot --headless --path game --export-release "Web" ../build/web/index.html
cd build/web
gzip -9 -c index.wasm > engine.gz.wasm     # engine, gzipped to fit the 15 MB per-file limit
cp index.pck game.pck.wasm                 # game data under a type artifacts serve
cp ../../web/play.html play.html           # page that loads both
