"""PortAnalyzer / DockerScanner / HostScanner 核心逻辑测试。

该文件原测试 PortMonitor，现已拆分到：
  - tests/unit/test_port_analyzer.py
  - tests/unit/test_docker_scanner.py
  - tests/unit/test_host_scanner.py
保留本文件用于向后兼容的集成测试。
"""
from __future__ import annotations

from app.services.docker_scanner import DockerScanner
from app.services.host_scanner import HostScanner
from app.services.port_analyzer import PortAnalyzer


def _make_analyzer() -> PortAnalyzer:
    """创建不依赖 Docker 的 PortAnalyzer。"""
    docker_scanner = DockerScanner.__new__(DockerScanner)
    docker_scanner.docker_client = None
    docker_scanner._host_container_cache = {}
    docker_scanner._cache_timestamp = 0.0
    docker_scanner._cache_ttl = 30

    host_scanner = HostScanner(docker_scanner)
    host_scanner.default_ports = {22: "SSH", 80: "HTTP", 443: "HTTPS", 3306: "MySQL"}

    return PortAnalyzer(docker_scanner, host_scanner)


class TestGetServiceName:
    def test_from_config(self):
        analyzer = _make_analyzer()
        config = {"my_service": {"port": 8080, "protocol": "TCP"}}
        assert analyzer.host_scanner.get_service_name(8080, config) == "my_service"

    def test_from_default(self):
        analyzer = _make_analyzer()
        assert analyzer.host_scanner.get_service_name(22, {}) == "SSH"
        assert analyzer.host_scanner.get_service_name(80, {}) == "HTTP"

    def test_unknown(self):
        analyzer = _make_analyzer()
        assert analyzer.host_scanner.get_service_name(12345, {}) == "未知服务"


class TestMergeUnknownAndGaps:
    def test_single_used_port(self):
        analyzer = _make_analyzer()
        cards = [
            {"port": 80, "type": "used", "source": "system", "protocol": "TCP",
             "service_name": "HTTP", "container": None},
        ]
        result = analyzer._merge_unknown_and_gaps(cards, 1, 100)
        types = [c["type"] for c in result]
        assert "used" in types
        assert "gap" in types
        gap = [c for c in result if c["type"] == "gap"][0]
        assert gap["start_port"] == 81
        assert gap["end_port"] == 100

    def test_consecutive_unknown_merges(self):
        analyzer = _make_analyzer()
        cards = [
            {"port": 1000, "type": "used", "source": "system", "protocol": "TCP",
             "service_name": "未知服务", "container": None},
            {"port": 1001, "type": "used", "source": "system", "protocol": "TCP",
             "service_name": "未知服务", "container": None},
            {"port": 1002, "type": "used", "source": "system", "protocol": "TCP",
             "service_name": "未知服务", "container": None},
        ]
        result = analyzer._merge_unknown_and_gaps(cards, 1, 2000)
        unknown = [c for c in result if c["type"] == "unknown_range"]
        assert len(unknown) == 1
        assert unknown[0]["start_port"] == 1000
        assert unknown[0]["end_port"] == 1002
        assert unknown[0]["port_count"] == 3

    def test_single_unknown_not_merged(self):
        analyzer = _make_analyzer()
        cards = [
            {"port": 1000, "type": "used", "source": "system", "protocol": "TCP",
             "service_name": "未知服务", "container": None},
        ]
        result = analyzer._merge_unknown_and_gaps(cards, 1, 2000)
        assert any(c["type"] == "used" and c["port"] == 1000 for c in result)

    def test_gap_between_cards(self):
        analyzer = _make_analyzer()
        cards = [
            {"port": 80, "type": "used", "source": "system", "protocol": "TCP",
             "service_name": "HTTP", "container": None},
            {"port": 8080, "type": "used", "source": "system", "protocol": "TCP",
             "service_name": "App", "container": None},
        ]
        result = analyzer._merge_unknown_and_gaps(cards, 1, 10000)
        gaps = [c for c in result if c["type"] == "gap"]
        assert len(gaps) >= 1
        first_gap = gaps[0]
        assert first_gap["start_port"] == 81
        assert first_gap["end_port"] == 8079
        assert first_gap["available_count"] == 8079 - 81 + 1

    def test_empty_cards(self):
        analyzer = _make_analyzer()
        result = analyzer._merge_unknown_and_gaps([], 1, 100)
        assert len(result) == 1
        assert result[0]["type"] == "gap"
        assert result[0]["start_port"] == 1
        assert result[0]["end_port"] == 100
        assert result[0]["available_count"] == 100


class TestCardHidden:
    def test_used_port_hidden(self):
        card = {"type": "used", "port": 80}
        assert PortAnalyzer._card_hidden(card, [80]) is True
        assert PortAnalyzer._card_hidden(card, [443]) is False

    def test_unknown_range_hidden(self):
        card = {"type": "unknown_range", "start_port": 1000, "end_port": 1005}
        assert PortAnalyzer._card_hidden(card, [1003]) is True
        assert PortAnalyzer._card_hidden(card, [2000]) is False

    def test_gap_never_hidden(self):
        card = {"type": "gap", "start_port": 1, "end_port": 100}
        assert PortAnalyzer._card_hidden(card, [50]) is False


class TestPortAnalysis:
    def test_no_docker_no_host(self):
        """无 Docker、无主机端口时，应返回全 gap。"""
        analyzer = _make_analyzer()
        config = {"ssh": {"port": 22, "protocol": "TCP"}}
        result = analyzer.analyze(config, start_port=1, end_port=100)

        assert result["total_used"] == 0
        assert result["total_available"] == 100
        assert len(result["port_cards"]) == 1
        assert result["port_cards"][0]["type"] == "gap"

    def test_protocol_filter(self):
        analyzer = _make_analyzer()
        config = {}
        result_tcp = analyzer.analyze(config, start_port=1, end_port=100, protocol_filter="TCP")
        result_udp = analyzer.analyze(config, start_port=1, end_port=100, protocol_filter="UDP")
        assert result_tcp["protocol_filter"] == "TCP"
        assert result_udp["protocol_filter"] == "UDP"

    def test_hidden_ports_filter(self):
        analyzer = _make_analyzer()
        config = {}
        config_with_port = {"test": {"port": 80, "protocol": "TCP"}}
        result = analyzer.analyze(
            config_with_port, start_port=1, end_port=200, hidden_ports=[80]
        )
        assert result["hidden_ports"] == [80]
