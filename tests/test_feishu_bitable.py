"""
feishu_bitable.py 单元测试
覆盖：批量写入部分失败时的成功 URL 记录、日期区间过滤辅助逻辑。
"""

import feishu_bitable
from feishu_bitable import _build_record, _map_bitable_record, write_to_bitable


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


def test_build_record_writes_hierarchical_geography_when_fields_exist():
    record = _build_record(
        {
            "title_zh": "测试",
            "region": "欧洲",
            "jurisdiction": "欧盟",
            "applicability_scope": "supranational",
        },
        available_fields={"具体国家/地区", "适用范围"},
    )
    assert record["fields"]["国家/地区"] == "欧洲"
    assert record["fields"]["具体国家/地区"] == "欧盟"
    assert record["fields"]["适用范围"] == "超国家管辖区"


def test_build_record_omits_optional_fields_for_legacy_table():
    fields = _build_record(
        {"region": "北美", "jurisdiction": "美国", "applicability_scope": "single"},
        available_fields=set(),
    )["fields"]
    assert fields["国家/地区"] == "北美"
    assert "具体国家/地区" not in fields
    assert "适用范围" not in fields
    assert "推送判定" not in fields


def test_build_record_writes_push_assessment_when_fields_exist():
    fields = _build_record(
        {
            "title_zh": "测试",
            "push_decision": "pool_only",
            "value_score": 1,
            "noise_reason": "信息不足",
        },
        available_fields={"推送判定", "信息价值分", "降噪原因"},
    )["fields"]
    assert fields["推送判定"] == "📥 仅入池"
    assert fields["信息价值分"] == 1
    assert fields["降噪原因"] == "信息不足"


def test_map_bitable_record_reads_hierarchical_geography():
    item = _map_bitable_record({
        "国家/地区": "港澳台",
        "具体国家/地区": "台湾地区",
        "适用范围": "单一管辖区",
    })
    assert item["jurisdiction"] == "台湾地区"
    assert item["applicability_scope"] == "single"
