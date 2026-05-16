# Deploy notes — Vultr (80.240.26.175)

The frontend systemd unit lives in `/etc/systemd/system/diligence-frontend.service`
already. This directory contains the bits Day-3 adds: the FastAPI backend
unit and the nginx snippet that routes `/api/` to it.

## One-time setup on the box

```bash
ssh root@80.240.26.175

# 1. Python venv + deps
cd /srv/diligence
sudo -u diligence python3 -m venv .venv
sudo -u diligence .venv/bin/pip install --upgrade pip
sudo -u diligence .venv/bin/pip install -r requirements.txt

# 2. Install + start the API unit
cp deploy/diligence-api.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now diligence-api
systemctl status diligence-api --no-pager

# 3. Wire nginx — paste the contents of deploy/nginx-snippet.conf
#    into /etc/nginx/sites-enabled/diligence, immediately ABOVE the
#    `location /` block. Then:
nginx -t && systemctl reload nginx
```

## Routine deploy (after this point)

```bash
ssh root@80.240.26.175 '
  cd /srv/diligence
  sudo -u diligence git pull --ff-only
  sudo -u diligence .venv/bin/pip install -r requirements.txt
  cd frontend && sudo -u diligence npm ci --no-audit --no-fund && sudo -u diligence npm run build
  systemctl restart diligence-api diligence-frontend
'
```

## Uploading the NVDA cache (one-time)

The audio is 45 MB; the JSONs are <5 MB total. rsync from a dev machine:

```bash
rsync -avz --progress data/NVDA/ root@80.240.26.175:/srv/diligence/data/NVDA/
ssh root@80.240.26.175 'chown -R diligence:diligence /srv/diligence/data'
```

## Health checks

```bash
curl http://80.240.26.175/api/health
curl http://80.240.26.175/api/research/NVDA | jq '.agents.reconciliation.disputed_facts[0].topic'
curl -I -H 'Range: bytes=0-1023' http://80.240.26.175/api/research/NVDA/audio
```
