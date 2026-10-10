"""Security headers sent with every response, telling browsers to apply extra protections."""

from flask import Response

# One rule per line, to keep the policy easy to read and change.
CSP_RULES = (
    "default-src 'self'",
    # 'unsafe-eval' is needed by the standard Alpine.js build (see TODO: Alpine CSP build).
    "script-src 'self' 'unsafe-eval'",
    "style-src 'self'",
    "img-src 'self' data:",
    "font-src 'self'",
    "connect-src 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
    "base-uri 'self'",
    "object-src 'none'",
)
CONTENT_SECURITY_POLICY = "; ".join(CSP_RULES)

SECURITY_HEADERS: dict[str, str] = {
    "Content-Security-Policy": CONTENT_SECURITY_POLICY,
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=()",
    "Cross-Origin-Opener-Policy": "same-origin",
}


def add_security_headers(response: Response) -> Response:
    """Add the security headers to a response, unless it already sets them."""
    for name, value in SECURITY_HEADERS.items():
        response.headers.setdefault(name, value)
    return response
