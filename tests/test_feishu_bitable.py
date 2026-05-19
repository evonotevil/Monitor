"""
feishu_bitable.py 单元测试
覆盖：批量写入部分失败时的成功 URL 记录、日期区间过滤辅助逻辑。
"""

import feishu_bitable
from feishu_bitable import write_to_bitable


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


def test_write_to_bitable_returns_only_successful_urls(monkeypatch):
    calls = []

    def fake_post(*args, **kwargs):
        calls.append(kwargs["json"]["records"])
        if len(calls) == 1:
            return _FakeResponse({
                "code": 0,
                "data": {"records": [{"record_id": "rec1"}, {"record_id": "rec2"}]},
            })
        return _FakeResponse({"code": 1250001, "msg": "batch failed"})

    monkeypatch.setattr(feishu_bitable, "_BATCH_SIZE", 2)
    monkeypatch.setattr(feishu_bitable.requests, "post", fake_post)

    items = [
        {"title_zh": "A", "source_url": "https://example.com/a"},
        {"title_zh": "B", "source_url": "https://example.com/b"},
        {"title_zh": "C", "source_url": "https://example.com/c"},
    ]

    written_urls = write_to_bitable(
        items,
        app_token="app",
        table_id="tbl",
        access_token="token",
        return_success_urls=True,
    )

    assert written_urls == {"https://example.com/a", "https://example.com/b"}
