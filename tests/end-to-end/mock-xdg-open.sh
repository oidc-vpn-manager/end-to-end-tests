#!/bin/bash
# Mock xdg-open for E2E testing
# Captures URLs that would normally be opened in browser and stores them for Playwright to use

URL="$1"
CAPTURE_FILE="/tmp/xdg-open-captured-url.txt"

# Write the URL to a capture file that tests can read
echo "$URL" > "$CAPTURE_FILE"

# Log the capture for debugging
echo "$(date): Captured URL: $URL" >> /tmp/xdg-open-capture.log

# Exit successfully (don't actually open browser)
exit 0