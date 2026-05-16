# Pi-hole Domain Lists

A supplementary blocklist collection for Pi-hole, built from real traffic 
analysis and OISD Big database filtering.

---

## Lists

### `captured`
Domains that slipped through commonly used filters, captured from real device 
traffic. Captured domains were reviewed and filtered to include only those 
related to **tracking, advertising, or marketing**.

### `oisd-unique`
Unique domains filtered from the [OISD Big](https://big.oisd.nl) database. 
The diff script ensures no duplication with the base filters listed below.

> **Attribution**  
> `oisd-unique` is derived from [OISD](https://oisd.nl) by 
> [@sjhgvr](https://github.com/sjhgvr).  
> OISD offers multiple variants:
> - [Basic](https://basic.oisd.nl) — lightweight, low false-positive rate
> - [Big](https://big.oisd.nl) — comprehensive, recommended for most users
> - [NSFW](https://nsfw.oisd.nl) — adult content blocking
>
> This repository does not claim ownership of any OISD content — only a 
> filtered subset is redistributed to avoid duplication with other mentioned lists.

---

## Base filters (deduplication baseline)

https://raw.githubusercontent.com/StevenBlack/hosts/master/hosts
https://raw.githubusercontent.com/hagezi/dns-blocklists/main/domains/pro.plus.txt
https://raw.githubusercontent.com/MajkiIT/polish-ads-filter/master/polish-pihole-filters/hostfile.txt

---

## Usage

Add the raw URLs of `/captured` and `/oisd-unique` as adlists in your 
Pi-hole admin panel, then run:

```bash
pihole -g
```

---

## Tools

Scripts used to generate and maintain these lists are available on the 
[`tools`](../../tree/tools) branch.