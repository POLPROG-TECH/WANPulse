"""Tests for WANPulse probe engines."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from custom_components.wanpulse.models import ProbeMethod, ProbeTarget
from custom_components.wanpulse.probes import get_probe_engine
from custom_components.wanpulse.probes.dns import DNSProbeEngine
from custom_components.wanpulse.probes.http import HTTPProbeEngine
from custom_components.wanpulse.probes.tcp import TCPProbeEngine


class TestGetProbeEngine:
    """Tests for probe engine factory."""

    def test_tcp_engine(self) -> None:
        engine = get_probe_engine("tcp")
        assert isinstance(engine, TCPProbeEngine)

    def test_http_engine(self) -> None:
        engine = get_probe_engine("http")
        assert isinstance(engine, HTTPProbeEngine)

    def test_dns_engine(self) -> None:
        engine = get_probe_engine("dns")
        assert isinstance(engine, DNSProbeEngine)

    def test_unknown_engine(self) -> None:
        with pytest.raises(ValueError, match="Unknown probe method"):
            get_probe_engine("icmp")


class TestTCPProbeEngine:
    """Tests for the TCP probe engine."""

    @pytest.mark.asyncio
    async def test_successful_connect(self) -> None:
        target = ProbeTarget(host="1.1.1.1", label="Test", method=ProbeMethod.TCP, port=443)
        engine = TCPProbeEngine()

        mock_writer = MagicMock()
        mock_writer.close = MagicMock()
        mock_writer.wait_closed = AsyncMock()

        with (
            patch("asyncio.open_connection", return_value=Mock()),
            patch("asyncio.wait_for", new_callable=AsyncMock) as mock_wait,
        ):
            mock_wait.return_value = (MagicMock(), mock_writer)
            result = await engine.async_probe(target, timeout=5.0)

        assert result.success is True
        assert result.latency_ms is not None
        assert result.latency_ms >= 0

    @pytest.mark.asyncio
    async def test_timeout(self) -> None:
        target = ProbeTarget(host="1.1.1.1", label="Test", method=ProbeMethod.TCP, port=443)
        engine = TCPProbeEngine()

        with (
            patch("asyncio.open_connection", return_value=Mock()),
            patch("asyncio.wait_for", side_effect=TimeoutError),
        ):
            result = await engine.async_probe(target, timeout=1.0)

        assert result.success is False
        assert "timed out" in (result.error or "")

    @pytest.mark.asyncio
    async def test_connection_refused(self) -> None:
        target = ProbeTarget(host="1.1.1.1", label="Test", method=ProbeMethod.TCP, port=443)
        engine = TCPProbeEngine()

        with (
            patch("asyncio.open_connection", return_value=Mock()),
            patch("asyncio.wait_for", side_effect=OSError("Connection refused")),
        ):
            result = await engine.async_probe(target, timeout=5.0)

        assert result.success is False
        assert "Connection refused" in (result.error or "")

    @pytest.mark.asyncio
    async def test_default_port(self) -> None:
        target = ProbeTarget(host="1.1.1.1", label="Test", method=ProbeMethod.TCP)
        engine = TCPProbeEngine()

        mock_writer = MagicMock()
        mock_writer.close = MagicMock()
        mock_writer.wait_closed = AsyncMock()

        with (
            patch("asyncio.open_connection", return_value=Mock()),
            patch("asyncio.wait_for", new_callable=AsyncMock) as mock_wait,
        ):
            mock_wait.return_value = (MagicMock(), mock_writer)
            result = await engine.async_probe(target, timeout=5.0)

        assert result.success is True


class TestHTTPProbeEngine:
    """Tests for the HTTP probe engine."""

    @pytest.mark.asyncio
    async def test_successful_head(self) -> None:
        target = ProbeTarget(host="https://example.com", label="Test", method=ProbeMethod.HTTP)
        engine = HTTPProbeEngine()

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)

        mock_session = MagicMock()
        mock_session.head = MagicMock(return_value=mock_resp)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = await engine.async_probe(target, timeout=5.0)

        assert result.success is True
        assert result.latency_ms is not None

    @pytest.mark.asyncio
    async def test_timeout(self) -> None:
        target = ProbeTarget(host="https://example.com", label="Test", method=ProbeMethod.HTTP)
        engine = HTTPProbeEngine()

        mock_session = MagicMock()
        mock_resp = MagicMock()
        mock_resp.__aenter__ = AsyncMock(side_effect=TimeoutError)
        mock_resp.__aexit__ = AsyncMock(return_value=False)
        mock_session.head = MagicMock(return_value=mock_resp)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = await engine.async_probe(target, timeout=1.0)

        assert result.success is False
        assert "timed out" in (result.error or "")

    @pytest.mark.asyncio
    async def test_url_construction_no_scheme(self) -> None:
        target = ProbeTarget(host="example.com", label="Test", method=ProbeMethod.HTTP, port=443)
        engine = HTTPProbeEngine()

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_resp.__aexit__ = AsyncMock(return_value=False)

        mock_session = MagicMock()
        mock_session.head = MagicMock(return_value=mock_resp)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = await engine.async_probe(target, timeout=5.0)

        assert result.success is True


class TestDNSProbeEngine:
    """Tests for the DNS probe engine."""

    @pytest.mark.asyncio
    async def test_successful_resolve(self) -> None:
        target = ProbeTarget(host="www.google.com", label="Test", method=ProbeMethod.DNS)
        engine = DNSProbeEngine()

        mock_loop = Mock()
        mock_loop.getaddrinfo = Mock(return_value=Mock())
        with (
            patch("asyncio.get_running_loop", return_value=mock_loop),
            patch("asyncio.wait_for", new_callable=AsyncMock) as mock_wait,
        ):
            mock_wait.return_value = [("family", "type", "proto", "canonname", ("addr", 80))]
            result = await engine.async_probe(target, timeout=5.0)

        assert result.success is True
        assert result.latency_ms is not None

    @pytest.mark.asyncio
    async def test_timeout(self) -> None:
        target = ProbeTarget(host="nonexistent.invalid", label="Test", method=ProbeMethod.DNS)
        engine = DNSProbeEngine()

        mock_loop = Mock()
        mock_loop.getaddrinfo = Mock(return_value=Mock())
        with (
            patch("asyncio.get_running_loop", return_value=mock_loop),
            patch("asyncio.wait_for", side_effect=TimeoutError),
        ):
            result = await engine.async_probe(target, timeout=1.0)

        assert result.success is False
        assert "timed out" in (result.error or "")

    @pytest.mark.asyncio
    async def test_resolution_failure(self) -> None:
        import socket

        target = ProbeTarget(host="nonexistent.invalid", label="Test", method=ProbeMethod.DNS)
        engine = DNSProbeEngine()

        mock_loop = Mock()
        mock_loop.getaddrinfo = Mock(return_value=Mock())
        with (
            patch("asyncio.get_running_loop", return_value=mock_loop),
            patch(
                "asyncio.wait_for",
                side_effect=socket.gaierror("Name or service not known"),
            ),
        ):
            result = await engine.async_probe(target, timeout=5.0)

        assert result.success is False
        assert "failed" in (result.error or "")
