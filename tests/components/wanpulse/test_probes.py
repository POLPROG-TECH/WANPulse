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

    """GIVEN the probe method "tcp"."""
    def test_tcp_engine(self) -> None:
        """WHEN requesting the probe engine"""
        engine = get_probe_engine("tcp")

        """THEN a TCPProbeEngine is returned"""
        assert isinstance(engine, TCPProbeEngine)

    """GIVEN the probe method "http"."""
    def test_http_engine(self) -> None:
        """WHEN requesting the probe engine"""
        engine = get_probe_engine("http")

        """THEN an HTTPProbeEngine is returned"""
        assert isinstance(engine, HTTPProbeEngine)

    """GIVEN the probe method "dns"."""
    def test_dns_engine(self) -> None:
        """WHEN requesting the probe engine"""
        engine = get_probe_engine("dns")

        """THEN a DNSProbeEngine is returned"""
        assert isinstance(engine, DNSProbeEngine)

    """GIVEN an unsupported probe method"""
    def test_unknown_engine(self) -> None:
        """WHEN unknown engine is evaluated"""

        """THEN a ValueError is raised"""
        with pytest.raises(ValueError, match="Unknown probe method"):
            get_probe_engine("icmp")


class TestTCPProbeEngine:
    """Tests for the TCP probe engine."""

    """GIVEN a TCP target on port 443 and a mocked successful connection"""
    @pytest.mark.asyncio
    async def test_successful_connect(self) -> None:
        target = ProbeTarget(host="1.1.1.1", label="Test", method=ProbeMethod.TCP, port=443)
        engine = TCPProbeEngine()

        mock_writer = MagicMock()
        mock_writer.close = MagicMock()
        mock_writer.wait_closed = AsyncMock()

        """WHEN probing the target"""
        with (
            patch("asyncio.open_connection", return_value=Mock()),
            patch("asyncio.wait_for", new_callable=AsyncMock) as mock_wait,
        ):
            mock_wait.return_value = (MagicMock(), mock_writer)
            result = await engine.async_probe(target, timeout=5.0)

        """THEN the probe succeeds with a non-negative latency"""
        assert result.success is True
        assert result.latency_ms is not None
        assert result.latency_ms >= 0

    """GIVEN a TCP target on port 443 and a connection that times out"""
    @pytest.mark.asyncio
    async def test_timeout(self) -> None:
        target = ProbeTarget(host="1.1.1.1", label="Test", method=ProbeMethod.TCP, port=443)
        engine = TCPProbeEngine()

        """WHEN probing the target"""
        with (
            patch("asyncio.open_connection", return_value=Mock()),
            patch("asyncio.wait_for", side_effect=TimeoutError),
        ):
            result = await engine.async_probe(target, timeout=1.0)

        """THEN the probe fails with a timeout error"""
        assert result.success is False
        assert "timed out" in (result.error or "")

    """GIVEN a TCP target on port 443 and a refused connection"""
    @pytest.mark.asyncio
    async def test_connection_refused(self) -> None:
        target = ProbeTarget(host="1.1.1.1", label="Test", method=ProbeMethod.TCP, port=443)
        engine = TCPProbeEngine()

        """WHEN probing the target"""
        with (
            patch("asyncio.open_connection", return_value=Mock()),
            patch("asyncio.wait_for", side_effect=OSError("Connection refused")),
        ):
            result = await engine.async_probe(target, timeout=5.0)

        """THEN the probe fails with a connection refused error"""
        assert result.success is False
        assert "Connection refused" in (result.error or "")

    """GIVEN a TCP target with no explicit port"""
    @pytest.mark.asyncio
    async def test_default_port(self) -> None:
        target = ProbeTarget(host="1.1.1.1", label="Test", method=ProbeMethod.TCP)
        engine = TCPProbeEngine()

        mock_writer = MagicMock()
        mock_writer.close = MagicMock()
        mock_writer.wait_closed = AsyncMock()

        """WHEN probing the target"""
        with (
            patch("asyncio.open_connection", return_value=Mock()),
            patch("asyncio.wait_for", new_callable=AsyncMock) as mock_wait,
        ):
            mock_wait.return_value = (MagicMock(), mock_writer)
            result = await engine.async_probe(target, timeout=5.0)

        """THEN the probe succeeds using the default port"""
        assert result.success is True


class TestHTTPProbeEngine:
    """Tests for the HTTP probe engine."""

    """GIVEN an HTTP target and a mocked session returning status 200"""
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

        """WHEN probing the target"""
        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = await engine.async_probe(target, timeout=5.0)

        """THEN the probe succeeds with a recorded latency"""
        assert result.success is True
        assert result.latency_ms is not None

    """GIVEN an HTTP target and a session that times out"""
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

        """WHEN probing the target"""
        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = await engine.async_probe(target, timeout=1.0)

        """THEN the probe fails with a timeout error"""
        assert result.success is False
        assert "timed out" in (result.error or "")

    """GIVEN an HTTP target without a URL scheme on port 443"""
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

        """WHEN probing the target"""
        with patch("aiohttp.ClientSession", return_value=mock_session):
            result = await engine.async_probe(target, timeout=5.0)

        """THEN the probe succeeds despite the missing scheme"""
        assert result.success is True


class TestDNSProbeEngine:
    """Tests for the DNS probe engine."""

    """GIVEN a DNS target for www.google.com and a mocked successful resolution"""
    @pytest.mark.asyncio
    async def test_successful_resolve(self) -> None:
        target = ProbeTarget(host="www.google.com", label="Test", method=ProbeMethod.DNS)
        engine = DNSProbeEngine()

        mock_loop = Mock()
        mock_loop.getaddrinfo = Mock(return_value=Mock())

        """WHEN probing the target"""
        with (
            patch("asyncio.get_running_loop", return_value=mock_loop),
            patch("asyncio.wait_for", new_callable=AsyncMock) as mock_wait,
        ):
            mock_wait.return_value = [("family", "type", "proto", "canonname", ("addr", 80))]
            result = await engine.async_probe(target, timeout=5.0)

        """THEN the probe succeeds with a recorded latency"""
        assert result.success is True
        assert result.latency_ms is not None

    """GIVEN a DNS target and a lookup that times out"""
    @pytest.mark.asyncio
    async def test_timeout(self) -> None:
        target = ProbeTarget(host="nonexistent.invalid", label="Test", method=ProbeMethod.DNS)
        engine = DNSProbeEngine()

        mock_loop = Mock()
        mock_loop.getaddrinfo = Mock(return_value=Mock())

        """WHEN probing the target"""
        with (
            patch("asyncio.get_running_loop", return_value=mock_loop),
            patch("asyncio.wait_for", side_effect=TimeoutError),
        ):
            result = await engine.async_probe(target, timeout=1.0)

        """THEN the probe fails with a timeout error"""
        assert result.success is False
        assert "timed out" in (result.error or "")

    """GIVEN a DNS target for a nonexistent domain and a gaierror on resolution"""
    @pytest.mark.asyncio
    async def test_resolution_failure(self) -> None:
        import socket

        target = ProbeTarget(host="nonexistent.invalid", label="Test", method=ProbeMethod.DNS)
        engine = DNSProbeEngine()

        mock_loop = Mock()
        mock_loop.getaddrinfo = Mock(return_value=Mock())

        """WHEN probing the target"""
        with (
            patch("asyncio.get_running_loop", return_value=mock_loop),
            patch(
                "asyncio.wait_for",
                side_effect=socket.gaierror("Name or service not known"),
            ),
        ):
            result = await engine.async_probe(target, timeout=5.0)

        """THEN the probe fails with a resolution failure error"""
        assert result.success is False
        assert "failed" in (result.error or "")
