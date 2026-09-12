"""配置模块测试。"""

import json
import os
import shutil

import pytest

from app.config import (
    CONFIG_DIR,
    CONFIG_FILE,
    HIDDEN_PORTS_FILE,
    init_config,
    load_access_address,
    load_config,
    load_hidden_ports,
    load_raw_config,
    normalize_access_address,
    save_access_address,
    save_config,
    save_hidden_ports,
    save_raw_config,
)


@pytest.fixture(autouse=True)
def clean_config_dir():
    """每个测试前清理配置目录。"""
    if os.path.exists(CONFIG_DIR):
        shutil.rmtree(CONFIG_DIR)
    os.makedirs(CONFIG_DIR, exist_ok=True)
    yield
    if os.path.exists(CONFIG_DIR):
        shutil.rmtree(CONFIG_DIR)


class TestInitConfig:
    def test_creates_config_dir(self):
        init_config()
        assert os.path.isdir(CONFIG_DIR)

    def test_creates_config_file(self):
        init_config()
        assert os.path.isfile(CONFIG_FILE)

    def test_creates_hidden_ports_file(self):
        init_config()
        assert os.path.isfile(HIDDEN_PORTS_FILE)

    def test_idempotent(self):
        init_config()
        init_config()  # 第二次不应报错
        assert os.path.isfile(CONFIG_FILE)


class TestLoadConfig:
    def test_new_format(self):
        """新格式：服务名:docker/host -> 端口:协议"""
        raw = {
            "远程登录:host": "22:tcp",
            "MySQL数据库:host": "3306:tcp",
            "PortView:docker": "7575:tcp",
        }
        with open(CONFIG_FILE, "w") as f:
            json.dump(raw, f)

        config = load_config()
        assert "远程登录" in config
        assert config["远程登录"]["port"] == 22
        assert config["远程登录"]["protocol"] == "TCP"
        assert config["远程登录"]["service_type"] == "host"

        assert "MySQL数据库" in config
        assert config["MySQL数据库"]["port"] == 3306

        assert "PortView" in config
        assert config["PortView"]["port"] == 7575
        assert config["PortView"]["service_type"] == "docker"

    def test_old_format(self):
        """旧格式：服务名 -> 端口:协议"""
        raw = {
            "ssh": "22:tcp",
            "http": "80:tcp",
        }
        with open(CONFIG_FILE, "w") as f:
            json.dump(raw, f)

        config = load_config()
        assert "ssh" in config
        assert config["ssh"]["port"] == 22
        assert config["ssh"]["protocol"] == "TCP"

    def test_int_value(self):
        """纯整数端口值"""
        raw = {"ftp": 21}
        with open(CONFIG_FILE, "w") as f:
            json.dump(raw, f)

        config = load_config()
        assert config["ftp"]["port"] == 21
        assert config["ftp"]["protocol"] == "TCP"

    def test_udp_protocol(self):
        raw = {"dns": "53:udp"}
        with open(CONFIG_FILE, "w") as f:
            json.dump(raw, f)

        config = load_config()
        assert config["dns"]["protocol"] == "UDP"

    def test_missing_file_returns_fallback(self):
        config = load_config()
        assert "ssh" in config
        assert config["ssh"]["port"] == 22


class TestSaveConfig:
    def test_save_and_load_roundtrip(self):
        config = {
            "ssh": {"port": 22, "protocol": "TCP", "service_type": "host"},
            "app": {"port": 8080, "protocol": "TCP", "service_type": "docker"},
        }
        assert save_config(config) is True

        raw = load_raw_config()
        assert raw["ssh:host"] == "22:tcp"
        assert raw["app:docker"] == "8080:tcp"

    def test_save_raw(self):
        raw = {"test:host": "1234:tcp"}
        assert save_raw_config(raw) is True

        loaded = load_raw_config()
        assert loaded == raw


class TestAccessAddress:
    def test_normalize_bare_ip(self):
        assert normalize_access_address("192.168.31.1") == "http://192.168.31.1"

    def test_normalize_bare_domain(self):
        assert normalize_access_address("nas.example.com") == "http://nas.example.com"

    def test_normalize_keeps_http(self):
        assert normalize_access_address("http://192.168.1.100") == "http://192.168.1.100"

    def test_normalize_keeps_https(self):
        assert normalize_access_address("https://nas.example.com") == "https://nas.example.com"

    def test_normalize_keeps_custom_scheme(self):
        assert normalize_access_address("ftp://files.local") == "ftp://files.local"

    def test_normalize_empty(self):
        assert normalize_access_address("") == ""
        assert normalize_access_address("   ") == ""

    def test_normalize_strips_whitespace(self):
        assert normalize_access_address("  192.168.31.1  ") == "http://192.168.31.1"

    def test_save_bare_ip_persists_with_scheme(self):
        assert save_access_address("192.168.31.1") is True
        assert load_raw_config()["__access_address__"] == "http://192.168.31.1"
        assert load_access_address() == "http://192.168.31.1"

    def test_save_with_scheme_unchanged(self):
        assert save_access_address("https://nas.example.com") is True
        assert load_access_address() == "https://nas.example.com"

    def test_save_empty_clears(self):
        save_access_address("192.168.31.1")
        assert save_access_address("") is True
        assert load_access_address() == ""
        assert "__access_address__" not in load_raw_config()

    def test_load_normalizes_legacy_bare_value(self):
        """旧版本可能已落盘裸 IP，读取时应自动补 http://。"""
        with open(CONFIG_FILE, "w") as f:
            json.dump({"__access_address__": "10.0.0.5"}, f)
        assert load_access_address() == "http://10.0.0.5"


class TestHiddenPorts:
    def test_save_and_load(self):
        assert save_hidden_ports([80, 443, 8080]) is True
        assert load_hidden_ports() == [80, 443, 8080]

    def test_empty(self):
        assert save_hidden_ports([]) is True
        assert load_hidden_ports() == []

    def test_missing_file(self):
        assert load_hidden_ports() == []
