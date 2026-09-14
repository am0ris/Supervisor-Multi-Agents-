"""
SSRF (Server-Side Request Forgery) protection for outbound HTTP fetches.

Any URL we fetch on behalf of the agent comes from search results or LLM
output — i.e. untrusted input. Without validation, a malicious or
manipulated URL could point at internal infrastructure (localhost, cloud
metadata endpoints, private networks) and the agent would happily fetch
it. This module blocks that class of attack. It does NOT attempt to
bypass any server-side protection — it only restricts what WE choose to
request.
"""
import ipaddress
import socket
from urllib.parse import urlparse

ALLOWED_SCHEMES = {"http", "https"}

# Hostnames that are always blocked outright, regardless of DNS resolution.
BLOCKED_HOSTNAMES = {
    "localhost",
    "metadata.google.internal",  # GCP metadata
}

# Cloud metadata IP (AWS/GCP/Azure/OCI all use this well-known address).
CLOUD_METADATA_IP = ipaddress.ip_address("169.254.169.254")


class UnsafeURLError(ValueError):
    """Raised when a URL fails SSRF validation and must not be fetched."""


def _is_blocked_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    if ip == CLOUD_METADATA_IP:
        return True
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def validate_url(url: str) -> str:
    """
    Validates a URL is safe to fetch. Returns the URL unchanged if safe,
    raises UnsafeURLError otherwise.

    Checks:
    - scheme must be http/https (blocks file://, gopher://, ftp://, etc.)
    - hostname must not be a known-blocked name
    - resolved IP must not be private/loopback/link-local/cloud-metadata
    """
    parsed = urlparse(url)

    if parsed.scheme not in ALLOWED_SCHEMES:
        raise UnsafeURLError(f"Blocked scheme '{parsed.scheme}' in URL: {url}")

    hostname = parsed.hostname
    if not hostname:
        raise UnsafeURLError(f"URL has no hostname: {url}")

    if hostname.lower() in BLOCKED_HOSTNAMES:
        raise UnsafeURLError(f"Blocked hostname: {hostname}")

    # Resolve DNS and check every returned address. This also blocks
    # "DNS rebinding" tricks where a public-looking hostname resolves to
    # a private IP.
    try:
        addr_infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror as e:
        raise UnsafeURLError(f"Could not resolve hostname '{hostname}': {e}")

    for family, _, _, _, sockaddr in addr_infos:
        ip_str = sockaddr[0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            continue
        if _is_blocked_ip(ip):
            raise UnsafeURLError(
                f"URL '{url}' resolves to a blocked/internal address ({ip_str})"
            )

    return url
