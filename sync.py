#!/usr/bin/env python3

import os
import re
import sys
import time
import json
import urllib3
from typing import Dict, List, Optional

import requests


def env(name: str, default: Optional[str] = None, required: bool = False) -> str:
    value = os.getenv(name, default)
    if required and not value:
        print(f"ERROR: missing required environment variable: {name}", file=sys.stderr)
        sys.exit(2)
    return value or ""


UNIFI_URL = env("UNIFI_URL", required=True).rstrip("/")
UNIFI_USERNAME = env("UNIFI_USERNAME", required=True)
UNIFI_PASSWORD = env("UNIFI_PASSWORD", required=True)
UNIFI_SITES = [s.strip() for s in env("UNIFI_SITES", "default").split(",") if s.strip()]
UNIFI_VERIFY_SSL = env("UNIFI_VERIFY_SSL", "false").lower() == "true"

LIBRENMS_URL = env("LIBRENMS_URL", required=True).rstrip("/")
LIBRENMS_TOKEN = env("LIBRENMS_TOKEN", required=True)
LIBRENMS_POLLER_GROUP = int(env("LIBRENMS_POLLER_GROUP", "0"))

SNMP_VERSION = env("SNMP_VERSION", "v2c").lower()
SNMP_COMMUNITY = env("SNMP_COMMUNITY", "")

SNMPV3_AUTHLEVEL = env("SNMPV3_AUTHLEVEL", "authPriv")
SNMPV3_AUTHNAME = env("SNMPV3_AUTHNAME", "")
SNMPV3_AUTHPASS = env("SNMPV3_AUTHPASS", "")
SNMPV3_AUTHALGO = env("SNMPV3_AUTHALGO", "SHA")
SNMPV3_CRYPTOPASS = env("SNMPV3_CRYPTOPASS", "")
SNMPV3_CRYPTOALGO = env("SNMPV3_CRYPTOALGO", "AES")

HOSTNAME_DOMAIN = env("HOSTNAME_DOMAIN", "")
HOSTNAME_MODE = env("HOSTNAME_MODE", "dns").lower()
DRY_RUN = env("DRY_RUN", "true").lower() == "true"
PING_FALLBACK = env("PING_FALLBACK", "true").lower() == "true"
FORCE_ADD = env("FORCE_ADD", "false").lower() == "true"

DEVICE_LOCATION = env("DEVICE_LOCATION", "")
OVERRIDE_SYSLOCATION = env("OVERRIDE_SYSLOCATION", "false").lower() == "true"

if not UNIFI_VERIFY_SSL:
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = re.sub(r"-+", "-", value)
    return value.strip("-")


def unifi_login(session: requests.Session) -> None:
    """
    UniFi OS / CloudKey login endpoint.
    """
    url = f"{UNIFI_URL}/api/auth/login"
    payload = {
        "username": UNIFI_USERNAME,
        "password": UNIFI_PASSWORD,
        "rememberMe": False,
    }

    response = session.post(url, json=payload, verify=UNIFI_VERIFY_SSL, timeout=30)

    if response.status_code not in (200, 201):
        raise RuntimeError(
            f"UniFi login failed: HTTP {response.status_code}: {response.text[:300]}"
        )


def get_unifi_devices(session: requests.Session, site: str) -> List[Dict]:
    """
    UniFi OS / CloudKey Network Application path.
    """
    url = f"{UNIFI_URL}/proxy/network/api/s/{site}/stat/device"
    response = session.get(url, verify=UNIFI_VERIFY_SSL, timeout=60)

    if response.status_code != 200:
        raise RuntimeError(
            f"UniFi device query failed for site '{site}': "
            f"HTTP {response.status_code}: {response.text[:300]}"
        )

    data = response.json()
    return data.get("data", [])


def is_unifi_ap(device: Dict) -> bool:
    """
    UniFi APs generally have type 'uap'.
    """
    return device.get("type") == "uap"


def device_hostname(device: Dict) -> Optional[str]:
    """
    Choose how LibreNMS should know the device.

    HOSTNAME_MODE=dns:
      UniFi name 'AP Office 01' becomes ap-office-01.example.local

    HOSTNAME_MODE=ip:
      Uses the AP management IP from UniFi.
    """
    if HOSTNAME_MODE == "ip":
        return device.get("ip")

    name = device.get("name") or device.get("hostname") or device.get("mac")
    if not name:
        return None

    host = slugify(name)

    if HOSTNAME_DOMAIN:
        return f"{host}.{HOSTNAME_DOMAIN.lstrip('.')}"

    return host


def librenms_headers() -> Dict[str, str]:
    return {
        "X-Auth-Token": LIBRENMS_TOKEN,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def librenms_device_exists(hostname: str) -> bool:
    url = f"{LIBRENMS_URL}/api/v0/devices/{hostname}"
    response = requests.get(url, headers=librenms_headers(), timeout=30)

    if response.status_code == 200:
        try:
            payload = response.json()
            return payload.get("status") == "ok" and len(payload.get("devices", [])) > 0
        except Exception:
            return True

    if response.status_code in (404, 500):
        return False

    raise RuntimeError(
        f"LibreNMS device lookup failed for {hostname}: "
        f"HTTP {response.status_code}: {response.text[:300]}"
    )


def librenms_add_device(hostname: str, display_name: str) -> None:
    payload = {
        "hostname": hostname,
        "display_template": display_name,
        "poller_group": LIBRENMS_POLLER_GROUP,
        "ping_fallback": PING_FALLBACK,
        "force_add": FORCE_ADD,
    }

    if DEVICE_LOCATION:
        payload["location"] = DEVICE_LOCATION
        payload["override_sysLocation"] = OVERRIDE_SYSLOCATION

    if SNMP_VERSION in ("v1", "v2c"):
        if not SNMP_COMMUNITY:
            raise RuntimeError("SNMP_COMMUNITY is required for SNMP v1/v2c")
        payload["snmpver"] = SNMP_VERSION
        payload["community"] = SNMP_COMMUNITY

    elif SNMP_VERSION == "v3":
        required = {
            "SNMPV3_AUTHNAME": SNMPV3_AUTHNAME,
            "SNMPV3_AUTHPASS": SNMPV3_AUTHPASS,
            "SNMPV3_CRYPTOPASS": SNMPV3_CRYPTOPASS,
        }
        missing = [k for k, v in required.items() if not v]
        if missing:
            raise RuntimeError(f"Missing required SNMPv3 variables: {', '.join(missing)}")

        payload.update(
            {
                "snmpver": "v3",
                "authlevel": SNMPV3_AUTHLEVEL,
                "authname": SNMPV3_AUTHNAME,
                "authpass": SNMPV3_AUTHPASS,
                "authalgo": SNMPV3_AUTHALGO,
                "cryptopass": SNMPV3_CRYPTOPASS,
                "cryptoalgo": SNMPV3_CRYPTOALGO,
            }
        )

    else:
        raise RuntimeError(f"Unsupported SNMP_VERSION: {SNMP_VERSION}")

    if DRY_RUN:
        print(f"DRY-RUN would add {hostname}: {json.dumps(payload, sort_keys=True)}")
        return

    url = f"{LIBRENMS_URL}/api/v0/devices"
    response = requests.post(url, headers=librenms_headers(), json=payload, timeout=120)

    if response.status_code not in (200, 201):
        raise RuntimeError(
            f"LibreNMS add failed for {hostname}: "
            f"HTTP {response.status_code}: {response.text[:500]}"
        )

    print(f"ADDED {hostname}: {response.text[:300]}")


def main() -> int:
    print("Starting UniFi → LibreNMS AP sync")
    print(f"Sites: {', '.join(UNIFI_SITES)}")
    print(f"Hostname mode: {HOSTNAME_MODE}")
    print(f"LibreNMS poller group: {LIBRENMS_POLLER_GROUP}")
    print(f"Dry-run: {DRY_RUN}")

    session = requests.Session()
    unifi_login(session)

    added = 0
    existing = 0
    skipped = 0

    for site in UNIFI_SITES:
        print(f"Reading UniFi site: {site}")
        devices = get_unifi_devices(session, site)
        aps = [d for d in devices if is_unifi_ap(d)]

        print(f"Found {len(aps)} AP(s) in site {site}")

        for ap in aps:
            hostname = device_hostname(ap)
            display_name = ap.get("name") or ap.get("hostname") or hostname or "UniFi AP"

            if not hostname:
                print(f"SKIP AP without hostname/IP: {ap.get('mac')}")
                skipped += 1
                continue

            if librenms_device_exists(hostname):
                print(f"EXISTS {hostname}")
                existing += 1
                continue

            librenms_add_device(hostname, display_name)
            added += 1

    print(
        f"Done. added={added}, existing={existing}, skipped={skipped}, dry_run={DRY_RUN}"
    )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
