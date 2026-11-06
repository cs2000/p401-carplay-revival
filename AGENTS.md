Read `docs/cloud-handover.md` before continuing this project. The latest development state is `experimental/ui1`; the public firmware release remains `2026.11-w3-rc1`.

Preserve the distinction between the field-tested W3 components, the offline-checked combined RC1 image, and the PC-tested UI1 extension. Do not claim a new build, radio behaviour or physical reboot has been tested without evidence from that exact artifact/device.

Never overwrite a user's MCU or factory settings to match the development car. Preserve the working CarPlay fix and the exact rollback payload. UI1 currently depends on the development W3 startup layout; do not present it as directly installable on the clean public RC1 layout.

Use `python tools/check_cloud_handover.py` for a read-only artifact check. Native laboratory references are under `experimental/ui1/lab/reference`; their Linux/WSL environment must be recreated and paths ported before running. Keep vendor services in private namespaces. Private phone captures, identifiers and raw vehicle logs must not be committed.

Keep the main README and install instructions concise. Link detailed build/compatibility material. Existing user authorization permits continuing feature work using saved files as a fallback; it is not proof of complete flash recovery. Do not remove the no-backup/no-recovery warning.
