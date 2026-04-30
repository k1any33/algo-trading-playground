# VPS Deployment Guide

## Infrastructure

- **Provider**: DigitalOcean Basic Droplet or AWS EC2 t3.micro
- **OS**: Ubuntu 22.04 LTS
- **Cost**: ~$6–10/month
- **What runs on VPS**: IB Gateway (paper) + the trading bot

## Prerequisites

- An IBKR account with paper trading enabled
- VPS SSH access

## Step-by-step

### 1. Provision the VPS

**DigitalOcean:**
1. Create Droplet → Ubuntu 22.04 → Basic ($6/mo, 1 GB RAM)
2. Add your SSH key during creation

**AWS:**
1. Launch EC2 → t3.micro → Ubuntu 22.04 AMI
2. Security group: allow SSH (port 22) from your IP only

### 2. Copy files to VPS

```bash
# From your local machine
scp -r /Users/jayden/Documents/dev/algo-trading-playground root@<VPS_IP>:/home/trader/
```

### 3. Run setup script

```bash
ssh root@<VPS_IP>
bash /home/trader/algo-trading-playground/deploy/setup_vps.sh
```

### 4. Configure IBC (IBKR auto-login)

Edit `/home/trader/ibc/config.ini`:
```ini
IbLoginId=YOUR_IBKR_USERNAME
IbPassword=YOUR_IBKR_PASSWORD
TradingMode=paper
```

### 5. Configure the bot

Edit `/home/trader/algo-trading-playground/.env`:
```
IBKR_HOST=127.0.0.1
IBKR_PORT=4002
IBKR_CLIENT_ID=1
DRY_RUN=true        # set false when ready to paper trade
```

### 6. Start services

```bash
systemctl start ibgateway    # starts IB Gateway via IBC (takes ~60s to login)
systemctl start ibkr-bot     # starts the trading bot (waits 30s for Gateway)
```

### 7. Monitor

```bash
journalctl -u ibkr-bot -f       # live logs
journalctl -u ibgateway -f      # IB Gateway logs
cat /home/trader/algo-trading-playground/logs/trading.log
```

### 8. Download history first (on VPS)

Before the bot can generate signals, fetch historical data:
```bash
sudo -u trader bash -c "cd /home/trader/algo-trading-playground && uv run python scripts/fetch_history.py"
```

## Ports

| Port | Service |
|------|---------|
| 4002 | IB Gateway paper trading |
| 7497 | TWS paper trading (if using TWS instead) |

## Notes

- IB Gateway must be running before the bot starts (`Requires=ibgateway.service`)
- The bot sleeps to align with 4H bar boundaries (00, 04, 08, 12, 16, 20 UTC)
- `position_state.json` persists trade state across restarts
- Paper account credentials are safe to use; no real money at risk
