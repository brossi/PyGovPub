#!/bin/bash

BACKUP_DIR="./.timestamp_backups"

# Function to print usage
print_usage() {
    echo "Usage: $0 [options] <markdown_file_path> [section_id]"
    echo ""
    echo "Options:"
    echo "  --revert        Revert the last timestamp update for the specified file"
    echo ""
    echo "Arguments:"
    echo "  markdown_file_path    Path to the markdown file to update"
    echo "  section_id            If provided, only updates the timestamp for that specific section"
    echo "                        Otherwise, updates all timestamps in the file"
    exit 1
}

# Parse arguments
REVERT=0
FILE=""
SECTION=""

if [ $# -lt 1 ]; then
    print_usage
fi

while [ "$1" != "" ]; do
    case $1 in
        --revert )      REVERT=1
                        ;;
        --help )        print_usage
                        ;;
        * )             if [ -z "$FILE" ]; then
                            FILE=$1
                        elif [ -z "$SECTION" ]; then
                            SECTION=$1
                        else
                            echo "Error: Too many arguments provided."
                            print_usage
                        fi
                        ;;
    esac
    shift
done

# Ensure file was provided
if [ -z "$FILE" ]; then
    echo "Error: No markdown file specified."
    print_usage
fi

# Check if the file exists
if [ ! -f "$FILE" ]; then
    echo "Error: File '$FILE' not found"
    exit 1
fi

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

# Function to create backup
create_backup() {
    local file=$1
    local backup_file="${BACKUP_DIR}/$(basename "$file").$(date +%s).bak"
    cp "$file" "$backup_file"
    echo "$backup_file"
}

# Function to find latest backup
find_latest_backup() {
    local file=$1
    local base_name=$(basename "$file")
    find "$BACKUP_DIR" -name "${base_name}.*.bak" | sort -r | head -n 1
}

# Process revert if requested
if [ $REVERT -eq 1 ]; then
    latest_backup=$(find_latest_backup "$FILE")
    
    if [ -z "$latest_backup" ] || [ ! -f "$latest_backup" ]; then
        echo "Error: No backup found for '$FILE'"
        exit 1
    fi
    
    cp "$latest_backup" "$FILE"
    echo "Reverted '$FILE' to backup from $(stat -f "%Sm" "$latest_backup")"
    exit 0
fi

# Not a revert, so proceeding with timestamp update

# Create backup before making changes
backup_file=$(create_backup "$FILE")

# Get current timestamp in UTC
current_timestamp=$(date -u '+%Y-%m-%d %H:%M UTC')

# If a specific section ID is provided, only update that section
if [ -n "$SECTION" ]; then
    # Extract the section containing the specified ID and check if it exists
    if ! grep -q "## $SECTION" "$FILE"; then
        echo "Error: Section with ID '$SECTION' not found in $FILE"
        exit 1
    fi
    
    # Use awk to update only the timestamp in the specified section
    # This is more complex but handles multiple sections correctly
    awk -v section="$SECTION" -v ts="$current_timestamp" '
        BEGIN { in_section = 0; updated = 0; }
        /^## / { in_section = ($0 ~ "## " section); }
        /- Last Updated:/ && in_section { 
            print "- Last Updated: " ts; 
            updated = 1;
            next; 
        }
        { print; }
        END {
            if (updated == 0 && in_section == 1) {
                print "Warning: No timestamp line found in section " section;
            }
        }
    ' "$FILE" > "${FILE}.tmp" && mv "${FILE}.tmp" "$FILE"
    
    echo "Updated timestamp for section '$SECTION' in $FILE to: $current_timestamp"
    echo "Backup created at: $backup_file (use --revert to undo)"
else
    # Update all "Last Updated" lines in the file
    # Using sed with backup extension on macOS
    sed -i '' "s/- Last Updated: .*$/- Last Updated: $current_timestamp/g" "$FILE"
    
    # Count how many timestamps were updated
    timestamp_count=$(grep -c -- "- Last Updated: $current_timestamp" "$FILE" || echo 0)
    
    echo "Updated $timestamp_count timestamp(s) in $FILE to: $current_timestamp"
    echo "Backup created at: $backup_file (use --revert to undo)"
fi
