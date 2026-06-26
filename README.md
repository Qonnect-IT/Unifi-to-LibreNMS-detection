# unifi-librenms-sync

`unifi-librenms-sync` automatically detects UniFi access points from one or more UniFi Network sites and adds them to LibreNMS.

It is designed for environments where UniFi is the source of truth for AP inventory, while LibreNMS is used for monitoring, alerting and graphing.

The container:

* logs in to a UniFi CloudKey / UniFi Network controller
* reads the AP inventory from one or more UniFi sites
* generates LibreNMS hostnames from UniFi AP names or AP IP addresses
* checks whether each AP already exists in LibreNMS
* adds missing APs through the LibreNMS API
* optionally assigns devices to a specific LibreNMS poller group
* supports SNMPv1, SNMPv2c and SNMPv3
* supports internal PKI / custom CA bundles
* supports dry-run mode for safe testing

---

## Why this exists

LibreNMS can monitor UniFi APs directly, but manually adding every AP can become annoying, especially when APs are replaced, renamed or added across multiple UniFi sites.

This tool keeps onboarding simple:

```text
UniFi Network Controller
        ↓
unifi-librenms-sync
        ↓
LibreNMS
```

After an AP is added, LibreNMS performs normal monitoring and polling.

This tool does **not** replace LibreNMS polling. It only handles AP discovery and adding missing devices.

---

## Docker image

The container image is available on Docker Hub:

```text
qonnectit/unifi-librenms-sync:latest
```

Docker Hub page:

```text
https://hub.docker.com/repository/docker/qonnectit/unifi-librenms-sync
```

Pull the image:

```bash
docker pull qonnectit/unifi-librenms-sync:latest
```

---

## Requirements

You need:

* a UniFi CloudKey / UniFi Network controller
* a UniFi user account that can read sites and devices
* a LibreNMS API token that can add devices
* SNMP enabled for UniFi devices
* DNS records or stable IP addresses for the APs
* Docker or Docker Compose

Recommended:

* DHCP reservations for APs
* DNS names for APs
* `DRY_RUN=true` during first tests
* `PING_FALLBACK=false` while validating SNMP
* a dedicated UniFi service account
* a dedicated LibreNMS API user/token

---

## Quick start

Create a directory:

```bash
mkdir -p /opt/deployment/unifi-librenms-sync
cd /opt/deployment/unifi-librenms-sync
```

Create `docker-compose.yml`:

```yaml
services:
  unifi-librenms-sync:
    image: qonnectit/unifi-librenms-sync:latest
    container_name: unifi-librenms-sync
    env_file:
      - .env
    restart: "no"

    # Optional, useful when using an internal CA on the Docker host
    volumes:
      - /etc/ssl/certs:/etc/ssl/certs:ro
```

Create `.env`:

```env
# UniFi
UNIFI_URL=https://unifi.example.local
UNIFI_USERNAME=librenms-sync
UNIFI_PASSWORD=change-me
UNIFI_SITES=default
UNIFI_VERIFY_SSL=true

# LibreNMS
LIBRENMS_URL=https://librenms.example.local
LIBRENMS_TOKEN=change-me
LIBRENMS_VERIFY_SSL=true

# LibreNMS distributed poller group
# 0 is the default LibreNMS poller group.
LIBRENMS_POLLER_GROUP=0

# Hostname generation
# dns = use UniFi AP name and append HOSTNAME_DOMAIN
# ip  = use the AP management IP from UniFi
HOSTNAME_MODE=dns
HOSTNAME_DOMAIN=wifi.example.local

# SNMP
SNMP_VERSION=v2c

# Optional.
# Leave empty to let LibreNMS use its globally configured SNMP communities.
SNMP_COMMUNITY=

# Safety
DRY_RUN=true
PING_FALLBACK=false
FORCE_ADD=false
```

Run it:

```bash
docker compose run --rm unifi-librenms-sync
```

When the output looks correct, set:

```env
DRY_RUN=false
```

Then run it again:

```bash
docker compose run --rm unifi-librenms-sync
```

---

## Updating the container

Pull the latest image:

```bash
docker compose pull
```

Then run the sync again:

```bash
docker compose run --rm unifi-librenms-sync
```

If you run it from cron, the next scheduled run will use the newly pulled image.

---

## Example output

Dry-run example:

```text
Starting UniFi → LibreNMS AP sync
UniFi URL: https://unifi.example.local
UniFi sites: default
LibreNMS URL: https://librenms.example.local
LibreNMS poller group: 0
Hostname mode: dns
Hostname domain: wifi.example.local
SNMP version: v2c
Ping fallback: False
Force add: False
Dry-run: True
UniFi: TLS verification enabled, default CA store
LibreNMS: TLS verification enabled, default CA store
Reading UniFi site: default
Found 3 AP(s) in site default
DRY-RUN would add ap-office-01.wifi.example.local
DRY-RUN would add ap-office-02.wifi.example.local
DRY-RUN would add ap-warehouse-01.wifi.example.local
Done. found_aps=3, added=3, existing=0, skipped=0, dry_run=True
```

Normal run example:

```text
Reading UniFi site: default
Found 3 AP(s) in site default
ADDED ap-office-01.wifi.example.local
EXISTS ap-office-02.wifi.example.local
EXISTS ap-warehouse-01.wifi.example.local
Done. found_aps=3, added=1, existing=2, skipped=0, dry_run=False
```

---

## UniFi sites

Multiple UniFi sites can be configured with a comma-separated list:

```env
UNIFI_SITES=default,site-alpha,site-beta
```

Use the UniFi **site key**, not necessarily the display name shown in the UI.

For example, a site displayed as:

```text
Warehouse WiFi
```

may have an API site key like:

```text
a1b2c3d4
```

The script uses the site key in this API path:

```text
/proxy/network/api/s/<site>/stat/device
```

---

## Hostname modes

### DNS mode

```env
HOSTNAME_MODE=dns
HOSTNAME_DOMAIN=wifi.example.local
```

In DNS mode, the UniFi AP name is converted to a DNS-safe hostname.

Example:

```text
UniFi AP name: AP Office 01
LibreNMS host: ap-office-01.wifi.example.local
```

Spaces and special characters are converted to dashes.

Example:

```text
UniFi AP name: AP Warehouse Front
LibreNMS host: ap-warehouse-front.wifi.example.local
```

This mode assumes DNS resolves correctly from the LibreNMS pollers.

### IP mode

```env
HOSTNAME_MODE=ip
```

In IP mode, the AP management IP from UniFi is used directly.

This can be useful if DNS is not available, but DNS names are recommended for readability and long-term maintenance.

---

## SNMP configuration

### SNMPv2c using LibreNMS global communities

Recommended when LibreNMS already has the correct SNMP communities configured globally:

```env
SNMP_VERSION=v2c
SNMP_COMMUNITY=
```

With `SNMP_COMMUNITY` empty, the tool does not force a community string and LibreNMS can use its configured global SNMP community list.

### SNMPv2c with a specific community

```env
SNMP_VERSION=v2c
SNMP_COMMUNITY=your-community-string
```

Use this only if all APs use the same community string.

### SNMPv3

```env
SNMP_VERSION=v3
SNMPV3_AUTHLEVEL=authPriv
SNMPV3_AUTHNAME=librenms
SNMPV3_AUTHPASS=your-auth-password
SNMPV3_AUTHALGO=SHA
SNMPV3_CRYPTOPASS=your-privacy-password
SNMPV3_CRYPTOALGO=AES
```

---

## Ping fallback

LibreNMS can add a device as ping-only when SNMP discovery fails.

This behavior is controlled by:

```env
PING_FALLBACK=true
```

During initial testing, it is recommended to use:

```env
PING_FALLBACK=false
```

This makes SNMP problems fail clearly instead of silently adding devices as ping-only.

After SNMP has been validated, you can enable ping fallback if desired.

---

## LibreNMS distributed poller group

Set the poller group ID with:

```env
LIBRENMS_POLLER_GROUP=0
```

`0` is the default LibreNMS poller group.

For distributed poller setups, set this to the poller group that should monitor the APs:

```env
LIBRENMS_POLLER_GROUP=2
```

The container does not need database access. Poller group assignment is done through the LibreNMS API when the device is added.

---

## Internal PKI / custom CA certificates

TLS verification is enabled by default:

```env
UNIFI_VERIFY_SSL=true
LIBRENMS_VERIFY_SSL=true
```

If UniFi or LibreNMS uses an internal CA, either mount the host CA store:

```yaml
volumes:
  - /etc/ssl/certs:/etc/ssl/certs:ro
```

and set:

```env
REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt
SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt
```

or mount a project-specific CA bundle:

```yaml
volumes:
  - ./certs/internal-ca-bundle.crt:/certs/internal-ca-bundle.crt:ro
```

and set:

```env
UNIFI_CA_BUNDLE=/certs/internal-ca-bundle.crt
LIBRENMS_CA_BUNDLE=/certs/internal-ca-bundle.crt
```

Avoid disabling TLS verification in production.

For temporary testing only:

```env
UNIFI_VERIFY_SSL=false
LIBRENMS_VERIFY_SSL=false
```

---

## Scheduling with cron

Example `/etc/cron.d/unifi-librenms-sync`:

```cron
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

*/30 * * * * root flock -n /tmp/unifi-librenms-sync.lock bash -c 'cd /opt/deployment/unifi-librenms-sync && /usr/bin/docker compose run --rm unifi-librenms-sync >> /var/log/unifi-librenms-sync.log 2>&1'
```

Set permissions:

```bash
sudo chown root:root /etc/cron.d/unifi-librenms-sync
sudo chmod 644 /etc/cron.d/unifi-librenms-sync
sudo systemctl restart cron
```

Check the log:

```bash
tail -n 100 /var/log/unifi-librenms-sync.log
```

`flock` prevents overlapping runs if a previous sync is still active.

---

## Environment variables

| Variable                | Required | Default    | Description                                                     |
| ----------------------- | -------: | ---------- | --------------------------------------------------------------- |
| `UNIFI_URL`             |      yes |            | UniFi CloudKey / UniFi Network URL                              |
| `UNIFI_USERNAME`        |      yes |            | UniFi username                                                  |
| `UNIFI_PASSWORD`        |      yes |            | UniFi password                                                  |
| `UNIFI_SITES`           |       no | `default`  | Comma-separated UniFi site keys                                 |
| `UNIFI_VERIFY_SSL`      |       no | `true`     | Enable TLS verification for UniFi                               |
| `UNIFI_CA_BUNDLE`       |       no |            | Optional CA bundle path for UniFi                               |
| `LIBRENMS_URL`          |      yes |            | LibreNMS URL                                                    |
| `LIBRENMS_TOKEN`        |      yes |            | LibreNMS API token                                              |
| `LIBRENMS_VERIFY_SSL`   |       no | `true`     | Enable TLS verification for LibreNMS                            |
| `LIBRENMS_CA_BUNDLE`    |       no |            | Optional CA bundle path for LibreNMS                            |
| `LIBRENMS_POLLER_GROUP` |       no | `0`        | LibreNMS poller group ID                                        |
| `HOSTNAME_MODE`         |       no | `dns`      | `dns` or `ip`                                                   |
| `HOSTNAME_DOMAIN`       |       no |            | Domain appended in DNS mode                                     |
| `SNMP_VERSION`          |       no | `v2c`      | `v1`, `v2c` or `v3`                                             |
| `SNMP_COMMUNITY`        |       no |            | SNMP community for v1/v2c. Leave empty to use LibreNMS defaults |
| `SNMPV3_AUTHLEVEL`      |       no | `authPriv` | SNMPv3 auth level                                               |
| `SNMPV3_AUTHNAME`       |       no |            | SNMPv3 username                                                 |
| `SNMPV3_AUTHPASS`       |       no |            | SNMPv3 auth password                                            |
| `SNMPV3_AUTHALGO`       |       no | `SHA`      | SNMPv3 auth algorithm                                           |
| `SNMPV3_CRYPTOPASS`     |       no |            | SNMPv3 privacy password                                         |
| `SNMPV3_CRYPTOALGO`     |       no | `AES`      | SNMPv3 privacy algorithm                                        |
| `DRY_RUN`               |       no | `true`     | Show what would be added without changing LibreNMS              |
| `PING_FALLBACK`         |       no | `true`     | Allow LibreNMS to add devices as ping-only if SNMP fails        |
| `FORCE_ADD`             |       no | `false`    | Pass force-add behavior to LibreNMS                             |
| `DEVICE_LOCATION`       |       no |            | Optional location value for added devices                       |
| `OVERRIDE_SYSLOCATION`  |       no | `false`    | Override sysLocation in LibreNMS                                |
| `REQUESTS_CA_BUNDLE`    |       no |            | CA bundle used by Python requests                               |
| `SSL_CERT_FILE`         |       no |            | CA bundle used by OpenSSL/Python                                |

---

## Security recommendations

Use dedicated accounts and tokens.

Recommended:

```text
UniFi account:    librenms-sync
LibreNMS user:    unifi-sync
LibreNMS token:   dedicated API token
```

Avoid:

* using a personal UniFi admin account
* using a shared admin account
* committing `.env` files
* committing API tokens or SNMP communities
* disabling TLS verification in production
* using `PING_FALLBACK=true` before SNMP has been tested

---

## Troubleshooting

### `CERTIFICATE_VERIFY_FAILED`

The container does not trust the CA used by UniFi or LibreNMS.

Use a mounted CA bundle:

```env
REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt
SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt
```

or:

```env
UNIFI_CA_BUNDLE=/certs/internal-ca-bundle.crt
LIBRENMS_CA_BUNDLE=/certs/internal-ca-bundle.crt
```

### Devices are added as `os: ping`

LibreNMS could not complete SNMP discovery and added the device as ping-only.

Check:

* SNMP is enabled in UniFi
* the LibreNMS poller can reach the AP on UDP/161
* the community or SNMPv3 settings are correct
* DNS resolves from the poller
* `PING_FALLBACK=false` while testing

### Site name does not work

Use the UniFi API site key, not the display name.

For example, the UI may show:

```text
Warehouse WiFi
```

but the API site key may be:

```text
a1b2c3d4
```

Use:

```env
UNIFI_SITES=a1b2c3d4
```

### Cron says `bad username`

Files in `/etc/cron.d/` require a username field.

Correct:

```cron
*/30 * * * * root command...
```

Incorrect:

```cron
*/30 * * * * command...
```

### Lock file is empty

That is normal.

`flock` uses the file as a lock handle. The lock file is not a status file and usually contains no text.

---

## Notes

This tool is intentionally simple.

It only adds missing UniFi APs to LibreNMS. It does not currently:

* delete APs from LibreNMS
* rename existing LibreNMS devices
* change SNMP credentials of existing devices
* move existing devices between poller groups
* monitor AP status directly
* replace LibreNMS polling

This avoids accidentally removing or changing existing monitoring objects.

---

## License

Add your chosen license here.

For example:

```text
MIT License
```
