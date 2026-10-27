#!/bin/sh

set -eu
src="$(dirname "$0")/zim.py"
dest=/usr/local/bin/zim
sudo mkdir -p "$(dirname "$dest")"
sudo install -m 755 "$src" "$dest"
echo "installed to $dest"
