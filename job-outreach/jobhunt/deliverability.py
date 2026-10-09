"""Sender-domain authentication checks (SPF, DKIM, DMARC, MX, FCrDNS)."""
from __future__ import annotations

import socket
from dataclasses import dataclass, field

import dns.exception
import dns.resolver
import dns.reversename

FREEMAIL = {
    "gmail.com", "googlemail.com", "yahoo.com", "outlook.com", "hotmail.com", "live.com",
    "aol.com", "icloud.com", "me.com", "proton.me", "protonmail.com", "gmx.com", "yandex.com",
}


@dataclass
class Check:
    name: str
    ok: bool
    detail: str
    required: bool = True


@dataclass
class Report:
    domain: str
    checks: list[Check] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(c.ok for c in self.checks if c.required)

    def failures(self) -> list[str]:
        return [f"{c.name}: {c.detail}" for c in self.checks if c.required and not c.ok]


def _txt(name: str, resolver: dns.resolver.Resolver) -> list[str]:
    try:
        answers = resolver.resolve(name, "TXT")
    except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.resolver.NoNameservers, dns.exception.Timeout):
        return []
    return [b"".join(r.strings).decode(errors="replace") for r in answers]


def check_domain(domain: str, dkim_selector: str = "", smtp_host: str = "",
                 resolver: dns.resolver.Resolver | None = None) -> Report:
    resolver = resolver or dns.resolver.Resolver()
    resolver.lifetime = 8.0
    domain = domain.lower().strip()
    rep = Report(domain)

    rep.checks.append(Check(
        "Dedicated domain", domain not in FREEMAIL,
        "free-mail domains cannot publish your SPF/DKIM/DMARC; use a dedicated outreach domain"
        if domain in FREEMAIL else "custom domain",
    ))

    spf = [t for t in _txt(domain, resolver) if t.lower().startswith("v=spf1")]
    if len(spf) == 1:
        rep.checks.append(Check("SPF", True, spf[0]))
    elif not spf:
        rep.checks.append(Check("SPF", False, "no v=spf1 TXT record"))
    else:
        rep.checks.append(Check("SPF", False, f"{len(spf)} SPF records found (RFC 7208 allows exactly one)"))

    dmarc = [t for t in _txt(f"_dmarc.{domain}", resolver) if t.lower().startswith("v=dmarc1")]
    if dmarc:
        tags = dict(
            (k.strip().lower(), v.strip()) for k, _, v in (p.partition("=") for p in dmarc[0].split(";")) if k.strip()
        )
        policy = tags.get("p", "").lower()
        ok = policy in ("none", "quarantine", "reject")
        rep.checks.append(Check("DMARC", ok, f"p={policy or 'missing'}" + ("" if ok else " (invalid policy)")))
    else:
        rep.checks.append(Check("DMARC", False, f"no v=DMARC1 TXT record at _dmarc.{domain}"))

    if dkim_selector:
        name = f"{dkim_selector}._domainkey.{domain}"
        dkim = [t for t in _txt(name, resolver) if "p=" in t]
        if not dkim:
            try:
                cname = resolver.resolve(name, "CNAME")
                dkim = [str(cname[0].target)]
            except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.resolver.NoNameservers, dns.exception.Timeout):
                pass
        rep.checks.append(Check("DKIM", bool(dkim), f"{name} " + ("published" if dkim else "not found")))
    else:
        rep.checks.append(Check("DKIM", False, "set DKIM_SELECTOR so the public key can be verified"))

    try:
        mx = resolver.resolve(domain, "MX")
        rep.checks.append(Check("MX", True, ", ".join(sorted(str(r.exchange).rstrip(".") for r in mx)), required=False))
    except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.resolver.NoNameservers, dns.exception.Timeout):
        rep.checks.append(Check("MX", False, "no MX record: replies and bounces will not reach you", required=False))

    if smtp_host:
        rep.checks.append(_fcrdns(smtp_host, resolver))
    return rep


def _fcrdns(host: str, resolver: dns.resolver.Resolver) -> Check:
    """Forward-confirmed reverse DNS of the SMTP relay. Advisory: hosted relays
    (Google Workspace, SES, Postmark...) manage this for you."""
    try:
        ip = socket.gethostbyname(host)
        ptr = str(resolver.resolve(dns.reversename.from_address(ip), "PTR")[0]).rstrip(".")
        forward = {str(r) for r in resolver.resolve(ptr, "A")}
        ok = ip in forward
        return Check("FCrDNS", ok, f"{host} -> {ip} -> {ptr} -> {'matches' if ok else 'mismatch'}", required=False)
    except (OSError, dns.exception.DNSException) as exc:
        return Check("FCrDNS", False, f"could not verify for {host}: {exc}", required=False)
