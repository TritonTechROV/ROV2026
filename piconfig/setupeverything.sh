#!/usr/bin/env bash
set -euo pipefail

sudo cp ./startrovcode.service /etc/systemd/system/startrovcode.service
sudo systemctl daemon-reload
sudo systemctl enable startrovcode.service
sudo systemctl restart startrovcode.service
sudo systemctl --no-pager -l status startrovcode.service
