#!/bin/bash

# Check if a file path is provided
if [ $# -ne 1 ]; then
    echo "Usage: $0 <markdown_file_path>"
    exit 1
fi

markdown_file="$1"

# Check if the file exists
if [ ! -f "$markdown_file" ]; then
    echo "Error: File '$markdown_file' not found"
    exit 1
fi

# Get current timestamp in UTC
current_timestamp=$(date -u '+%Y-%m-%d %H:%M UTC')

# Update the Last Updated line in the file
# Using sed with backup extension on macOS
sed -i '' "s/- Last Updated: .*$/- Last Updated: $current_timestamp/" "$markdown_file"

echo "Updated timestamp in $markdown_file to: $current_timestamp"
