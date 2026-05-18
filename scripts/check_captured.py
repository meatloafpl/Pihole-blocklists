import sys
import socket
import subprocess
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

CAPTURED_PATH = Path(__file__).resolve().parent.parent / "captured"
DNS_SERVER    = "1.1.1.1"
TIMEOUT_SECS  = 5
MAX_WORKERS   = 20


def resolve(domain: str) -> tuple[str, str]:
    # Returns (domain, status) where status is OK | NXDOMAIN | TIMEOUT
    try:
        result = subprocess.run(
            ["host", "-W", str(TIMEOUT_SECS), domain, DNS_SERVER],
            capture_output=True,
            text=True,
            timeout=TIMEOUT_SECS + 2,
        )
        output = result.stdout + result.stderr
        if "NXDOMAIN" in output or "not found" in output:
            return domain, "NXDOMAIN"
        if result.returncode == 0:
            return domain, "OK"
        return domain, "TIMEOUT"
    except subprocess.TimeoutExpired:
        return domain, "TIMEOUT"
    except FileNotFoundError:
        # 'host' not available — fall back to socket
        try:
            socket.setdefaulttimeout(TIMEOUT_SECS)
            socket.gethostbyname(domain)
            return domain, "OK"
        except socket.gaierror as e:
            if "Name or service not known" in str(e):
                return domain, "NXDOMAIN"
            return domain, "TIMEOUT"


def main():
    if not CAPTURED_PATH.exists():
        print("captured file not found — skipping check.")
        sys.exit(0)

    domains = [
        line.strip()
        for line in CAPTURED_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]

    if not domains:
        print("captured is empty — nothing to check.")
        sys.exit(0)

    print(f"Checking {len(domains)} domains against {DNS_SERVER}...")

    results = {"OK": [], "NXDOMAIN": [], "TIMEOUT": []}

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(resolve, d): d for d in domains}
        for future in as_completed(futures):
            domain, status = future.result()
            results[status].append(domain)
            if status != "OK":
                label = "NXDOMAIN" if status == "NXDOMAIN" else "TIMEOUT "
                print(f"  {label} : {domain}")

    print()
    print(f"  OK      : {len(results['OK'])}")
    print(f"  TIMEOUT : {len(results['TIMEOUT'])}  (warning only — do not remove automatically)")
    print(f"  NXDOMAIN: {len(results['NXDOMAIN'])}")

    if results["TIMEOUT"]:
        print()
        print("WARNING: Timeouts do not mean a domain is dead.")
        print("         The authoritative server may be slow or unreachable.")
        print("         Review manually before removing.")

    if results["NXDOMAIN"]:
        print()
        print("FAIL: The following domains returned NXDOMAIN and should be removed from captured:")
        for d in sorted(results["NXDOMAIN"]):
            print(f"   {d}")
        sys.exit(1)

    print()
    print("OK: No dead domains found.")
    sys.exit(0)

if __name__ == "__main__":
    main()