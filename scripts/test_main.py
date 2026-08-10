from unittest.mock import patch, Mock
import requests
from main import extract_domains, get_root, filter_subdomains, fetch, fetch_with_fallback, protect_infrastructure

# extract_domains

class TestExtractDomains:

    def test_hosts_format(self):
        text = "0.0.0.0 ads.example.com"
        assert extract_domains(text) == {"ads.example.com"}

    def test_hosts_format_127(self):
        text = "127.0.0.1 tracker.example.com"
        assert extract_domains(text) == {"tracker.example.com"}

    def test_hosts_format_skips_localhost(self):
        text = "127.0.0.1 localhost"
        assert extract_domains(text) == set()

    def test_hosts_format_skips_self(self):
        text = "0.0.0.0 0.0.0.0"
        assert extract_domains(text) == set()

    def test_adblock_syntax(self):
        text = "||ads.example.com^"
        assert extract_domains(text) == {"ads.example.com"}

    def test_adblock_syntax_strips_wildcard(self):
        text = "||*.ads.example.com^"
        assert extract_domains(text) == {"ads.example.com"}

    def test_plain_domain(self):
        text = "tracker.example.com"
        assert extract_domains(text) == {"tracker.example.com"}

    def test_ignores_comments_hash(self):
        text = "# this is a comment\ntracker.example.com"
        assert extract_domains(text) == {"tracker.example.com"}

    def test_ignores_comments_exclamation(self):
        text = "! this is a comment\ntracker.example.com"
        assert extract_domains(text) == {"tracker.example.com"}

    def test_ignores_empty_lines(self):
        text = "\n\ntracker.example.com\n\n"
        assert extract_domains(text) == {"tracker.example.com"}

    def test_lowercases_domains(self):
        text = "Tracker.Example.COM"
        assert extract_domains(text) == {"tracker.example.com"}

    def test_multiple_formats_mixed(self):
        text = (
            "# comment\n"
            "0.0.0.0 hosts-domain.com\n"
            "||adblock-domain.com^\n"
            "plain-domain.com\n"
        )
        assert extract_domains(text) == {
            "hosts-domain.com",
            "adblock-domain.com",
            "plain-domain.com",
        }

    def test_empty_input(self):
        assert extract_domains("") == set()


# get_root

class TestGetRoot:

    def test_simple_domain(self):
        assert get_root("example.com") == "example.com"

    def test_subdomain(self):
        assert get_root("sub.example.com") == "example.com"

    def test_deep_subdomain(self):
        assert get_root("a.b.c.example.com") == "example.com"

    def test_country_tld(self):
        assert get_root("example.co.uk") == "example.co.uk"

    def test_subdomain_country_tld(self):
        assert get_root("sub.example.co.uk") == "example.co.uk"

    def test_polish_tld(self):
        assert get_root("example.com.pl") == "example.com.pl"

    def test_subdomain_polish_tld(self):
        assert get_root("sub.example.com.pl") == "example.com.pl"


# filter_subdomains

class TestFilterSubdomains:

    def test_keeps_root_domain(self):
        domains = {"example.com"}
        assert filter_subdomains(domains) == {"example.com"}

    def test_removes_subdomain_when_root_present(self):
        domains = {"example.com", "sub.example.com"}
        assert filter_subdomains(domains) == {"example.com"}

    def test_keeps_subdomain_when_root_absent(self):
        domains = {"sub.example.com"}
        assert filter_subdomains(domains) == {"sub.example.com"}

    def test_removes_multiple_subdomains(self):
        domains = {"example.com", "a.example.com", "b.example.com"}
        assert filter_subdomains(domains) == {"example.com"}

    def test_independent_domains_untouched(self):
        domains = {"example.com", "other.com"}
        assert filter_subdomains(domains) == {"example.com", "other.com"}

    def test_empty_set(self):
        assert filter_subdomains(set()) == set()

    def test_mixed_tlds(self):
        domains = {"example.co.uk", "sub.example.co.uk", "other.com"}
        assert filter_subdomains(domains) == {"example.co.uk", "other.com"}


# fetch / fetch_with_fallback
#
# CACHE_DIR is monkeypatched to a per-test tmp_path so tests never touch
# the real .cache directory and never depend on network state.

def _mock_response(text):
    resp = Mock()
    resp.text = text
    resp.raise_for_status = Mock()
    return resp


def _mock_failure():
    resp = Mock()
    resp.raise_for_status = Mock(side_effect=requests.HTTPError("404 Client Error"))
    return resp


class TestFetch:

    def test_fetch_returns_fresh_content_on_success(self, tmp_path, monkeypatch):
        monkeypatch.setattr("main.CACHE_DIR", tmp_path)
        with patch("main.requests.get", return_value=_mock_response("example.com")):
            assert fetch("https://example.com/list.txt") == "example.com"

    def test_fetch_allow_stale_false_returns_empty_on_failure_no_cache(self, tmp_path, monkeypatch):
        monkeypatch.setattr("main.CACHE_DIR", tmp_path)
        with patch("main.requests.get", return_value=_mock_failure()):
            assert fetch("https://example.com/list.txt", allow_stale=False) == ""

    def test_fetch_allow_stale_true_returns_stale_cache_on_failure(self, tmp_path, monkeypatch):
        monkeypatch.setattr("main.CACHE_DIR", tmp_path)
        url = "https://example.com/list.txt"

        # Seed a stale cache entry by succeeding once, then backdating cached_at.
        with patch("main.requests.get", return_value=_mock_response("stale-content")):
            fetch(url)

        import json
        import hashlib
        from datetime import datetime, timedelta
        key = hashlib.md5(url.encode()).hexdigest()
        meta_path = tmp_path / f"{key}.meta.json"
        old_time = datetime.now() - timedelta(hours=999)
        meta_path.write_text(json.dumps({"cached_at": old_time.isoformat()}))

        with patch("main.requests.get", return_value=_mock_failure()):
            assert fetch(url, allow_stale=True) == "stale-content"

    def test_fetch_allow_stale_false_ignores_stale_cache_on_failure(self, tmp_path, monkeypatch):
        monkeypatch.setattr("main.CACHE_DIR", tmp_path)
        url = "https://example.com/list.txt"

        with patch("main.requests.get", return_value=_mock_response("stale-content")):
            fetch(url)

        import json
        import hashlib
        from datetime import datetime, timedelta
        key = hashlib.md5(url.encode()).hexdigest()
        meta_path = tmp_path / f"{key}.meta.json"
        old_time = datetime.now() - timedelta(hours=999)
        meta_path.write_text(json.dumps({"cached_at": old_time.isoformat()}))

        with patch("main.requests.get", return_value=_mock_failure()):
            assert fetch(url, allow_stale=False) == ""


class TestFetchWithFallback:

    def test_uses_primary_when_it_succeeds(self, tmp_path, monkeypatch):
        monkeypatch.setattr("main.CACHE_DIR", tmp_path)
        with patch("main.requests.get", return_value=_mock_response("primary-content")):
            result = fetch_with_fallback(
                "https://primary.example/list.txt",
                "https://fallback.example/list.txt",
            )
        assert result == "primary-content"

    def test_falls_back_when_primary_fails(self, tmp_path, monkeypatch):
        # Regression test: fetch() previously returned stale cache content
        # on failure, which fetch_with_fallback() treated as a truthy
        # success, so it never tried the fallback URL even when the
        # primary genuinely failed. This must not happen again.
        monkeypatch.setattr("main.CACHE_DIR", tmp_path)

        def side_effect(url, **kwargs):
            if "primary" in url:
                return _mock_failure()
            return _mock_response("fallback-content")

        with patch("main.requests.get", side_effect=side_effect):
            result = fetch_with_fallback(
                "https://primary.example/list.txt",
                "https://fallback.example/list.txt",
            )
        assert result == "fallback-content"

    def test_falls_back_ignores_stale_cache_of_failed_primary(self, tmp_path, monkeypatch):
        # Even if the primary URL has a stale cache from a previous run,
        # a fresh failure must still trigger the fallback, not silently
        # return the old cached content.
        monkeypatch.setattr("main.CACHE_DIR", tmp_path)
        primary = "https://primary.example/list.txt"
        fallback = "https://fallback.example/list.txt"

        with patch("main.requests.get", return_value=_mock_response("old-primary-content")):
            fetch(primary)

        import json
        import hashlib
        from datetime import datetime, timedelta
        key = hashlib.md5(primary.encode()).hexdigest()
        meta_path = tmp_path / f"{key}.meta.json"
        old_time = datetime.now() - timedelta(hours=999)
        meta_path.write_text(json.dumps({"cached_at": old_time.isoformat()}))

        def side_effect(url, **kwargs):
            if url == primary:
                return _mock_failure()
            return _mock_response("fresh-fallback-content")

        with patch("main.requests.get", side_effect=side_effect):
            result = fetch_with_fallback(primary, fallback)

        assert result == "fresh-fallback-content"

    def test_tries_all_urls_in_order_before_giving_up(self, tmp_path, monkeypatch):
        monkeypatch.setattr("main.CACHE_DIR", tmp_path)
        attempted = []

        def side_effect(url, **kwargs):
            attempted.append(url)
            return _mock_failure()

        with patch("main.requests.get", side_effect=side_effect):
            fetch_with_fallback(
                "https://a.example/list.txt",
                "https://b.example/list.txt",
                "https://c.example/list.txt",
            )

        # Each URL attempted once during the allow_stale=False pass,
        # plus one more retry of the primary for the final stale-cache attempt.
        assert attempted.count("https://a.example/list.txt") == 2
        assert attempted.count("https://b.example/list.txt") == 1
        assert attempted.count("https://c.example/list.txt") == 1

    def test_returns_stale_primary_cache_when_all_sources_fail(self, tmp_path, monkeypatch):
        monkeypatch.setattr("main.CACHE_DIR", tmp_path)
        primary = "https://primary.example/list.txt"
        fallback = "https://fallback.example/list.txt"

        with patch("main.requests.get", return_value=_mock_response("last-known-good")):
            fetch(primary)

        import json
        import hashlib
        from datetime import datetime, timedelta
        key = hashlib.md5(primary.encode()).hexdigest()
        meta_path = tmp_path / f"{key}.meta.json"
        old_time = datetime.now() - timedelta(hours=999)
        meta_path.write_text(json.dumps({"cached_at": old_time.isoformat()}))

        with patch("main.requests.get", return_value=_mock_failure()):
            result = fetch_with_fallback(primary, fallback)

        assert result == "last-known-good"

    def test_returns_empty_when_everything_fails_and_no_cache(self, tmp_path, monkeypatch):
        monkeypatch.setattr("main.CACHE_DIR", tmp_path)
        with patch("main.requests.get", return_value=_mock_failure()):
            result = fetch_with_fallback(
                "https://a.example/list.txt",
                "https://b.example/list.txt",
            )
        assert result == ""


# protect_infrastructure
#
# This is the actual defense against a self-blocking loop: if an upstream
# list ever includes a domain the script itself needs to fetch its own
# sources, it must never survive into the generated output. Without this,
# a poisoned oisd-unique/captured could brick future runs the moment it's
# loaded back into Pi-hole.

class TestProtectInfrastructure:

    def test_strips_exact_infra_domain(self):
        domains = {"raw.githubusercontent.com", "ads.example.com"}
        result = protect_infrastructure(domains, "test")
        assert result == {"ads.example.com"}

    def test_strips_subdomain_of_infra_root(self):
        # e.g. some-tracker.github.com should not survive either, since
        # its root (github.com) is critical infrastructure.
        domains = {"telemetry.github.com", "ads.example.com"}
        result = protect_infrastructure(domains, "test")
        assert result == {"ads.example.com"}

    def test_strips_all_known_critical_domains(self):
        domains = {
            "github.com",
            "raw.githubusercontent.com",
            "cdn.jsdelivr.net",
            "gitlab.com",
            "big.oisd.nl",
            "legit-ad-tracker.com",
        }
        result = protect_infrastructure(domains, "test")
        assert result == {"legit-ad-tracker.com"}

    def test_leaves_unrelated_domains_untouched(self):
        domains = {"ads.example.com", "tracker.other.com"}
        result = protect_infrastructure(domains, "test")
        assert result == domains

    def test_empty_input(self):
        assert protect_infrastructure(set(), "test") == set()

    def test_does_not_over_match_lookalike_domains(self):
        # A domain that merely contains "github" or "oisd" as a substring
        # must not be stripped — only exact matches or true subdomains
        # of the protected roots.
        domains = {"notgithub.com", "myoisd.nl", "github.com.evil.net"}
        result = protect_infrastructure(domains, "test")
        assert result == domains