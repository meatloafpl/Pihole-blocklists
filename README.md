# Pi-hole Domain Lists

A supplementary blocklist collection for Pi-hole, built from real traffic 
analysis and intelligent OISD Big database filtering.

> ⚠️ **This is not a standalone blocklist.**  
> It is a delta layer designed for users already running multiple major filters
> (StevenBlack, HaGeZi, OISD). Adding it without a strong baseline provides
> little value and may increase false positives.

This repository provides two curated blocklists that extend popular filters 
without duplication:

- **`captured`** — domains caught in the wild that slipped through common filters
- **`oisd-unique`** — unique domains from OISD Big, deduplicated against base filters

---

## 📋 Lists

### `captured`

Domains captured from real device traffic that evaded commonly used filters. 
Each domain has been manually reviewed and verified to be related to 
**tracking, advertising, or marketing**.

**Source:** Real-world network analysis  
**Update frequency:** Manual updates as new domains are discovered  
**Current count:** ~165 domains (maintained minimal to avoid overlap)

> **Note:** `main.py` automatically removes entries from `captured` that the
> base filters already block (the exact domain, or a parent domain, is listed
> there), so the list stays a pure delta. `check_captured.py` and CI flag dead
> (NXDOMAIN) entries. See [`main.py`](#mainpy--domain-list-generator).

### `oisd-unique`

Unique domains filtered from the comprehensive [OISD Big](https://big.oisd.nl) 
database. The generation script ensures zero duplication with the base filters 
listed below.

**Processing pipeline:**
1. Fetch OISD Big (~250k domains)
2. Remove domains already in base filters
3. Remove domains whose registrable domain (eTLD+1) already appears in the base filters
4. Filter internal subdomain redundancy
5. Strip any domain the generator itself depends on to fetch updates (see [Self-update protection](#-self-update-protection))
6. Result: ~110k unique domains

> **📌 Attribution**  
> 
> `oisd-unique` is derived from [OISD](https://oisd.nl) by 
> [@sjhgvr](https://github.com/sjhgvr).  
> 
> OISD offers multiple variants:
> - [Basic](https://basic.oisd.nl) — lightweight, low false-positive rate
> - [Big](https://big.oisd.nl) — comprehensive, recommended for most users
> - [NSFW](https://nsfw.oisd.nl) — adult content blocking
>
> This repository does not claim ownership of any OISD content. Only a 
> filtered subset is redistributed to avoid duplication with base lists.

---

## 🔗 Base Filters (Deduplication Baseline)

The following lists are used as the deduplication baseline when generating 
`oisd-unique`:

```
https://raw.githubusercontent.com/StevenBlack/hosts/master/hosts
https://raw.githubusercontent.com/hagezi/dns-blocklists/main/adblock/pro.plus.txt
https://raw.githubusercontent.com/MajkiIT/polish-ads-filter/master/polish-pihole-filters/hostfile.txt
```

If you use different base filters, you can modify `EXISTING_LISTS` in 
`scripts/main.py` to match your setup.

> **Note:** the Hagezi entry above is fetched with automatic fallback to
> jsDelivr and GitLab mirrors if `raw.githubusercontent.com` is temporarily
> unreachable. See [Fallback sources](#-fallback-sources) below.

---

## 🚀 Usage

### Adding to Pi-hole

1. **Copy raw URLs** for the lists you want:

```
https://raw.githubusercontent.com/meatloafpl/Pihole-blocklists/main/captured
https://raw.githubusercontent.com/meatloafpl/Pihole-blocklists/main/oisd-unique
```

2. **Add to Pi-hole:**
   - Go to **Pi-hole Admin Panel** → **Adlists**
   - Paste the URLs
   - Click **Add**

3. **Update gravity:**
```bash
pihole -g
```

4. **(Optional)** Set up a cron job to auto-update:
```bash
# Update every Sunday at 3 AM
0 3 * * 0 pihole -g
```

---

## 🛠️ Tools

Scripts used to generate and maintain these lists are located in the `scripts/` directory.

### `main.py` — Domain List Generator

Analyzes existing blocklists, fetches OISD Big, removes duplicates and covered
subdomains, then generates the `oisd-unique` list.

**What it does:**

1. **Fetches and parses** the following lists:
   - StevenBlack hosts
   - Hagezi Pro Plus (with automatic fallback, see below)
   - MajkiIT Polish filters
   - Local `captured` list

2. **Downloads OISD Big** database (~250k domains)

3. **Computes the diff:**
   - Removes domains already present in base filters (exact match)
   - Removes domains whose registrable domain already appears in the base
     filters (matching is by root domain, e.g. `msn.com`; a sibling subdomain
     being listed is enough)
   - Filters out internal subdomain redundancy (e.g., keeps `example.com`
     instead of both `sub.example.com` and `example.com`)

4. **Cleans the `captured` list** by removing entries already blocked by the
   base filters (exact match, or a parent domain is listed; a blocked *sibling*
   subdomain does not count)

5. **Protects against self-blocking** by stripping any domain the script
   itself needs to reach its own update sources (see below)

6. **Saves `oisd-unique`** with ~110k new domains

**Features:**
- 1-hour HTTP cache to avoid unnecessary requests
- Supports hosts file format, adblock syntax, and plain domain lists
- Automatic root domain detection using `tldextract`
- Automatic fallback sources for the Hagezi list
- Built-in protection against a self-blocking update loop

**Requirements:**
```bash
pip install requests tldextract
```

**Usage:**
```bash
cd scripts/
python main.py
```

#### 🔁 Fallback sources

`raw.githubusercontent.com` occasionally returns a transient 404 for the
Hagezi list due to CDN edge propagation delays. To avoid a failed run over
this, the Hagezi entry is fetched with automatic fallback, in order:

1. `raw.githubusercontent.com` (primary — always freshest)
2. `cdn.jsdelivr.net` (jsDelivr mirror)
3. `gitlab.com` (official Hagezi GitLab mirror)

If all three fail on a given run, the script falls back to the last
successfully cached copy of the primary source rather than failing outright.

#### 🛡️ Self-update protection

If an upstream list (OISD, Hagezi, MajkiIT) were ever to include a domain
this script itself depends on to fetch its own sources, that domain is stripped
from `captured` and `oisd-unique` before they're written. Protection works on
whole registrable domains, so these and all their subdomains are removed:
`github.com`, `githubusercontent.com`, `jsdelivr.net`, `gitlab.com`, `oisd.nl`.
Without this, a poisoned generated list could end up blocking its
own update infrastructure the moment it's loaded back into Pi-hole. A warning
is printed if anything is ever stripped.

---

### `check_captured.py` — Dead Domain Checker

Resolves all domains in `captured` concurrently (20 workers, via `1.1.1.1`) and
reports their DNS status. Useful for periodic manual cleanup before pushing
changes. Exits with code `1` if any domain returns NXDOMAIN.

**Statuses:**
- `OK` — domain resolves normally
- `TIMEOUT` — no response from authoritative server; does not mean the domain is dead, review manually
- `NXDOMAIN` — domain does not exist and should be removed from `captured`

**Usage:**
```bash
cd scripts/
python check_captured.py
```

No Python dependencies beyond the standard library. It shells out to the `host`
command (`dnsutils` / `bind9-dnsutils`) and falls back to `socket` if `host` is
not installed.

> **CI differs slightly:** the GitHub Actions check treats NXDOMAIN as dead only
> if both `1.1.1.1` and `8.8.8.8` agree; a single-resolver NXDOMAIN is reported
> as a warning for manual review.

---

### `test_main.py` — Unit Tests

Pytest test suite covering all core functions in `main.py`:
`extract_domains`, `get_root`, `filter_subdomains`, `fetch`,
`fetch_with_fallback`, and `protect_infrastructure`.

All network calls are mocked — the suite runs fully offline and never
touches the real `.cache/` directory or the network.

Run before pushing changes to catch regressions early.
Also executed automatically by CI on every push.

**Requirements:**
```bash
pip install pytest requests tldextract
```

**Usage:**
```bash
cd scripts/
pytest test_main.py -v
```
---

## 🤖 Automation (GitHub Actions)

| Workflow | Trigger | What it does |
|----------|---------|--------------|
| `lint.yml` (Lint & Test) | push / PR to `main` | Runs `pytest test_main.py` and checks `captured` for dead (NXDOMAIN) domains |
| `update-lists.yml` (Update Lists) | Sundays 03:00 UTC, or manually | Runs tests, regenerates `oisd-unique` (and cleans `captured`) with `main.py`, commits the result with `[skip ci]` |

So `oisd-unique` refreshes itself every week; you only need to run `main.py`
locally if you want an update in between.

---

## 📦 Installation

### For Pi-hole users (recommended):

Just add the raw URLs to your Pi-hole adlists — no installation needed.

### For maintainers/contributors:

1. **Clone the repository:**
```bash
git clone https://github.com/meatloafpl/Pihole-blocklists.git
cd Pihole-blocklists
```

2. **Install Python dependencies:**
```bash
pip install requests tldextract
```

3. **Run the generator:**
```bash
cd scripts/
python main.py
```

4. **Commit and push changes:**
```bash
git add captured oisd-unique
git commit -m ":zap: update lists"
git push
```

---

## 📊 Statistics

| List | Domains |
|------|---------|
| Base filters combined (StevenBlack + Hagezi Pro++ + MajkiIT + captured, unique) | ~285k |
| **oisd-unique** | **~111k** |
| captured | ~165 (manual) |

*Counts measured October 2026. `main.py` prints OISD Big size and its overlap
with the base filters on every run.*

---

## ❓ FAQ

**Q: Why not just use OISD Big directly?**  
A: If you already use StevenBlack + Hagezi, adding OISD Big would include 
duplicate domains, wasting Pi-hole's processing time. `oisd-unique` 
gives you only the new coverage.

**Q: How often should I update?**  
A: `oisd-unique` is regenerated automatically every Sunday by GitHub Actions,
so weekly or monthly gravity updates on your side are enough.  
`captured` — updates are manual and infrequent

**Q: Can I customize the base filters?**  
A: Yes! Edit `EXISTING_LISTS` in `scripts/main.py` to match your Pi-hole setup.

**Q: Does this work with AdGuard Home?**  
A: Yes, both lists use plain domain format compatible with AdGuard Home.

**Q: The script shows "No significant new domains" — is something wrong?**  
A: No, this means OISD Big is well-covered by your base filters. Your setup 
is already comprehensive.

**Q: Why did a run print a "stripped self-update infrastructure domain" warning?**  
A: One of the upstream lists (OISD, Hagezi, MajkiIT) included a domain the
script itself needs to fetch updates (e.g. a GitHub or jsDelivr subdomain).
It was automatically removed from the generated output — no action needed,
but worth knowing which upstream list triggered it if it happens repeatedly.

---

## 📝 License

Lists: Public domain (CC0)  
Scripts: MIT License

OISD content is used under [OISD's terms](https://oisd.nl) — proper attribution 
is maintained in this repository.

---

## 🙏 Acknowledgments

- **[@sjhgvr](https://github.com/sjhgvr)** for maintaining OISD
- **[StevenBlack](https://github.com/StevenBlack/hosts)** for the unified hosts file
- **[Hagezi](https://github.com/hagezi/dns-blocklists)** for Pro Plus lists
- **[MajkiIT](https://github.com/MajkiIT/polish-ads-filter)** for Polish filters

---

## 🤝 Contributing

Contributions welcome! If you find domains that should be in `captured`, 
please open an issue with:

- Domain name
- Category (tracking/ads/marketing)
- How you discovered it (which site/app triggered it)

### Commit convention

This repository uses [gitmoji](https://gitmoji.dev) with lowercase messages:

| Emoji | Use case |
|-------|----------|
| `:zap:` | update lists |
| `:bug:` | fix incorrect behavior |
| `:sparkles:` | new feature |
| `:construction_worker:` | ci/cd changes |
| `:white_check_mark:` | add or update tests |
| `:memo:` | documentation changes |
| `:fire:` | remove files or code |
| `:shield:` | improve resilience, safety, or self-protection |

Example: `:bug: fix subdomain filtering when root domain is absent`

---

<p align="center">Made with ☕ for a cleaner internet</p>