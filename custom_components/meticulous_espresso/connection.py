"""Connection helpers: API base URL construction and port auto-detection.

Older Meticulous firmware exposes the backend directly on port 8080. Newer
firmware binds the backend to localhost and serves the API through a reverse
proxy on port 80. Both are supported by probing the candidate ports.
"""

from __future__ import annotations

import logging
import socket
from typing import Any

from homeassistant.core import HomeAssistant

from .const import PORT_CANDIDATES, PORT_PROBE_TIMEOUT

_LOGGER = logging.getLogger(__name__)


def build_base_url(host: str, port: int) -> str:
    """Return the API base URL for a host/port.

    No trailing slash: pyMeticulous appends "/api/v1/..." to the base URL and a
    trailing slash produces "//api/v1/..." which the reverse proxy rejects.
    """
    return f"http://{host}:{port}"


def _port_open(host: str, port: int) -> bool:
    """Return True if a TCP connection to host:port can be established."""
    try:
        with socket.create_connection((host, port), timeout=PORT_PROBE_TIMEOUT):
            return True
    except OSError:
        return False


def probe_port(host: str, port: int) -> Any | None:
    """Probe host:port for the Meticulous API. Returns device info or None.

    Blocking — must be run in an executor.
    """
    from meticulous import Api
    from meticulous.api_types import APIError

    if not _port_open(host, port):
        return None

    try:
        api = Api(base_url=build_base_url(host, port))
        result = api.get_device_info()
    except Exception as err:  # noqa: BLE001 - any failure means "not the API"
        _LOGGER.debug("Probe of %s:%s failed: %s", host, port, err)
        return None

    if isinstance(result, APIError) or result is None:
        return None

    return result


def discover_api(host: str, preferred_port: int | None = None) -> tuple[int, Any] | None:
    """Find the port serving the Meticulous API on host.

    Tries the preferred port first (if given), then the known candidates.
    Returns (port, device_info) or None. Blocking — run in an executor.
    """
    ports: list[int] = []
    if preferred_port:
        ports.append(preferred_port)
    ports.extend(p for p in PORT_CANDIDATES if p not in ports)

    for port in ports:
        info = probe_port(host, port)
        if info is not None:
            _LOGGER.debug("Meticulous API found at %s:%s", host, port)
            return port, info

    return None


async def async_discover_api(
    hass: HomeAssistant, host: str, preferred_port: int | None = None
) -> tuple[int, Any] | None:
    """Async wrapper around :func:`discover_api`."""
    return await hass.async_add_executor_job(discover_api, host, preferred_port)
