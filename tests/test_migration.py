"""v1.6.12 统一存储迁移测试：旧库搬家 + JSON 入库 + 幂等。"""

from __future__ import annotations

import json
import os
import sqlite3

import pytest

from app.config import load_access_address, load_config, load_hidden_ports
from app.services import migrate


def _make_db(path: str, table: str = "users", rows: list[tuple] | None = None) -> None:
    conn = sqlite3.connect(path)
    try:
        conn.execute(f"CREATE TABLE {table} (id INTEGER, name TEXT)")
        for row in rows or []:
            conn.execute(f"INSERT INTO {table} VALUES (?, ?)", row)
        conn.commit()
    finally:
        conn.close()


class TestRelocateDb:
    def test_no_old_db_skips(self, tmp_path):
        old = str(tmp_path / "old.db")
        new = str(tmp_path / "new.db")
        assert migrate.relocate_db(old, new) is False
        assert not os.path.exists(new)

    def test_new_exists_skips(self, tmp_path):
        old = tmp_path / "old.db"
        new = tmp_path / "new.db"
        _make_db(str(old))
        _make_db(str(new))
        assert migrate.relocate_db(str(old), str(new)) is False
        # 旧库不动
        assert os.path.exists(str(old))

    def test_relocate_copies_and_removes_old(self, tmp_path):
        old = tmp_path / "old.db"
        new = tmp_path / "new.db"
        _make_db(str(old), rows=[(1, "admin")])
        assert migrate.relocate_db(str(old), str(new)) is True
        assert os.path.exists(str(new))
        assert not os.path.exists(str(old))
        # 数据完整
        conn = sqlite3.connect(str(new))
        try:
            rows = conn.execute("SELECT id, name FROM users").fetchall()
        finally:
            conn.close()
        assert rows == [(1, "admin")]

    def test_replay_wal(self, tmp_path):
        """模拟崩溃（SIGKILL）留下未 checkpoint 的 WAL，搬家后新库应重放完整。"""
        import subprocess
        import sys

        old = tmp_path / "old.db"
        new = tmp_path / "new.db"
        # 子进程以 WAL 模式写入后自杀（SIGKILL），模拟崩溃：WAL 含未 checkpoint 数据
        code = (
            "import sqlite3, os, signal\n"
            f"conn = sqlite3.connect({str(old)!r})\n"
            'conn.execute("PRAGMA journal_mode=WAL")\n'
            'conn.execute("CREATE TABLE t (x INTEGER)")\n'
            'conn.execute("INSERT INTO t VALUES (42)")\n'
            'conn.execute("INSERT INTO t VALUES (43)")\n'
            "conn.commit()\n"
            "os.kill(os.getpid(), signal.SIGKILL)\n"
        )
        subprocess.run([sys.executable, "-c", code], check=False)
        assert os.path.exists(str(old) + "-wal")
        assert migrate.relocate_db(str(old), str(new)) is True
        conn2 = sqlite3.connect(str(new))
        try:
            rows = conn2.execute("SELECT x FROM t ORDER BY x").fetchall()
        finally:
            conn2.close()
        assert rows == [(42,), (43,)]

    def test_corrupt_old_db_raises_and_keeps_old(self, tmp_path):
        old = tmp_path / "old.db"
        new = tmp_path / "new.db"
        old.write_bytes(b"not a sqlite database" * 10)
        with pytest.raises(RuntimeError):
            migrate.relocate_db(str(old), str(new))
        assert os.path.exists(str(old))
        assert not os.path.exists(str(new))

    def test_cleans_stale_tmp(self, tmp_path):
        """上次崩溃遗留的 .tmp 应被清理。"""
        old = str(tmp_path / "old.db")
        new = str(tmp_path / "new.db")
        (tmp_path / "new.db.tmp").write_bytes(b"stale")
        assert migrate.relocate_db(old, new) is False
        assert not os.path.exists(str(tmp_path / "new.db.tmp"))


class TestParseLegacyEntry:
    def test_new_format(self):
        assert migrate._parse_legacy_entry("MyApp:host", "80:tcp") == ("MyApp", "host", 80)
        assert migrate._parse_legacy_entry("PortView:docker", "7575:tcp") == (
            "PortView",
            "docker",
            7575,
        )

    def test_old_format(self):
        assert migrate._parse_legacy_entry("ssh", "22:tcp") == ("ssh", "host", 22)

    def test_int_value(self):
        assert migrate._parse_legacy_entry("ftp", 21) == ("ftp", "host", 21)

    def test_invalid(self):
        assert migrate._parse_legacy_entry("bad", "noport:tcp")[2] is None
        assert migrate._parse_legacy_entry("bad", 99999)[2] is None
        assert migrate._parse_legacy_entry("bad", "0:tcp")[2] is None
        assert migrate._parse_legacy_entry("bad", None)[2] is None


class TestMigrateJsonFiles:
    async def test_migrate_config_and_hidden(self, tmp_path, db):
        (tmp_path / "config.json").write_text(
            json.dumps(
                {
                    "MyApp:host": "80:tcp",
                    "MyApp-HTTPS:host": "443:tcp",
                    "旧格式服务": "3306:tcp",
                    "ftp": 21,
                    "__access_address__": "http://192.168.31.1:8081",
                },
                ensure_ascii=False,
            )
        )
        (tmp_path / "hidden_ports.json").write_text(json.dumps([9999, 8080]))

        await migrate.migrate_json_files(str(tmp_path), db)

        config = await load_config()
        assert config[80] == {"service_name": "MyApp", "port_type": "host"}
        assert config[443] == {"service_name": "MyApp-HTTPS", "port_type": "host"}
        assert config[3306] == {"service_name": "旧格式服务", "port_type": "host"}
        assert config[21] == {"service_name": "ftp", "port_type": "host"}
        assert await load_access_address() == "192.168.31.1"
        assert await load_hidden_ports() == [8080, 9999]
        # 源文件已删除
        assert not os.path.exists(tmp_path / "config.json")
        assert not os.path.exists(tmp_path / "hidden_ports.json")

    async def test_idempotent(self, tmp_path, db):
        (tmp_path / "config.json").write_text(json.dumps({"MyApp:host": "80:tcp"}))
        await migrate.migrate_json_files(str(tmp_path), db)
        # 第二次：源文件已删 → 直接跳过，不报错
        await migrate.migrate_json_files(str(tmp_path), db)
        config = await load_config()
        assert config[80]["service_name"] == "MyApp"

    async def test_conflict_last_wins(self, tmp_path, db):
        """旧格式两个名字指向同一端口 → 保留后者（新模型端口唯一，必然收敛）。"""
        (tmp_path / "config.json").write_text(json.dumps({"A:host": "80:tcp", "B:host": "80:tcp"}))
        await migrate.migrate_json_files(str(tmp_path), db)
        config = await load_config()
        assert config[80]["service_name"] == "B"

    async def test_missing_files_noop(self, tmp_path, db):
        await migrate.migrate_json_files(str(tmp_path), db)
        assert await load_config() == {}
        assert await load_hidden_ports() == []

    async def test_hidden_only(self, tmp_path, db):
        (tmp_path / "hidden_ports.json").write_text(json.dumps([1234]))
        await migrate.migrate_json_files(str(tmp_path), db)
        assert await load_hidden_ports() == [1234]
        assert not os.path.exists(tmp_path / "hidden_ports.json")

    async def test_invalid_hidden_entries_skipped(self, tmp_path, db):
        (tmp_path / "hidden_ports.json").write_text(json.dumps([1234, 0, 70000, "bad"]))
        await migrate.migrate_json_files(str(tmp_path), db)
        assert await load_hidden_ports() == [1234]
