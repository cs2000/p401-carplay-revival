#!/bin/sh
PATH=/bin:/sbin:/usr/bin:/usr/sbin
export PATH
ram=/tmp/p401-diag-r4
mkdir -p "$ram/network"
helper=/usr/lib/p401-r4/p401-diag
{
    echo 'P401 DIAGNOSTICS R4 + W3 NETWORK REPAIR runner entered'
    date
    cat /proc/uptime
    chmod 0755 /data/p401-w3/bin/udhcpd
    "$helper" --selftest
    install_ok=no
    [ ! -s /data/p401-w3/install-checks.txt ] || install_ok=yes
    while read -r crc size path; do
        if ! "$helper" verify "$path" "$crc" "$size"; then
            echo "INSTALL CHECK FAILED: $path"
            install_ok=no
        fi
    done < /data/p401-w3/install-checks.txt
    if [ "$install_ok" = yes ]; then
        echo 'ALL W3 NETWORK REPAIR INSTALL CHECKS PASSED'
        touch /tmp/p401-w3-install-ok
    fi
    echo '--- Installed Wi-Fi advertisement configuration ---'
    grep -E '^(interworking|access_network_type|internet|venue_group|venue_type)=' /etc/hostapd/hostapd.conf
} > /tmp/p401-diag-startup.txt 2>&1
/bin/sh /usr/bin/p401-recovery-diagnostics.sh > /tmp/p401-collector-errors.txt 2>&1 &
/bin/sh /usr/bin/p401-r4-observers.sh > "$ram/observers.txt" 2>&1 &
MsnCoreApp -qws 2>&1 | /bin/sh /usr/bin/p401-log-stream.sh core
