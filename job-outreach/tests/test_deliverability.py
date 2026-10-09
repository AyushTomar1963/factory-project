import dns.resolver

from jobhunt import deliverability


class _TXT:
    def __init__(self, s):
        self.strings = [s.encode()]


class _MX:
    def __init__(self, h):
        self.exchange = h


class FakeResolver:
    def __init__(self, records):
        self.records = records
        self.lifetime = 0

    def resolve(self, name, rtype):
        try:
            return self.records[(name, rtype)]
        except KeyError:
            raise dns.resolver.NXDOMAIN


def test_fully_authenticated_domain_passes():
    r = FakeResolver({
        ("out.dev", "TXT"): [_TXT("v=spf1 include:_spf.google.com ~all"), _TXT("google-site-verification=x")],
        ("_dmarc.out.dev", "TXT"): [_TXT("v=DMARC1; p=quarantine; rua=mailto:d@out.dev")],
        ("google._domainkey.out.dev", "TXT"): [_TXT("v=DKIM1; k=rsa; p=MIIB...")],
        ("out.dev", "MX"): [_MX("aspmx.l.google.com.")],
    })
    rep = deliverability.check_domain("out.dev", "google", resolver=r)
    assert rep.ok, rep.failures()
    assert {c.name: c.ok for c in rep.checks}["MX"]


def test_missing_records_and_freemail_fail():
    rep = deliverability.check_domain("gmail.com", "", resolver=FakeResolver({}))
    failed = {f.split(":")[0] for f in rep.failures()}
    assert failed == {"Dedicated domain", "SPF", "DMARC", "DKIM"}


def test_duplicate_spf_fails():
    r = FakeResolver({("d.dev", "TXT"): [_TXT("v=spf1 a ~all"), _TXT("v=spf1 mx ~all")]})
    rep = deliverability.check_domain("d.dev", "s", resolver=r)
    assert any("exactly one" in f for f in rep.failures())
