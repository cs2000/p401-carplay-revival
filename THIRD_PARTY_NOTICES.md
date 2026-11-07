# Third-party components and license scope

The root [LICENSE](LICENSE) applies to original project tooling and documentation only. It does not grant rights in vendor firmware, Apple/CarPlay technology, screenshots, libraries, kernel binaries or bundled third-party code. No official affiliation or endorsement is implied.

## BusyBox

The added DHCP binary is built from unmodified BusyBox 1.38.0 source with only the udhcpd applet enabled. BusyBox is distributed under GPL-2.0; its license, complete upstream source archive, build configuration and build instructions are included under `third_party/busybox` and `tools/build_dhcp.sh`.

## Standalone integrity verifier runtime

The Jaguar full-image verifier statically links the ARM musl C runtime supplied by the documented build toolchain. The installed musl copyright and license notice is retained at `third_party/musl/COPYRIGHT`, in the full-image source archive and with its technical build records as `MUSL_COPYRIGHT.txt`. This runtime attribution is separate from the original verifier source's MIT license.

## Vendor firmware

The reference contains Linux, BusyBox, Qt and other third-party and proprietary components, with their respective licenses and rights. This repository does not contain the complete vendor BSP/kernel/application source corresponding to the November 2025 firmware. The separate public Arkmicro kernel projects are not asserted to match this binary. The two-byte patch does not transfer ownership or relicense the original library.

The downloadable firmware is an unofficial modified vendor image. Source availability and redistribution terms for inherited components remain separate from the original project tools' MIT license. The repository must not be described as a fully open-source CarPlay implementation.

## Experimental Jaguar interface

The UI1 extension dynamically links to the existing vendor Qt 4.7.4 libraries. Qt header licenses and the Qt LGPL exception are retained under `experimental/ui1/licenses/qt`; build instructions identify the pinned upstream header source. Jaguar leaper/wordmark artwork and screenshots are excluded from the project MIT license. Jaguar trademarks remain the property of their respective rights holders; this project is unofficial and is not endorsed by Jaguar.
