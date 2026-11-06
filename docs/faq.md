# Frequently asked questions

## Did Apple introduce IPv6 CarPlay in iOS 17?

I haven't established that. IPv6 existed in iOS years earlier: [Apple's IPv6 guidance](https://developer.apple.com/support/ipv6/) describes the 2016 app compatibility requirement, and [Apple Platform Security](https://support.apple.com/en-gb/guide/security/seccb625dcd9/web) documents per-network link-local addressing in iOS 14.

My box worked on iOS 16 and failed when iOS 17 arrived. A change in discovery, address selection, DHCP or timing could have exposed the old firmware restriction. That is a hypothesis, not proof of a specific iOS change. I have no matched iOS 16/17 captures or Apple statement establishing the trigger. The current capture proves successful IPv6 use after the box-side repair.

## Was MFi authentication too old?

The recorded failure occurred after successful authentication. The working repair changes address handling and DHCP, leaving the authentication implementation intact. No certificates or authentication secrets are extracted or replaced by the patch tool.

## Is this a brand-new kernel?

No. It includes the unmodified November 2025 Linux 3.4.0 vendor kernel and its matching modules, already booted in the working R1 installation. The project did not replace it with a newer major Linux version. MCU choice alone does not establish kernel compatibility: display, NAND, Wi-Fi, GPU, audio and vendor userspace interfaces also matter.

## Can an Ottocast adapter's binaries be used?

The examined Ottocast reference used an incompatible architecture and stack. It helped investigate protocol roles; its CarPlay libraries were not copied into this image.

## Can the P401 be fully emulated on a PC?

Some original ARM applications and libraries can run under QEMU. The project demonstrated native control-request replay and the real Qt menu rendered through a framebuffer shim. That does not emulate the complete board, MCU, Wi-Fi radio, MFi hardware or an iPhone CarPlay video session. Offline success is reported separately from vehicle success.

## Has this download been tested in a car?

I've tested the kernel, menus and fix binaries on my box. The combined download packages them into one update while preserving existing settings. That exact image has only been checked offline so far, which is why it is labelled rc1.

## Does it back up the old firmware, or provide a recovery method?

No. It does not back up your firmware, and I cannot provide a recovery image or method if it fails. A factory-settings export is not a firmware backup.
