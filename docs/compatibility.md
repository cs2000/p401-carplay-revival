# Compatibility and hardware identity

## What was tested

The successful installation was a Limcet Box-P401 interface in a Jaguar XFR. Its saved selections included CheKuShiDai MCU type 7, SD-RDA5876 Bluetooth type 3, RTL8189FS WLAN type 1, screen type 3, resolution type 1 and touchscreen type 3. The display was 800 × 480. These describe **one tested unit**, not mandatory settings for every box.

The public release does not write those settings to another device. Saved configuration stays in userdata and remains authoritative. An existing MCU lock is also retained; the release does not add or remove it.

## P301, P306, P401 and P701

The P-number is a product/board/resource variant identifier, not a proven chronological version number. P301 resource names occur inside the P306 reference. A lower P-number is not inherently a downgrade, and a higher one is not evidence of compatibility.

The relevant upgrade here is the vendor software change from the owner's original V3.9.5-era build to V3.22.1 from November 2025, followed by the targeted W2/W3 fixes.

## Requirements and limits

- ARM/Arkmicro firmware family and a bootloader that accepts the kernel/filesystem UBI update format used here.
- Compatible NAND layout, kernel/driver hardware support and existing persistent configuration.
- Readable, nonempty `[General]` configuration files under `/data/msncfg` before hardware initialization.
- Wireless-capable hardware and a native wireless link mode selected by the user.

The kernel and vendor MCU adapters contain support for multiple configurations. That is not proof that every adapter, screen, radio or harness works with this release. There is no tested universal Limcet image. P701 and arbitrary P305/P306 devices are not certified by this project.

The preflight checks presence/readability, not correctness of every setting or hardware compatibility. Settings preservation cannot repair an incorrect MCU selection already stored on the unit. Missing or unmountable settings stop hardware startup, and no recovery route is supplied.
