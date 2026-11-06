# Third-party components and license scope

The root [LICENSE](LICENSE) applies to original project tooling and documentation only. It does not grant rights in vendor firmware, Apple/CarPlay technology, screenshots, libraries, kernel binaries or bundled third-party code. No official affiliation or endorsement is implied.

## BusyBox

The added DHCP binary is built from unmodified BusyBox 1.38.0 source with only the udhcpd applet enabled. BusyBox is distributed under GPL-2.0; its license, complete upstream source archive, build configuration and build instructions are included under `third_party/busybox` and `tools/build_dhcp.sh`.

## Vendor firmware

The reference contains Linux, BusyBox, Qt and other third-party and proprietary components, with their respective licenses and rights. This repository does not contain the complete vendor BSP/kernel/application source corresponding to the November 2025 firmware. The separate public Arkmicro kernel projects are not asserted to match this binary. The two-byte patch does not transfer ownership or relicense the original library.

The downloadable firmware is an unofficial modified vendor image. Source availability and redistribution terms for inherited components remain separate from the original project tools' MIT license. The repository must not be described as a fully open-source CarPlay implementation.
