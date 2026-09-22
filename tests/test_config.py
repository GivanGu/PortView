"""配置模块测试（v1.6.12 统一存储：全部落 SQLite）。"""

from app.config import (
    load_access_address,
    load_config,
    load_hidden_ports,
    normalize_access_address,
    save_access_address,
    save_hidden_ports,
)


class TestLoadConfig:
    async def test_empty(self, db):
        assert await load_config() == {}

    async def test_labels_by_port(self, db):
        await db.execute(
            "INSERT INTO port_labels (port, service_name, port_type, created_at, updated_at) "
            "VALUES (80, 'MyApp', 'host', 0, 0)"
        )
        await db.execute(
            "INSERT INTO port_labels (port, service_name, port_type, created_at, updated_at) "
            "VALUES (443, 'MyApp', 'host', 0, 0)"
        )
        await db.commit()
        config = await load_config()
        # 端口为主键：同一服务名可绑多端口
        assert config[80] == {"service_name": "MyApp", "port_type": "host"}
        assert config[443] == {"service_name": "MyApp", "port_type": "host"}


class TestAccessAddress:
    """v1.5.18 起访问地址只存主机部分（IP/域名），协议由打开时实时探测。"""

    def test_normalize_bare_ip(self):
        assert normalize_access_address("192.168.31.1") == "192.168.31.1"

    def test_normalize_bare_domain(self):
        assert normalize_access_address("nas.example.com") == "nas.example.com"

    def test_normalize_strips_http(self):
        assert normalize_access_address("http://192.168.1.100") == "192.168.1.100"

    def test_normalize_strips_https(self):
        assert normalize_access_address("https://nas.example.com") == "nas.example.com"

    def test_normalize_strips_custom_scheme(self):
        assert normalize_access_address("ftp://files.local") == "files.local"

    def test_normalize_strips_path(self):
        assert normalize_access_address("http://192.168.1.100:8081/") == "192.168.1.100"

    def test_normalize_bare_ip_with_port(self):
        """旧数据 / 手填「IP:端口」（无协议）→ 剥离端口，否则探测主机非法全部失败"""
        assert normalize_access_address("192.168.31.1:8081") == "192.168.31.1"

    def test_normalize_schemed_ip_with_port(self):
        assert normalize_access_address("http://192.168.31.1:8081") == "192.168.31.1"

    def test_normalize_empty(self):
        assert normalize_access_address("") == ""
        assert normalize_access_address("   ") == ""

    def test_normalize_strips_whitespace(self):
        assert normalize_access_address("  192.168.31.1  ") == "192.168.31.1"

    async def test_save_bare_ip_persists_bare(self, db):
        assert await save_access_address("192.168.31.1") is True
        assert await load_access_address() == "192.168.31.1"

    async def test_save_with_scheme_strips_scheme(self, db):
        assert await save_access_address("https://nas.example.com") is True
        assert await load_access_address() == "nas.example.com"

    async def test_save_empty_clears(self, db):
        await save_access_address("192.168.31.1")
        assert await save_access_address("") is True
        assert await load_access_address() == ""

    async def test_default_empty(self, db):
        assert await load_access_address() == ""


class TestHiddenPorts:
    async def test_save_and_load(self, db):
        assert await save_hidden_ports([80, 443, 8080]) is True
        assert await load_hidden_ports() == [80, 443, 8080]

    async def test_empty(self, db):
        assert await save_hidden_ports([]) is True
        assert await load_hidden_ports() == []

    async def test_fresh_db_empty(self, db):
        assert await load_hidden_ports() == []
