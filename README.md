# P401 CarPlay Revival

Newer menus and native wireless CarPlay fixes for Limcet/Arkmicro P401 interfaces. These fixes restored wireless CarPlay on my Jaguar XFR.

**Flash at your own risk. This does not back up your current firmware. A failed update can brick your unit, and I cannot provide a recovery image or method.**

## How to install this

Check [compatibility](docs/compatibility.md) first. Existing factory settings are retained; this is not a universal update for every CarPlay box.

1. [**Download the firmware ZIP**](https://github.com/cs2000/p401-carplay-revival/raw/refs/heads/main/releases/2026.11-w3-rc1/P401_2026.11_W3_RC1.zip) and extract it on your computer.
2. Use an empty **FAT32 USB drive under 16 GB**.
3. Copy these three files directly onto the USB—not inside another folder:

   ```text
   update
   zImage
   rootfs.img
   ```

4. With the vehicle parked and stable power available, insert the USB and restart the CarPlay box.
5. Wait for the update to finish. **Do not interrupt power or remove the USB while it is updating.** Follow the completion prompt, then remove the USB before the next normal startup.
6. If your saved setting is USB-only, select **USB & Wireless CarPlay** in Factory Settings, then pair your phone normally. Keep your existing MCU selection.

The filename is **`update`**, without an extension. It starts the full firmware update; an `msn_autocopy` folder is not needed.

## Test status

I've tested the fixes on my box. This combined download has passed offline checks but has not yet been tested in a vehicle, so it is labelled **rc1**.

[Release details and checksums](releases/2026.11-w3-rc1/README.md) · [Installation help](docs/installation.md) · [Technical notes](docs/README.md)

Optional Jaguar XFR menu: [**Glass + Clock installer and rollback**](releases/2026.11-ui1-jaguar-xfr/README.md). I've tested this exact overlay on my P401. It requires the matching R1 + field-W3 startup layout and is not directly compatible with the clean RC1 image above.

[UI1 source and lab notes](experimental/ui1/README.md) · [Cloud project handover](docs/cloud-handover.md)
