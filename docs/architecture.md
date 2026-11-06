# System architecture

```text
Existing bootloader
  └─ Linux 3.4.0 kernel + matching vendor modules
      └─ rcS: locate/mount existing userdata by partition name
          └─ profile: read-only persistent-settings preflight
              └─ MsnFirstInit: resolve hardware/display configuration
                  └─ MsnCoreApp: vendor Qt 4.7.4 interface
                      ├─ selected MCU adapter / touch / vehicle switching
                      ├─ Bluetooth and Wi-Fi setup
                      └─ D-Bus activation of /usr/bin/carplay
                          └─ libAirPlay + CoreUtils + vendor authentication/media
```

The menu update is the newer vendor UI, not a newly written UI. The relevant native CarPlay executable is `/usr/bin/carplay`; the separate `sink` executable belongs to the Android Auto path in the examined reference. Descriptions of another project's `carplay-sidecar` do not establish this firmware's process architecture.

## Configuration preservation

Static inspection of `MsnApplication::getMsnProductValue` shows selection of `/data/msncfg/MsnProductInfo.ini` if it exists, with `/msnprofile` as the fallback location. The consolidated image makes the two rootfs profile paths symbolic links to the existing userdata INIs and checks those files before `MsnFirstInit` runs. It therefore supplies no donor or P401-specific hardware defaults through these paths.

There are no merge scripts, fixed MCU assignments, one-time configuration migrations, or pairing-list deletion. Userdata is not included in the update selector. Existing vendor settings, including an existing USB-only CarPlay choice, are retained. Normal vendor application behaviour remains; the added startup code itself does not rewrite settings.

`rcS` resolves the partition named `userdata` and reuses an existing UBI attachment. It does not erase/reformat the partition on mount failure or honor the old automatic factory-erasure path. Its RAM fallback does not pass the persistent-settings preflight, so hardware startup stops instead of adopting a foreign profile.

## Standalone packaging

The successful W3 experiment used userdata overrides and logger wrappers. The public consolidated image instead patches `/usr/lib/libAirPlay.so` directly and launches the exact same corrected DHCP binary from `/usr/libexec/carplay-revival/udhcpd` in the vendor hostapd startup script.

The original system BusyBox remains intact. D-Bus launches the vendor CarPlay executable directly. No capture preload, diagnostic collector, USB log marker or R4 helper is shipped. Old experiment files in userdata are left untouched and are not referenced by the new startup path.

## Flash format

The selector is exactly `kernel\r\nfilesystem\r\n` (20 bytes). It does not request bootloader, MCU, userdata or environment-image replacement. The bootloader can still update its own ordinary update metadata.

The image uses UBI with 131,072-byte eraseblocks, 2,048-byte minimum I/O and VID offset, 4,096-byte data offset and 126,976-byte LEBs. The rootfs volume is dynamic/autoresize, with UBIFS format 4, LZO compression and space fixup. The build reserves the measured number of LEBs and keeps the image within the reference's 106 MiB rootfs partition. The matching kernel is below its reference 4 MiB limit. This is not a guarantee of another device's layout.
