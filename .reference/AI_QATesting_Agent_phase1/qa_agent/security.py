from __future__ import annotations

import ipaddress
from urllib.parse import urlparse

from qa_agent.models import TargetSite


class TargetSafetyError(ValueError):
    """Raised when a URL target is not appropriate for this local URL runner."""


def validate_authorized_external_target(target: TargetSite) -> None:
    if not target.authorized:
        raise TargetSafetyError(
            "Execution requires authorized=true in the target configuration. "
            "Only run checks against targets you own or are explicitly allowed to test."
        )

    parsed = urlparse(target.base_url)
    host = parsed.hostname
    if parsed.scheme not in {"http", "https"} or not host:
        raise TargetSafetyError("Target must be an absolute http:// or https:// URL.")

    normalized = host.rstrip(".").lower()
    blocked_names = {
        "localhost",
        "metadata.google.internal",
        "metadata",
        "host.docker.internal",
    }
    if normalized in blocked_names or normalized.endswith((".local", ".internal")):
        raise TargetSafetyError("Local, internal, and cloud metadata hosts are blocked.")

    try:
        address = ipaddress.ip_address(normalized)
    except ValueError:
        return

    if (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_reserved
        or address.is_unspecified
    ):
        raise TargetSafetyError("Private, loopback, link-local, reserved, and multicast IP targets are blocked.")
