# Cloudflared ecom_price tunnel

This tunnel exposes the price API at:

```text
ecom-price.appdeals.in -> http://localhost:9000
```

Install the safe config and systemd service:

```bash
cp deploy/cloudflared/ecom-price.yml ~/.cloudflared/ecom-price.yml
sudo cp deploy/cloudflared/cloudflared-ecom-price.service /etc/systemd/system/cloudflared-ecom-price.service
sudo systemctl daemon-reload
sudo systemctl enable --now cloudflared-ecom-price
```

The credential file is intentionally not committed. Create it locally with:

```bash
cloudflared tunnel token --cred-file ~/.cloudflared/ecom-price.json ecom_price
```

