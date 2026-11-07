# Compatibility and hardware identity

## What was tested

I tested the fixes on a Limcet Box-P401 interface in my Jaguar XFR. My saved selections included CheKuShiDai MCU type 7, SD-RDA5876 Bluetooth type 3, RTL8189FS WLAN type 1, screen type 3, resolution type 1 and touchscreen type 3. The display was 800 × 480. These describe **my unit**, not settings you should copy.

The public release does not write those settings to another device. Saved configuration stays in userdata and remains authoritative. An existing MCU lock is also retained; the release does not add or remove it.

## P301, P306, P401 and P701

The P-number is a product/board/resource variant identifier, not a proven chronological version number. P301 resource names occur inside the P306 reference. A lower P-number is not inherently a downgrade, and a higher one is not evidence of compatibility.

My original firmware was from the V3.9.5 era. This project uses V3.22.1 from November 2025 with the wireless fixes added.

## Requirements and limits

The [complete Jaguar RC2 firmware](../releases/2026.11-jaguar-xfr-rc2/README.md) supports the matching stock P401/configuration layout without a previous R1 or field-W3 install. The same full bundle upgrades the complete Jaguar RC1 release. It includes the firmware, wireless repair and UI launcher; saved userdata settings remain authoritative. A previously disabled Jaguar UI stays disabled until explicitly re-enabled. The car model alone does not establish hardware/configuration compatibility. [UI rollback](../recovery/2026.11-jaguar-xfr-rc2/README.md) requires a booting box and is not full-flash recovery. Development field-W3 overlays use different startup files and are not the public installation route.

- ARM/Arkmicro firmware family and a bootloader that accepts the kernel/filesystem UBI update format used here.
- Compatible NAND layout, kernel/driver hardware support and existing persistent configuration.
- Existing, readable `MsnProductInfo.ini` and `FactoryConfig.ini` files under `/data/msncfg`, each containing a `[General]` section.
- Wireless-capable hardware and a native wireless link mode selected by the user.

The kernel and vendor MCU adapters contain support for multiple configurations. That is not proof that every adapter, screen, radio or harness works with this release. There is no tested universal Limcet image. P701 and arbitrary P305/P306 devices are not certified by this project.

The preflight checks presence/readability, not correctness of every setting or hardware compatibility. Settings preservation cannot repair an incorrect MCU selection already stored on the unit. Missing or unmountable settings stop hardware startup, and no recovery route is supplied.
