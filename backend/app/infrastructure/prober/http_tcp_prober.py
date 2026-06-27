from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone

import httpx

from app.domain.models import Observation, Service, ServiceType

_HTTP_TIMEOUT_S = 10.0
_TCP_TIMEOUT_S = 5.0


class HttpTcpProber:
    """Performs HTTP and TCP black-box probes against a service target."""

    async def probe(self, service: Service) -> Observation:
        """Probe the given service and return an Observation."""
        if service.type is ServiceType.HTTP:
            return await self._probe_http(service)
        if service.type is ServiceType.TCP:
            return await self._probe_tcp(service)
        # Defensive: unknown type is treated as a failed probe.
        return Observation(
            service_id=service.id,
            time=datetime.now(timezone.utc),
            latency_ms=-1.0,
            status_code=None,
            is_up=False,
            error=f"Unsupported service type: {service.type!r}",
        )

    async def _probe_http(self, service: Service) -> Observation:
        target = service.target or ""
        started = time.perf_counter()
        try:
            async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT_S) as client:
                response = await client.get(target)
            latency_ms = (time.perf_counter() - started) * 1000.0
            expected = service.expected_status
            is_up = expected is None or response.status_code == expected
            error = (
                None
                if is_up
                else f"Unexpected status {response.status_code} (expected {expected})"
            )
            return Observation(
                service_id=service.id,
                time=datetime.now(timezone.utc),
                latency_ms=latency_ms,
                status_code=response.status_code,
                is_up=is_up,
                error=error,
            )
        except Exception as exc:  # noqa: BLE001 - any failure means the target is down
            return Observation(
                service_id=service.id,
                time=datetime.now(timezone.utc),
                latency_ms=-1.0,
                status_code=None,
                is_up=False,
                error=str(exc) or exc.__class__.__name__,
            )

    async def _probe_tcp(self, service: Service) -> Observation:
        host, port, parse_error = self._parse_host_port(service.target)
        if parse_error is not None:
            return Observation(
                service_id=service.id,
                time=datetime.now(timezone.utc),
                latency_ms=-1.0,
                status_code=None,
                is_up=False,
                error=parse_error,
            )

        started = time.perf_counter()
        writer: asyncio.StreamWriter | None = None
        try:
            _reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port),
                timeout=_TCP_TIMEOUT_S,
            )
            latency_ms = (time.perf_counter() - started) * 1000.0
            return Observation(
                service_id=service.id,
                time=datetime.now(timezone.utc),
                latency_ms=latency_ms,
                status_code=None,
                is_up=True,
                error=None,
            )
        except Exception as exc:  # noqa: BLE001 - any failure means the target is down
            return Observation(
                service_id=service.id,
                time=datetime.now(timezone.utc),
                latency_ms=-1.0,
                status_code=None,
                is_up=False,
                error=str(exc) or exc.__class__.__name__,
            )
        finally:
            if writer is not None:
                writer.close()
                try:
                    await writer.wait_closed()
                except Exception:  # noqa: BLE001 - best-effort cleanup
                    pass

    @staticmethod
    def _parse_host_port(target: str | None) -> tuple[str, int, str | None]:
        """Parse a ``host:port`` string into its components."""
        if not target:
            return "", 0, "TCP target is empty"
        if ":" not in target:
            return "", 0, f"Invalid TCP target {target!r}: expected 'host:port'"
        host, _, port_str = target.rpartition(":")
        if not host:
            return "", 0, f"Invalid TCP target {target!r}: missing host"
        try:
            port = int(port_str)
        except ValueError:
            return "", 0, f"Invalid TCP target {target!r}: port is not an integer"
        if not (0 < port < 65536):
            return "", 0, f"Invalid TCP target {target!r}: port out of range"
        return host, port, None
