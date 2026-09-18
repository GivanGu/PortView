"""全局测试夹具：隔离 SQLite 数据库与配置目录。

``app.services.db`` 在 import 时读取 ``PORTVIEW_DB`` 决定 DB 路径，
``app.config`` 在 import 时读取 ``PORTVIEW_CONFIG_DIR`` 决定配置目录。
本文件由 pytest 在任何测试模块之前加载，因此在模块级设置环境变量，
保证所有测试（含单文件运行）都使用临时路径，
不会触碰仓库内真实的 ``.data/portview.db`` 或 ``/app/config``。

注意：test_api.py / test_scheme_probe.py 模块级也会设置
``PORTVIEW_CONFIG_DIR``，且发生在 ``app`` 首次 import 之前，
因此全量运行时以它们的值为准（保持原有行为）。

每个测试前删除临时 DB 文件（含 WAL/SHM），保证各用例初始状态干净。
"""

from __future__ import annotations

import os
import tempfile

import pytest

_TEST_DIR = tempfile.mkdtemp(prefix="portview_test_")
_TEST_DB = os.path.join(_TEST_DIR, "portview.db")
_TEST_CONFIG_DIR = os.path.join(_TEST_DIR, "config")

os.environ["PORTVIEW_DB"] = _TEST_DB
os.environ["PORTVIEW_CONFIG_DIR"] = _TEST_CONFIG_DIR
# 不让 env 层强制开启 auth，由测试自行控制
os.environ.pop("PORTVIEW_REQUIRE_AUTH", None)


@pytest.fixture(autouse=True)
def _fresh_db():
    """每个测试前删除临时 DB（及 WAL/SHM），保证干净初始状态。"""
    for suffix in ("", "-wal", "-shm"):
        path = _TEST_DB + suffix
        if os.path.exists(path):
            os.remove(path)
    yield
