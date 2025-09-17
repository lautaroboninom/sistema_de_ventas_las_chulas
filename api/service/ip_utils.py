import re
from typing import Any, Mapping

# Allowed characters for IPv4/IPv6 (with ports stripped out earlier)
_IP_PATTERN = re.compile(r"^[0-9a-fA-F:.]{3,45}$")

def get_client_ip(meta: Mapping[str, Any] | None) -> str:
    """Return best-effort client IP from request.META.

    Prefers the first entry in X-Forwarded-For, then X-Real-IP, then REMOTE_ADDR.
    Results are sanitized to avoid header injection and limited to 45 chars.
    """
    if not meta:
        return ""

    forwarded = meta.get("HTTP_X_FORWARDED_FOR", "") or ""
    if forwarded:
        for part in forwarded.split(","):
            candidate = part.strip()
            if candidate and _IP_PATTERN.match(candidate):
                return candidate[:45]

    real_ip = (meta.get("HTTP_X_REAL_IP", "") or "").strip()
    if real_ip and _IP_PATTERN.match(real_ip):
        return real_ip[:45]

    remote = (meta.get("REMOTE_ADDR", "") or "").strip()
    if remote and _IP_PATTERN.match(remote):
        return remote[:45]

    return remote[:45] if remote else ""
