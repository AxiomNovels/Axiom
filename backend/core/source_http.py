"""Source allowlists apply before every request, including redirects."""
from urllib.parse import urljoin, urlsplit, urlunsplit


def source_url(value: str, domain: str) -> str:
    value = str(value).strip()
    try:
        parsed = urlsplit(value)
        valid = (
            parsed.scheme in ("http", "https")
            and parsed.hostname in (domain, f"www.{domain}")
            and parsed.username is None and parsed.password is None
            and parsed.port in (None, 80 if parsed.scheme == "http" else 443)
            and not any(ord(char) < 32 or char == "\\" for char in value)
        )
    except ValueError:
        valid = False
    if not valid:
        raise ValueError(f"Expected a public {domain} URL.")
    return urlunsplit(("https", parsed.hostname, parsed.path, parsed.query, ""))


def source_get(get, url: str, domain: str, *, redirect_option="allow_redirects", **kwargs):
    """Follow at most five same-source redirects without forwarding to other hosts."""
    url = source_url(url, domain)
    kwargs[redirect_option] = False
    for _ in range(6):
        response = get(url, **kwargs)
        if response.status_code not in (301, 302, 303, 307, 308):
            return response
        location = response.headers.get("location") or response.headers.get("Location")
        if not location:
            raise ValueError("Source redirect has no destination.")
        url = source_url(urljoin(url, location), domain)
    raise ValueError("Source redirected too many times.")
