# Contributing

Useful contributions include precise compatibility reports, analysis of the native networking paths, portable offline tests and improvements to reproducible packaging.

For a hardware report, include the displayed software version, product family, selected MCU/BT/WLAN/display types, iOS version, whether wired CarPlay works, and whether native wireless reached the actual CarPlay screen. Include the release ZIP hash. State whether you used the consolidated release or a staged experimental installation.

Do not post raw packet captures, pairing databases, authentication material, Wi-Fi credentials, phone contacts or identifying screenshots. Use a redacted description or minimal synthetic fixture.

Keep these release invariants:

- Saved device configuration stays authoritative. Do not add one user's MCU/defaults or enable wireless by overwriting preferences.
- The update selector requests only kernel and filesystem. Do not introduce bootloader or userdata writes.
- New firmware/library hashes require their own tests. Hardware success and offline verification must be distinguished.
- Every release must retain the explicit no-backup/no-recovery warning.
- Original tools and documentation may use the project MIT license. Do not relabel vendor binaries or third-party code under it.

Use a new release directory for changed firmware; do not silently replace a published ZIP. The current combined build is rc1 and requires real-world validation before being described as vehicle-tested.
