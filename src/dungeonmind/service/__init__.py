"""Optional FastAPI Mind Turn host. Requires the ``api`` extra to import ``api``."""

from .demo_access import DemoAccessBinding, authorize_demo_request
from .error_mapping import error_envelope, http_status_for

__all__ = [
    "DemoAccessBinding",
    "authorize_demo_request",
    "error_envelope",
    "http_status_for",
]
