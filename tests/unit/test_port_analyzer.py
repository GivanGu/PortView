"""PortAnalyzer 单元测试：卡片生成、合并、隐藏、统计。"""
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


class TestAnalyze_NoDocker_NoHost:
    def test_returns_full_gap(self):
        analyzer = _make_analyzer()
        result = analyzer.analyze({}, start_port=1, end_port=100)
        assert result["total_used"] == 0
        assert result["total_available"] == 100
        assert len(result["port_cards"]) == 1
        assert result["port_cards"][0]["type"] == "gap"


class TestProtocolFilter:
    def test_tcp_filter(self):
        analyzer = _make_analyzer()
        result = analyzer.analyze({}, start_port=1, end_port=100, protocol_filter="TCP")
        assert result["protocol_filter"] == "TCP"

    def test_udp_filter(self):
        analyzer = _make_analyzer()
        result = analyzer.analyze({}, start_port=1, end_port=100, protocol_filter="UDP")
        assert result["protocol_filter"] == "UDP"


class TestHiddenPorts:
    def test_hidden_reflected(self):
        analyzer = _make_analyzer()
        result = analyzer.analyze({}, start_port=1, end_port=200, hidden_ports=[80])
        assert result["hidden_ports"] == [80]


class TestMerge:
    def test_single_used_port_has_gap(self):
        analyzer = _make_analyzer()
        cards = [
            {"port": 80, "type": "used", "source": "system", "protocol": "TCP",
             "service_name": "HTTP", "container": None, "protocol": "TCP"},
        ]
        result = analyzer._merge_unknown_and_gaps(cards, 1, 100)
        assert any(c["type"] == "used" and c["port"] == 80 for c in result)
        assert any(c["type"] == "gap" and c["start_port"] == 81 for c in result)

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

    def test_empty_cards(self):
        analyzer = _make_analyzer()
        result = analyzer._merge_unknown_and_gaps([], 1, 100)
        assert len(result) == 1
        assert result[0]["type"] == "gap"
        assert result[0]["start_port"] == 1
