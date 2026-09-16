"""``common.transform_runner.apply_transform`` 单元测试。"""

from common.transform_runner import apply_transform


# ---------------------------------------------------------------------------
# 成功路径
# ---------------------------------------------------------------------------
def test_empty_script_returns_data():
    """空 script_src 应直接返回原数据。"""
    ok, data, err = apply_transform("", [1, 2, 3], {})
    assert ok is True
    assert data == [1, 2, 3]
    assert err is None


def test_none_script_returns_data():
    """None script_src 应直接返回原数据。"""
    ok, data, err = apply_transform(None, {"a": 1}, {})
    assert ok is True
    assert data == {"a": 1}
    assert err is None


def test_normal_transform_filter():
    """正常转换: 过滤 x > 0 的行。"""
    script = "def transform(data, config): return [row for row in data if row.get('x') > 0]"
    ok, data, err = apply_transform(script, [{"x": 1}, {"x": -1}], {})
    assert ok is True
    assert data == [{"x": 1}]
    assert err is None


def test_transform_field_rename():
    """字段重命名: 仅保留 id 字段。"""
    script = "def transform(data, config): return [{'id': r['id']} for r in data]"
    ok, data, err = apply_transform(
        script, [{"id": 1, "name": "a"}, {"id": 2, "name": "b"}], {}
    )
    assert ok is True
    assert data == [{"id": 1}, {"id": 2}]
    assert err is None


def test_transform_aggregation():
    """聚合: 求 v 字段之和。"""
    script = "def transform(data, config): return {'total': sum(r['v'] for r in data)}"
    ok, data, err = apply_transform(script, [{"v": 1}, {"v": 2}, {"v": 3}], {})
    assert ok is True
    assert data == {"total": 6}
    assert err is None


# ---------------------------------------------------------------------------
# 失败路径
# ---------------------------------------------------------------------------
def test_syntax_error():
    """语法错误应返回 syntax_error。"""
    ok, data, err = apply_transform("def transform(", [], {})
    assert ok is False
    assert isinstance(data, str)
    assert err == "syntax_error"


def test_missing_transform():
    """未定义 transform 应返回 missing_transform。"""
    ok, data, err = apply_transform("x = 1", [], {})
    assert ok is False
    assert isinstance(data, str)
    assert err == "missing_transform"


def test_blocked_call_open():
    """危险调用 open() 应返回 blocked_call, 不能真的打开文件。"""
    script = "def transform(data, config): open('/etc/passwd'); return data"
    ok, data, err = apply_transform(script, [], {})
    assert ok is False
    assert isinstance(data, str)
    assert err == "blocked_call"


def test_runtime_error():
    """运行时错误 (KeyError) 应返回 runtime_error。"""
    script = "def transform(data, config): return data['missing_key']"
    ok, data, err = apply_transform(script, {}, {})
    assert ok is False
    assert isinstance(data, str)
    assert err == "runtime_error"


def test_invalid_signature():
    """transform 不可调用应返回 invalid_signature。"""
    ok, data, err = apply_transform("transform = 42", [], {})
    assert ok is False
    assert isinstance(data, str)
    assert err == "invalid_signature"
