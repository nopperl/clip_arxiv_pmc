#!/bin/bash

# Check if the user provided a directory as an argument
if [ $# -ne 1 ]; then
  echo "Usage: $0 <directory>"
  exit 1
fi

directory="$1"

# Check if the provided directory exists
if [ ! -d "$directory" ]; then
  echo "Error: Directory '$directory' does not exist."
  exit 1
fi

# Initialize a variable to store the total member count
total_members=0

# Loop through all the tar files in the directory
for file in "$directory"/*.tar; do
  if [ -f "$file" ]; then
    # Use tar to list the members and count them
    member_count=$(tar -tf "$file" | wc -l)
    echo "File: $file - Members: $member_count"
    total_members=$((total_members + member_count))
  fi
done

# Print the total number of members
echo "Total Members in Directory: $total_members"

