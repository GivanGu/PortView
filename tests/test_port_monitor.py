"""PortMonitor 核心逻辑测试。"""

from typing import Any

import pytest

from app.services.port_monitor import PortMonitor


def _make_monitor() -> PortMonitor:
    """创建不依赖 Docker 的 PortMonitor。"""
    monitor = PortMonitor.__new__(PortMonitor)
    monitor.docker_client = None
    monitor.container_cache = {}
    monitor.cache_timestamp = 0.0
    monitor.cache_ttl = 30
    monitor.default_ports = {22: "SSH", 80: "HTTP", 443: "HTTPS", 3306: "MySQL"}
    return monitor


class TestGetServiceName:
    def test_from_config(self):
        monitor = _make_monitor()
        config = {"my_service": {"port": 8080, "protocol": "TCP"}}
        assert monitor.get_service_name(8080, config) == "my_service"

    def test_from_default(self):
        monitor = _make_monitor()
        assert monitor.get_service_name(22, {}) == "SSH"
        assert monitor.get_service_name(80, {}) == "HTTP"

    def test_unknown(self):
        monitor = _make_monitor()
        assert monitor.get_service_name(12345, {}) == "未知服务"


class TestMergeUnknownAndGaps:
    def test_single_used_port(self):
        monitor = _make_monitor()
        cards = [
            {"port": 80, "type": "used", "source": "system", "protocol": "TCP",
             "service_name": "HTTP", "container": None},
        ]
        result = monitor._merge_unknown_and_gaps(cards, 1, 100)
        # 应该有: 80(used), gap(81-100)
        types = [c["type"] for c in result]
        assert "used" in types
        assert "gap" in types
        gap = [c for c in result if c["type"] == "gap"][0]
        assert gap["start_port"] == 81
        assert gap["end_port"] == 100

    def test_consecutive_unknown_merges(self):
        monitor = _make_monitor()
        cards = [
            {"port": 1000, "type": "used", "source": "system", "protocol": "TCP",
             "service_name": "未知服务", "container": None},
            {"port": 1001, "type": "used", "source": "system", "protocol": "TCP",
             "service_name": "未知服务", "container": None},
            {"port": 1002, "type": "used", "source": "system", "protocol": "TCP",
             "service_name": "未知服务", "container": None},
        ]
        result = monitor._merge_unknown_and_gaps(cards, 1, 2000)
        # 1000-1002 应合并为 unknown_range
        unknown = [c for c in result if c["type"] == "unknown_range"]
        assert len(unknown) == 1
        assert unknown[0]["start_port"] == 1000
        assert unknown[0]["end_port"] == 1002
        assert unknown[0]["port_count"] == 3

    def test_single_unknown_not_merged(self):
        monitor = _make_monitor()
        cards = [
            {"port": 1000, "type": "used", "source": "system", "protocol": "TCP",
             "service_name": "未知服务", "container": None},
        ]
        result = monitor._merge_unknown_and_gaps(cards, 1, 2000)
        # 单个未知服务不合并，保持 used
        assert any(c["type"] == "used" and c["port"] == 1000 for c in result)

    def test_gap_between_cards(self):
        monitor = _make_monitor()
        cards = [
            {"port": 80, "type": "used", "source": "system", "protocol": "TCP",
             "service_name": "HTTP", "container": None},
            {"port": 8080, "type": "used", "source": "system", "protocol": "TCP",
             "service_name": "App", "container": None},
        ]
        result = monitor._merge_unknown_and_gaps(cards, 1, 10000)
        # 应该有 gap 81-8079
        gaps = [c for c in result if c["type"] == "gap"]
        assert len(gaps) >= 1
        first_gap = gaps[0]
        assert first_gap["start_port"] == 81
        assert first_gap["end_port"] == 8079
        assert first_gap["available_count"] == 8079 - 81 + 1

    def test_empty_cards(self):
        monitor = _make_monitor()
        result = monitor._merge_unknown_and_gaps([], 1, 100)
        assert len(result) == 1
        assert result[0]["type"] == "gap"
        assert result[0]["start_port"] == 1
        assert result[0]["end_port"] == 100
        assert result[0]["available_count"] == 100


class TestCardHidden:
    def test_used_port_hidden(self):
        card = {"type": "used", "port": 80}
        assert PortMonitor._card_hidden(card, [80]) is True
        assert PortMonitor._card_hidden(card, [443]) is False

    def test_unknown_range_hidden(self):
        card = {"type": "unknown_range", "start_port": 1000, "end_port": 1005}
        assert PortMonitor._card_hidden(card, [1003]) is True
        assert PortMonitor._card_hidden(card, [2000]) is False

    def test_gap_never_hidden(self):
        card = {"type": "gap", "start_port": 1, "end_port": 100}
        assert PortMonitor._card_hidden(card, [50]) is False


class TestPortAnalysis:
    def test_no_docker_no_host(self):
        """无 Docker、无主机端口时，应返回全 gap。"""
        monitor = _make_monitor()
        config = {"ssh": {"port": 22, "protocol": "TCP"}}
        result = monitor.get_port_analysis(config, start_port=1, end_port=100)

        assert result["total_used"] == 0
        assert result["total_available"] == 100
        assert len(result["port_cards"]) == 1
        assert result["port_cards"][0]["type"] == "gap"

    def test_protocol_filter(self):
        monitor = _make_monitor()
        config = {}
        result_tcp = monitor.get_port_analysis(config, start_port=1, end_port=100, protocol_filter="TCP")
        result_udp = monitor.get_port_analysis(config, start_port=1, end_port=100, protocol_filter="UDP")
        assert result_tcp["protocol_filter"] == "TCP"
        assert result_udp["protocol_filter"] == "UDP"

    def test_hidden_ports_filter(self):
        monitor = _make_monitor()
        config = {}
        # 模拟：手动构造一个有已用端口的场景
        # 由于没有 Docker 和主机端口，用 config 里的端口来测试
        config_with_port = {"test": {"port": 80, "protocol": "TCP"}}
        result = monitor.get_port_analysis(
            config_with_port, start_port=1, end_port=200, hidden_ports=[80]
        )
        # 80 被隐藏了，但因为没有实际监听，total_used 可能还是 0
        # 关键是 hidden_ports 字段正确
        assert result["hidden_ports"] == [80]
