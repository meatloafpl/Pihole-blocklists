from main import extract_domains, get_root, filter_subdomains

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