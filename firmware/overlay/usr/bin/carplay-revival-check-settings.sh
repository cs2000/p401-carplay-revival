#!/bin/sh
# Read-only preflight: this helper never creates, merges, or rewrites settings.
set -eu
[ "$(cat /tmp/p401-data-mode 2>/dev/null)" = persistent ] || exit 1
for name in MsnProductInfo.ini FactoryConfig.ini; do
    file=/data/msncfg/$name
    [ -f "$file" ] && [ -r "$file" ] && [ -s "$file" ] || exit 1
    grep -qi '^[[:space:]]*\[General\]' "$file" || exit 1
done
exit 0
