#!/usr/bin/env bash
# VPS setup script for Ubuntu 22.04 LTS
# Installs: Java, Xvfb, IB Gateway, IBC, Python/uv, the bot
#
# Usage (as root on a fresh droplet):
#   curl -fsSL <your-repo>/deploy/setup_vps.sh | bash
#   OR: scp deploy/setup_vps.sh root@<vps-ip>:~ && ssh root@<vps-ip> bash setup_vps.sh

set -euo pipefail

BOT_USER="trader"
BOT_DIR="/home/$BOT_USER/algo-trading-playground"
IBC_VERSION="3.18.0"
IB_GATEWAY_VERSION="10.30.1"

echo "=== 1. System packages ==="
apt-get update -qq
apt-get install -y --no-install-recommends \
    openjdk-17-jre-headless \
    xvfb \
    x11vnc \
    curl \
    unzip \
    git \
    ca-certificates

echo "=== 2. Create bot user ==="
useradd -m -s /bin/bash "$BOT_USER" || true

echo "=== 3. Install IB Gateway ==="
IB_GW_INSTALLER="ibgateway-${IB_GATEWAY_VERSION}-standalone-linux-x64.sh"
curl -fsSL "https://download2.interactivebrokers.com/installers/ibgateway/latest-standalone/linux-x64/$IB_GW_INSTALLER" \
    -o "/tmp/$IB_GW_INSTALLER"
chmod +x "/tmp/$IB_GW_INSTALLER"
# Run in headless mode
Xvfb :99 -screen 0 1024x768x24 &
DISPLAY=:99 "/tmp/$IB_GW_INSTALLER" -q -dir "/home/$BOT_USER/ibgateway"
chown -R "$BOT_USER:$BOT_USER" "/home/$BOT_USER/ibgateway"

echo "=== 4. Install IBC (automates IB Gateway login) ==="
IBC_ARCHIVE="IBCLinux-${IBC_VERSION}.zip"
curl -fsSL "https://github.com/IbcAlpha/IBC/releases/download/${IBC_VERSION}/$IBC_ARCHIVE" \
    -o "/tmp/$IBC_ARCHIVE"
unzip -q "/tmp/$IBC_ARCHIVE" -d "/home/$BOT_USER/ibc"
chmod +x /home/$BOT_USER/ibc/*.sh
chown -R "$BOT_USER:$BOT_USER" "/home/$BOT_USER/ibc"

echo ""
echo ">>> Edit /home/$BOT_USER/ibc/config.ini with your IBKR username/password <<<"
echo ""

echo "=== 5. Install uv (Python package manager) ==="
curl -LsSf https://astral.sh/uv/install.sh | sudo -u "$BOT_USER" sh

echo "=== 6. Clone and set up the bot ==="
# If you have the repo, clone it here. Otherwise copy files manually:
# scp -r /path/to/algo-trading-playground root@<vps-ip>:$BOT_DIR
# For now, assume files are already at $BOT_DIR

if [ -d "$BOT_DIR" ]; then
    cd "$BOT_DIR"
    sudo -u "$BOT_USER" /home/$BOT_USER/.local/bin/uv sync
    cp .env.example .env
    echo ">>> Edit $BOT_DIR/.env with IBKR_HOST=127.0.0.1 IBKR_PORT=4002 DRY_RUN=false <<<"
fi

echo "=== 7. Install systemd services ==="
cp /home/$BOT_USER/algo-trading-playground/deploy/ibgateway.service /etc/systemd/system/
cp /home/$BOT_USER/algo-trading-playground/deploy/ibkr-bot.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable ibgateway ibkr-bot

echo ""
echo "=== Setup complete ==="
echo "Next steps:"
echo "  1. Edit /home/$BOT_USER/ibc/config.ini (IBKR credentials)"
echo "  2. Edit $BOT_DIR/.env (DRY_RUN=false when ready)"
echo "  3. systemctl start ibgateway   (starts IB Gateway via IBC)"
echo "  4. systemctl start ibkr-bot    (starts the trading bot)"
echo "  5. journalctl -u ibkr-bot -f   (watch logs)"
