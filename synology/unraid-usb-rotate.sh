#!/bin/bash
ls -t /volume1/Backup/unraid-usb/*.zip 2>/dev/null | tail -n +27 | xargs rm -f
