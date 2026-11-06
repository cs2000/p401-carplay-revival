# Why wireless CarPlay failed and what changed

## Observed failure

Bluetooth pairing and Apple authentication succeeded. The phone joined the access point automatically and advertised its CarPlay service. Direct USB CarPlay worked. The interface nevertheless timed out at `CarPlayControlClientConnect` and displayed a wireless connection failure.

Earlier W2 captures showed DHCP DISCOVER/OFFER retries without REQUEST/ACK, while IPv6 link-local addressing was available. Native-library replay reproduced the control timeout (`-6722`) without a car or iPhone emulator.

## Link-local exclusion

The Wi-Fi control-client branch in `libAirPlay.so` set HTTP flags containing `0x100`. The vendor CoreUtils translation mapped this to AsyncConnection flag `0x80`, which excludes both IPv4 link-local (`169.254.0.0/16`) and IPv6 link-local (`fe80::/10`) endpoints.

That left the client unable to use a valid discovered IPv6 endpoint while IPv4 assignment was incomplete. IPv6 support itself was already present in the kernel and libraries.

For the exact identified library:

| Item | Value |
| --- | --- |
| Original SHA256 | `f86ec8573bf9a1dbd1526b8e99a5e6ff503a4191fd5f9d0024518f7fc4110716` |
| Patched SHA256 | `551112f2b5e525a0ff4994357ee1563c5d1e1dad56f59df6724962a0be8e34db` |
| File offset | `0x244b4` |
| Original ARM instruction | `movne r1, #0x104` (`41 1f a0 13`) |
| Replacement | `movne r1, #4` (`04 10 a0 13`) |
| Actual changed bytes | Two |

[The patch tool](../tools/patch_airplay.py) checks the complete original hash and expected instruction, then checks the final hash. Do not apply this offset to another version.

Offline tests exercised the actual vendor connection routine and resolver with a synthetic Bonjour/TCP peer. The original failed with link-local-only addressing; W3 completed the control request. IPv4 continued to work and a deliberate HTTP 503 remained an error. This was a connection test, not an emulated Apple authentication/video session.

## DHCP correction

W3 also uses a static, DHCP-only ARM BusyBox 1.38.0 build. The upstream reply-delivery correction avoids forcing broadcast replies when the client's DHCP broadcast flag is clear. The captured phone requests used flags `0`; the replacement sent unicast OFFER/ACK. Address-pool and other DHCP options remain from the vendor configuration.

Sources: [upstream BusyBox discussion](https://lists.busybox.net/pipermail/busybox/2025-April/091410.html), [BusyBox 1.38.0 source](https://busybox.net/downloads/busybox-1.38.0.tar.bz2). Source and build configuration are also preserved under [third_party/busybox](../third_party/busybox).

## Wi-Fi advertisement

W2 enabled the existing `interworking=1` hostapd template option. W2 alone still failed; it is retained as part of the working setup. The remaining vendor template values are unchanged. This does not replace the Wi-Fi driver or claim to implement a new radio protocol.

## Physical result

I confirmed native wireless success on 5 November 2026 and reviewed the results on 6 November. There was one successful Wi-Fi AirPlay session, screen frames, 26 touch calls and a return from the accessory UI to CarPlay. Two screen starts represent foreground transitions within that session, not two independent reconnections.

The packet order is particularly useful:

| Packet | Event |
| --- | --- |
| 38 | IPv6 link-local control GET |
| 40 | IPv6 HTTP 200 OK |
| 62–63 | Unicast DHCP OFFER |
| 64 | DHCP REQUEST |
| 65 | Unicast DHCP ACK |

Thus the successful control connection preceded DHCP completion and directly exercised the link-local fix. Both W3 changes were installed together; their independent necessity was not isolated in a hardware A/B test. Long-term reconnect reliability has not been established. Audio setup is logged, but audibility was not independently verified.

A generic vendor `carplay connet timer out` message still appeared despite success. There were no `CarPlayControlClientConnect failed` lines in the successful session. Do not turn these findings into a claim of zero errors or universal reliability.

The public [field summary](../evidence/w3-field-summary.json) contains counts and event order. Private raw logs, packet captures, phone addresses and pairing data are excluded.
