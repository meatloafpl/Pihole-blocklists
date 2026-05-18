# Pi-hole Domain Lists

A supplementary blocklist collection for Pi-hole, built from real traffic 
analysis and intelligent OISD Big database filtering.

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
**Current count:** ~0-50 domains (maintained minimal to avoid overlap)

### `oisd-unique`

Unique domains filtered from the comprehensive [OISD Big](https://big.oisd.nl) 
database. The generation script ensures zero duplication with the base filters 
listed below.

**Processing pipeline:**
1. Fetch OISD Big (~400k domains)
2. Remove domains already in base filters
3. Remove subdomains if root domain is blocked elsewhere
4. Filter internal subdomain redundancy
5. Result: ~180k-200k unique domains

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

https://raw.githubusercontent.com/StevenBlack/hosts/master/hosts
https://raw.githubusercontent.com/hagezi/dns-blocklists/main/domains/pro.plus.txt
https://raw.githubusercontent.com/MajkiIT/polish-ads-filter/master/polish-pihole-filters/hostfile.txt

If you use different base filters, you can modify `EXISTING_LISTS` in 
`scripts/main.py` to match your setup.

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

Scripts used to generate and maintain these lists are located in the `scripts/` 
directory.

### `main.py` — Domain List Generator

Analyzes existing blocklists, fetches OISD Big, removes duplicates and covered 
subdomains, then generates the `oisd-unique` list.

**What it does:**

1. **Fetches and parses** the following lists:
   - StevenBlack hosts
   - Hagezi Pro Plus
   - MajkiIT Polish filters
   - Local `captured` list

2. **Downloads OISD Big** database (400k+ domains)

3. **Computes the diff:**
   - Removes domains already covered by base filters
   - Removes subdomains if their root domain is already blocked
   - Filters out internal subdomain redundancy (e.g., keeps `example.com` 
     instead of both `sub.example.com` and `example.com`)

4. **Cleans the `captured` list** by removing domains already covered by 
   other filters

5. **Saves `oisd-unique`** with ~180k–200k new domains

**Features:**
- 1-hour HTTP cache to avoid unnecessary requests
- Supports hosts file format, adblock syntax, and plain domain lists
- Automatic root domain detection using `tldextract`

**Requirements:**
```bash
pip install requests tldextract
```

**Usage:**
```bash
cd scripts/
python main.py
```

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
git commit -m "Update lists"
git push
```

---

## 📊 Statistics

| List | Domains | Coverage |
|------|---------|----------|
| Base filters combined | ~625k | 100% |
| OISD Big | ~402k | — |
| OISD overlap with base | ~218k | 54.2% |
| **oisd-unique (new)** | **~184k** | **45.8%** |
| captured | ~0-50 | Manual |

*Stats based on latest generation run*

---

## ❓ FAQ

**Q: Why not just use OISD Big directly?**  
A: If you already use StevenBlack + Hagezi, adding OISD Big would include 
~218k duplicate domains, wasting Pi-hole's processing time. `oisd-unique` 
gives you only the new coverage.

**Q: How often should I update?**  
A: `oisd-unique` — weekly or monthly (OISD updates frequently)  
`captured` — updates are manual and infrequent

**Q: Can I customize the base filters?**  
A: Yes! Edit `EXISTING_LISTS` in `scripts/main.py` to match your Pi-hole setup.

**Q: Does this work with AdGuard Home?**  
A: Yes, both lists use plain domain format compatible with AdGuard Home.

**Q: The script shows "No significant new domains" — is something wrong?**  
A: No, this means OISD Big is well-covered by your base filters. Your setup 
is already comprehensive.

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

---

<p align="center">Made with ☕ for a cleaner internet</p>