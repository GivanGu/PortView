"""测试基础。"""

import os

# 确保测试使用临时配置目录
os.environ["PORTVIEW_CONFIG_DIR"] = "/tmp/portview_test_config"
