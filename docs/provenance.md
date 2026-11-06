# Component provenance

| Component | Identity / SHA256 |
| --- | --- |
| Public reference archive | `AA-NEW=P306.zip` — `552308f9519e77cce34cf7e25d04b0fba78461e46b05b12040b10ffa3b6fe75c` |
| Reference rootfs.img | `b99969c5c376a2675d1136b42aa5fd7d168d9a18334069614e799226b4de1870` |
| Unmodified reference zImage | `04dc369f6fa30443a5c4353467cb5f8994af3a95798824e3f2815d360a46f9fc` |
| Metadata-preserving donor tar | `22e13e2b765595aa2ad5ad50df202e924fcf4b0bceb503416053b47642e98d7a` |
| Original libAirPlay.so | `f86ec8573bf9a1dbd1526b8e99a5e6ff503a4191fd5f9d0024518f7fc4110716` |
| W3 libAirPlay.so | `551112f2b5e525a0ff4994357ee1563c5d1e1dad56f59df6724962a0be8e34db` |
| BusyBox 1.38.0 source tar.bz2 | `34f9ea6ff8636f2c9241153b9114eefa9e65674a45318ae1ef95bb5f31c53bb2` |
| Field-tested DHCP binary | `bddafb863e3f37da68fc680db389f0c1b4c5fd0468953580f0f4422726c382d7` |

The reference came from this [public supplier share](https://u.pcloud.link/publink/show?code=kZeQ7P5Z2kkxSmt9n9hJKhJwh6mo3pzRYdSk). Public availability is not proof of an authenticated manufacturer signature. This is an unofficial community adaptation, not an official Limcet release.

The reference identifies vendor software V3.22.1. The kernel payload contains Linux 3.4.0 #396, built 21 November 2025 with GCC 4.9.4 / Buildroot 2018.08. The kernel image is retained unchanged. The resulting rootfs and downloadable ZIP have separate hashes in the [release manifest](../releases/2026.11-w3-rc1/manifest.json).

The build uses the reference firmware and the project patches. My personal configuration and phone data are not included.

BusyBox upstream source: https://busybox.net/downloads/busybox-1.38.0.tar.bz2

See [third-party notices](../THIRD_PARTY_NOTICES.md). The proprietary native stack is not represented as original project source, and the separate community kernel/UI projects are not represented as the source of this exact vendor build.
