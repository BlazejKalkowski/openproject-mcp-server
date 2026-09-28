"""Tests for time entry custom field support (aioresponses, no network)."""

import pytest
from aioresponses import aioresponses

from src.client import OpenProjectClient
from src.tools.time_entries import CreateTimeEntryInput, UpdateTimeEntryInput
from src.utils.cache import TTLCache

BASE = "https://op.example.test"
API = f"{BASE}/api/v3"


@pytest.fixture
def client():
    c = OpenProjectClient(base_url=BASE, api_key="secret")
    c.cache = TTLCache(ttl=0)
    return c


@pytest.fixture
def http():
    with aioresponses() as m:
        yield m


def sent_json(m, method):
    for (req_method, _url), items in m.requests.items():
        if req_method == method:
            return items[-1].kwargs["json"]
    raise AssertionError(f"no {method} request sent")


async def test_create_time_entry_sends_custom_fields(client, http):
    http.post(f"{API}/time_entries", payload={"id": 1, "customField56": True})

    await client.create_time_entry(
        {"work_package_id": 10, "hours": "2", "spent_on": "2026-09-25", "activity_id": 7, "custom_fields": {56: True}}
    )

    body = sent_json(http, "POST")
    assert body["customField56"] is True
    assert body["_links"]["activity"]["href"] == "/api/v3/time_entries/activities/7"


async def test_create_time_entry_without_custom_fields_sends_none(client, http):
    http.post(f"{API}/time_entries", payload={"id": 1})

    await client.create_time_entry({"work_package_id": 10, "hours": "2", "spent_on": "2026-09-25", "activity_id": 7})

    body = sent_json(http, "POST")
    assert not [key for key in body if key.startswith("customField")]


async def test_update_time_entry_sends_custom_fields_with_lock_version(client, http):
    http.get(f"{API}/time_entries/5", payload={"id": 5, "lockVersion": 3})
    http.patch(f"{API}/time_entries/5", payload={"id": 5, "customField56": True})

    await client.update_time_entry(5, {"custom_fields": {56: True}})

    body = sent_json(http, "PATCH")
    assert body == {"lockVersion": 3, "customField56": True}


def test_input_models_accept_string_keys_for_custom_fields():
    create = CreateTimeEntryInput(
        work_package_id=1, hours=2, spent_on="2026-09-25", activity_id=7, custom_fields={"56": True}
    )
    update = UpdateTimeEntryInput(time_entry_id=1, custom_fields={"56": True})

    assert create.custom_fields == {56: True}
    assert update.custom_fields == {56: True}
