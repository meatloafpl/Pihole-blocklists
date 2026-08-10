import re
import sys
import json
import hashlib
import requests
import tldextract
from pathlib import Path
from datetime import datetime, timedelta

ROOT_DIR = Path(__file__).resolve().parent.parent

CAPTURED_PATH = ROOT_DIR / "captured"
EXISTING_LISTS = [
    "https://raw.githubusercontent.com/StevenBlack/hosts/master/hosts",
    ("https://raw.githubusercontent.com/hagezi/dns-blocklists/main/adblock/pro.plus.txt",
     "https://cdn.jsdelivr.net/gh/hagezi/dns-blocklists@main/adblock/pro.plus.txt",
     "https://gitlab.com/hagezi/mirror/-/raw/main/dns-blocklists/adblock/pro.plus.txt"),
    "https://raw.githubusercontent.com/MajkiIT/polish-ads-filter/master/polish-pihole-filters/hostfile.txt",
    CAPTURED_PATH,
]

OISD_URL = "https://big.oisd.nl"
CACHE_DIR = ROOT_DIR / ".cache"
CACHE_TTL = timedelta(hours=1)
TIMEOUT = 60

OISD_UNIQUE_PATH = ROOT_DIR / "oisd-unique"

# Domains this script itself depends on to fetch its own data sources.
# If any upstream blocklist (OISD, Hagezi, MajkiIT) ever includes one of
# these, and it lands in oisd-unique or captured, the resulting Pi-hole
# list would block the very infrastructure needed to update itself on
# the next run. This set is stripped from all generated output as a
# hard safety net, independent of which lists are in use.
CRITICAL_INFRA_DOMAINS = {
    "github.com",
    "raw.githubusercontent.com",
    "githubusercontent.com",
    "cdn.jsdelivr.net",
    "jsdelivr.net",
    "gitlab.com",
    "big.oisd.nl",
    "oisd.nl",
}


def protect_infrastructure(domains: set[str], label: str) -> set[str]:
    blocked = {d for d in domains if d in CRITICAL_INFRA_DOMAINS or get_root(d) in CRITICAL_INFRA_DOMAINS}
    if blocked:
        print(f" WARNING: stripped {len(blocked)} self-update infrastructure domain(s) from {label}: {sorted(blocked)}", file=sys.stderr)
    return domains - blocked


def cache_path(url: str) -> Path:
    key = hashlib.md5(url.encode()).hexdigest()
    return CACHE_DIR / f"{key}.txt"


def cache_meta_path(url: str) -> Path:
    key = hashlib.md5(url.encode()).hexdigest()
    return CACHE_DIR / f"{key}.meta.json"


def fetch(url: str, allow_stale: bool = True) -> str:
    CACHE_DIR.mkdir(exist_ok=True)
    cp = cache_path(url)
    cmp = cache_meta_path(url)

    if cp.exists() and cmp.exists():
        meta = json.loads(cmp.read_text())
        cached_at = datetime.fromisoformat(meta["cached_at"])
        if datetime.now() - cached_at < CACHE_TTL:
            age = datetime.now() - cached_at
            print(f" (cached {int(age.total_seconds() / 3600)}h ago)")
            return cp.read_text(encoding="utf-8")

    try:
        r = requests.get(url, timeout=TIMEOUT, headers={"User-Agent": "pihole-list-updater/1.0"})
        r.raise_for_status()
        text = r.text
        cp.write_text(text, encoding="utf-8")
        cmp.write_text(json.dumps({"cached_at": datetime.now().isoformat()}))
        print(f" (fetched fresh)")
        return text
    except requests.RequestException as e:
        print(f" ERROR fetching {url}: {e}", file=sys.stderr)
        if allow_stale and cp.exists():
            print(f" Using stale cache as fallback", file=sys.stderr)
            return cp.read_text(encoding="utf-8")
        return ""


def fetch_with_fallback(*urls: str) -> str:
    for i, url in enumerate(urls):
        if i > 0:
            print(f" Trying fallback: {url}", file=sys.stderr)
        text = fetch(url, allow_stale=False)
        if text:
            return text

    print(f" All sources failed, trying stale cache of primary", file=sys.stderr)
    return fetch(urls[0], allow_stale=True)


def extract_domains(text: str) -> set[str]:
    domains = set()
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith('#') or line.startswith('!'):
            continue

        if re.match(r'^(0\.0\.0\.0|127\.0\.0\.1)\s+', line):
            parts = line.split()
            if len(parts) >= 2 and parts[1] not in ('0.0.0.0', 'localhost', 'local'):
                domains.add(parts[1].lower())

        elif line.startswith('||'):
            match = re.match(r'^\|\|([a-zA-Z0-9._*-]+)\^', line)
            if match:
                domain = match.group(1).lstrip('*.')
                if domain:
                    domains.add(domain.lower())

        elif re.match(r'^[a-zA-Z0-9][a-zA-Z0-9._-]*\.[a-zA-Z]{2,}$', line):
            domains.add(line.lower())

    return domains


def get_root(domain: str) -> str:
    ext = tldextract.extract(domain)
    if ext.domain and ext.suffix:
        return f"{ext.domain}.{ext.suffix}"
    parts = domain.split('.')
    return '.'.join(parts[-2:]) if len(parts) >= 2 else domain


def filter_subdomains(domains: set[str]) -> set[str]:
    filtered = set()
    for d in domains:
        root = get_root(d)
        if d == root or root not in domains:
            filtered.add(d)
    return filtered


def main():
    print("=" * 60)
    print("Fetching existing lists...")
    print("=" * 60)

    existing_domains: set[str] = set()
    captured_domains: set[str] = set()

    for entry in EXISTING_LISTS:
        if isinstance(entry, Path):
            name = entry.name
            print(f" [{name}] (local)")
            text = entry.read_text(encoding="utf-8") if entry.exists() else ""
        elif isinstance(entry, tuple):
            primary = entry[0]
            name = primary.split('/')[-1]
            print(f" [{name}]")
            text = fetch_with_fallback(*entry)
        else:
            name = entry.split('/')[-1]
            print(f" [{name}]")
            text = fetch(entry)

        parsed = extract_domains(text)
        print(f" -> {len(parsed):>7,} domains")
        existing_domains.update(parsed)

        if isinstance(entry, Path) and entry.name == "captured":
            captured_domains = parsed

    print(f"\n TOTAL: {len(existing_domains):,} unique domains\n")

    existing_roots = {get_root(d) for d in existing_domains}

    existing_without_captured = existing_domains - captured_domains
    existing_without_captured_roots = {get_root(d) for d in existing_without_captured}

    captured_covered = {
        d for d in captured_domains
        if get_root(d) in existing_without_captured_roots
    }
    captured_cleaned = captured_domains - captured_covered
    captured_cleaned = protect_infrastructure(captured_cleaned, "captured")

    print("=" * 60)
    print("Cleaning captured list...")
    print("=" * 60)
    print(f" Domains in captured before: {len(captured_domains):>7,}")
    print(f" Covered by other lists: {len(captured_covered):>7,}")
    print(f" Domains in captured after: {len(captured_cleaned):>7,}")

    if captured_cleaned != captured_domains:
        CAPTURED_PATH.write_text(
            '\n'.join(sorted(captured_cleaned)) + '\n',
            encoding="utf-8"
        )
    else:
        print(f" No duplicates found — captured unchanged")

    print("\n" + "=" * 60)
    print("Fetching OISD Big...")
    print("=" * 60)
    text = fetch(OISD_URL)
    oisd_domains = extract_domains(text)
    print(f"  -> {len(oisd_domains):,} domains in OISD Big")

    print("\n" + "=" * 60)
    print("Computing diff...")
    print("=" * 60)

    unique_raw = oisd_domains - existing_domains
    print(f"  Raw unique domains: {len(unique_raw):>7,}")

    unique_no_covered_subs = {
        d for d in unique_raw
        if get_root(d) not in existing_roots
    }
    print(f"  After removing covered subdomains: {len(unique_no_covered_subs):>7,}")

    unique_filtered = filter_subdomains(unique_no_covered_subs)
    unique_filtered = protect_infrastructure(unique_filtered, "oisd-unique")
    print(f"  After removing internal subdomains: {len(unique_filtered):>7,}")

    overlap = len(oisd_domains) - len(unique_raw)
    overlap_pct = overlap / len(oisd_domains) * 100 if oisd_domains else 0
    print(f"\n OISD coverage by your lists: {overlap_pct:.1f}%")

    if len(unique_filtered) < 100:
        print("\n No significant new domains — lists are up to date.")
    else:
        print(f"\n New domains to add: {len(unique_filtered):,}")

    print("\n" + "=" * 60)
    print("Saving...")
    print("=" * 60)

    OISD_UNIQUE_PATH.write_text(
        '\n'.join(sorted(unique_filtered)) + '\n',
        encoding="utf-8"
    )
    print(f" /oisd-unique -> {OISD_UNIQUE_PATH} ({len(unique_filtered):,} domains)")

    print("\nDone!")


if __name__ == "__main__":
    main()