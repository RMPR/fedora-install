#!/usr/bin/env bash
# Install postr for the current user, using the system Python (which is the
# one that has PyGObject). No pip, no virtualenv.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
prefix="${PREFIX:-$HOME/.local}"

if command -v dnf >/dev/null && ! rpm -q python3-gobject gtk4 libadwaita libsecret >/dev/null 2>&1; then
	sudo dnf install -y python3-gobject gtk4 libadwaita libsecret
fi

rm -rf "$prefix/share/postr/lib"
mkdir -p "$prefix/share/postr/lib" "$prefix/bin" "$prefix/share/applications"
cp -r "$here/src/postr" "$prefix/share/postr/lib/"
cat > "$prefix/bin/postr" <<SH
#!/bin/sh
PYTHONPATH="$prefix/share/postr/lib" exec /usr/bin/python3 -m postr.cli "\$@"
SH
chmod +x "$prefix/bin/postr"
sed "s|^Exec=postr|Exec=$prefix/bin/postr|" "$here/data/xyz.rmpr.Postr.desktop" \
	> "$prefix/share/applications/xyz.rmpr.Postr.desktop"
update-desktop-database "$prefix/share/applications" 2>/dev/null || true
echo "Installed. Run 'postr' (or find postr in your app launcher), then open Preferences."
