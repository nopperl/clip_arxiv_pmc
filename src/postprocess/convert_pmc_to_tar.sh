#!/bin/sh
cd "$1"
for bucket in $(find . -mindepth 1 -maxdepth 1 -type d); do
  outname=$(printf "%04d" 0x$(basename $bucket))
  find "$bucket" -type f -exec tar -rf "$outname".tar --transform 's|.*/\([^/]*\)/\([^/]*\)$|\1-\2|' {} \;
done
