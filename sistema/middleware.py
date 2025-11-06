"""Custom middleware for security hardening of the admin interfaces."""

from __future__ import annotations

import ipaddress
from typing import Iterable, List

from django.conf import settings
from django.core.exceptions import PermissionDenied


class AdminIPAllowlistMiddleware:
    """Restrict access to the admin based on an IP/network allowlist.

    The middleware inspects the incoming request path and only enforces the
    allowlist for the root admin as well as the tenant admin URLs. Allowed
    networks can be configured through ``ADMIN_IP_ALLOWLIST`` using IPs or
    CIDR ranges. Optionally, a trusted header + value combination (e.g. a VPN
    header added by the platform) can be used to bypass the restriction.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        allowlist = getattr(settings, "ADMIN_IP_ALLOWLIST", [])
        self.allow_all = not allowlist
        self.allowed_networks: List[ipaddress._BaseNetwork] = []
        for value in allowlist:
            try:
                network = ipaddress.ip_network(value, strict=False)
            except ValueError as exc:  # pragma: no cover - configuration error
                raise ValueError(
                    f"ADMIN_IP_ALLOWLIST contiene una red/IPv4 inválida: {value!r}"
                ) from exc
            else:
                self.allowed_networks.append(network)

        self.trusted_header = getattr(settings, "ADMIN_TRUSTED_HEADER", None)
        trusted_values = getattr(settings, "ADMIN_TRUSTED_HEADER_VALUES", [])
        self.trusted_values = {value.lower() for value in trusted_values}

        self.root_prefix = f"/{getattr(settings, 'ROOT_ADMIN_URL', 'admin').strip('/')}/"
        tenant_segment = getattr(settings, 'TENANT_ADMIN_URL_SEGMENT', 'admin').strip('/')
        self.tenant_suffix = f"/{tenant_segment}/"

    def __call__(self, request):
        if self._should_enforce(request) and not self._is_allowed(request):
            raise PermissionDenied("Acceso no autorizado al panel de administración.")
        return self.get_response(request)

    def _should_enforce(self, request) -> bool:
        path = request.path or ""
        if path.startswith(self.root_prefix):
            return True

        # Paths formatted as /<tenant>/<segment>/...
        parts = path.split("/", 3)
        if len(parts) >= 3 and parts[2] == self.tenant_suffix.strip("/"):
            return True
        return False

    def _is_allowed(self, request) -> bool:
        if self.allow_all:
            return True

        if self._has_trusted_header(request):
            return True

        client_ips = self._extract_client_ips(request)
        for raw_ip in client_ips:
            try:
                ip = ipaddress.ip_address(raw_ip)
            except ValueError:
                continue
            if any(ip in network for network in self.allowed_networks):
                return True
        return False

    def _has_trusted_header(self, request) -> bool:
        if not self.trusted_header or not self.trusted_values:
            return False

        header_value = request.META.get(self.trusted_header)
        if not header_value:
            return False
        return header_value.strip().lower() in self.trusted_values

    @staticmethod
    def _extract_client_ips(request) -> Iterable[str]:
        header = request.META.get("HTTP_X_FORWARDED_FOR")
        if header:
            return [ip.strip() for ip in header.split(",") if ip.strip()]

        remote = request.META.get("REMOTE_ADDR")
        return [remote] if remote else []

