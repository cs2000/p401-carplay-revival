Read `docs/cloud-handover.md` before continuing this project. Source and lab tools are in `experimental/ui1`; the owner-tested historical overlay is preserved in `experimental/ui1/candidates/glass-clock-2026-11-06`. Its old public release folder was removed at the user's request. The generic combined firmware remains `2026.11-w3-rc1`.

The stock-to-Jaguar full-image candidate is `releases/2026.11-jaguar-xfr-rc1`; it removes the private field-layout requirement using a standalone rootfs launcher. Its exact combined image is offline/native verified, not vehicle-tested. Preserve this distinction from the owner's successful overlay report.

Keep public release folders simple: README, SHA256SUMS and firmware ZIP. RC1 build/source/evidence records are in `experimental/ui1/full-image-rc1`; its state-only UI controls are in `recovery/2026.11-jaguar-xfr-rc1`. Do not mix recovery autocopy payloads into the three-file full-firmware USB ZIP.

Preserve the distinction between the field-tested W3 components, the offline-checked combined RC1 image, fresh native UI1 checks and the owner's 7 November report that the exact UI1 installer fixed all reported bugs. Do not extend that report to other hardware, new builds, endurance or complete flash recovery.

Never overwrite a user's MCU or factory settings to match the development car. Preserve the working CarPlay fix and exact old rollback payload. Only the legacy UI1 overlay depends on the development W3 startup layout; the full Jaguar image includes a standalone launcher and its own state-only UI rollback. Neither supplies full-flash recovery. Stock support requires the documented matching hardware and existing userdata configuration layout.

Use `python tools/check_cloud_handover.py` for the immutable original artifact check; release hashes and later evidence are separate. The working Cloud native harness is `experimental/ui1/lab/cloud`; its inputs still need recreating in a new environment. `lab/reference` retains historical Windows/WSL launch paths. Keep vendor services in private namespaces. Private phone captures, identifiers and raw vehicle logs must not be committed.

Keep the main README and install instructions concise. Link detailed build/compatibility material. Existing user authorization permits continuing feature work using saved files as a fallback; it is not proof of complete flash recovery. Do not remove the no-backup/no-recovery warning.
