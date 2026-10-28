# Meridian on the Mumbai server

Meridian runs on the Google Cloud VM `outreach-mumbai` (asia-south1-a, e2-small, 34.14.206.140), in its own
container, at https://meridian.sendwise.online. Another app (outreach) runs on the same VM; its Caddy owns ports
80 and 443 and serves any site file placed in `/etc/caddy-sites`. Meridian only adds its own file there.

| What | Where on the server |
|---|---|
| Code (this repo) | `/opt/meridian` |
| Secrets | `/opt/meridian/.env`, readable by root only. Same keys as `render.yaml` |
| Data | `/opt/meridian/data` (the SQLite database and the Zoho rules file), on the VM disk |
| HTTPS site | `/etc/caddy-sites/meridian.caddy`, a copy of `deploy/meridian.caddy` |

## First set-up

```bash
sudo git clone https://github.com/mandanajignesh65-eng/Marketing-Automation- /opt/meridian
sudo install -m 600 /path/to/.env /opt/meridian/.env
cd /opt/meridian && sudo docker compose up -d --build
sudo install -D -m 644 deploy/meridian.caddy /etc/caddy-sites/meridian.caddy
sudo docker exec outreach-platform-caddy-1 caddy reload --config /etc/caddy/Caddyfile
```

On first start, with no data file, the app downloads the stored copy from Supabase Storage (`meridian/backup.py`).

## Update to the latest code

```bash
cd /opt/meridian && sudo git pull && sudo docker compose up -d --build
```

## Check it

```bash
sudo docker ps --filter name=meridian      # "healthy"
sudo docker logs --tail 50 meridian
```

## Google Analytics and Search Console

Meridian reads them as the service account `meridian-google@outreach-512414.iam.gserviceaccount.com`, which never
has to sign in again (a person's sign-in from `connect-google.sh` ends after 7 days while the Google Cloud app is
in "Testing"). The account is added as a Viewer in Analytics (Admin → Property access management) and as a
Restricted user in Search Console (Settings → Users and permissions). Its JSON key, base64-encoded, is
`GOOGLE_SERVICE_ACCOUNT_JSON` in `/opt/meridian/.env`.
