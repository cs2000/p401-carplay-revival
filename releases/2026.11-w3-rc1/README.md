# 2026.11-w3-rc1

Released 6 November 2026. Consolidated firmware without the diagnostic logger.

**This update does not back up your current firmware. Flashing can make the unit unusable. Neither the maintainer nor this project provides a recovery firmware, recovery route, or recovery method if it fails. Use it entirely at your own risk.**

[**Download the USB ZIP**](https://github.com/cs2000/p401-carplay-revival/raw/refs/heads/main/releases/2026.11-w3-rc1/P401_2026.11_W3_RC1_NO_LOGGER.zip) · [Checksums](SHA256SUMS.txt) · [Manifest](manifest.json) · [Installation](../../docs/installation.md)

Extract the ZIP on your computer. Copy `update`, `zImage` and `rootfs.img` directly to the root of a clean FAT32 USB. Do not copy the ZIP itself, a containing directory, or old factory-import/autocopy files.

## Included

- Vendor V3.22.1 menu/application stack from the November 2025 P306-family reference.
- The matching, unmodified Linux 3.4.0 #396 kernel already used in the working R1 installation.
- W2 Wi-Fi interworking advertisement setting.
- Exact W3 two-byte link-local control patch and successful BusyBox 1.38.0 DHCP binary.
- Named userdata mounting without automatic erasure on mount failure.
- Read-only settings preflight. Existing `/data/msncfg/MsnProductInfo.ini` and `FactoryConfig.ini` remain authoritative. There is no configuration migration, MCU pinning or forced CarPlay mode.

## Validation status

The staged R1/W2/W3 installation worked on the owner's P401. This ZIP is a newly assembled, standalone image with logging removed and settings preservation requested for public distribution. **The exact combined image has not been vehicle-tested.** See [offline verification](../../evidence/combined-image-verification.json).

The vendor System screen continues to report its V3.22.1 build and the saved product identity. The community revision is recorded in `/etc/carplay-revival-release` and this manifest.

## Excluded

No diagnostic collectors, capture preload, log-export marker, MCU firmware, bootloader, userdata image, factory export or community replacement UI is included. Normal vendor console messages remain normal vendor behaviour. The `update` selector requests only kernel and filesystem.

The image preserves existing settings; it cannot preserve an old rootfs-only profile that is absent from userdata. See the installation prerequisites. No default MCU is substituted when the required saved files are unavailable. That situation can leave the interface unusable, and this project supplies no recovery route.
