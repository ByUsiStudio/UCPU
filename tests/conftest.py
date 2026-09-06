"""pytest 共享夹具与本地临时目录 (workspace 内, 兼容沙箱环境)。"""

import os
import shutil
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

# 本地临时工作目录 (随会话清理); CI/无沙箱环境下同样安全
TMP_ROOT = os.path.join(ROOT, '.pytest_tmp')


@pytest.fixture(scope='session', autouse=True)
def _clean_tmp():
    os.makedirs(TMP_ROOT, exist_ok=True)
    yield
    shutil.rmtree(TMP_ROOT, ignore_errors=True)


@pytest.fixture()
def workdir():
    """返回一个唯一的本地工作目录 (test 级, 随会话清理)。"""
    import uuid
    d = os.path.join(TMP_ROOT, uuid.uuid4().hex)
    os.makedirs(d, exist_ok=True)
    return d
