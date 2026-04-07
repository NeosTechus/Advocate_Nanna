#!/bin/bash
# Build script: injects environment variables into index.html
# Used by Vercel during deployment

set -e

# Create output directory
mkdir -p dist

# Copy all static files
cp index.html dist/
cp data.json dist/
cp positions.json dist/ 2>/dev/null || true

# Inject env vars into HTML
if [ -n "$GOOGLE_CLIENT_ID" ]; then
  sed -i.bak "s|__GOOGLE_CLIENT_ID__|${GOOGLE_CLIENT_ID}|g" dist/index.html
  rm -f dist/index.html.bak
  echo "Injected GOOGLE_CLIENT_ID"
else
  echo "WARNING: GOOGLE_CLIENT_ID not set"
fi

echo "Build complete: dist/"
ls -la dist/
