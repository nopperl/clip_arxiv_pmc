#!/bin/sh
count=0
for file in "$1"/*.tar; do
    new_name=$(printf "%08d.tar" "$count")
    mv "$file" "$1/$new_name"
    ((count++))
done
