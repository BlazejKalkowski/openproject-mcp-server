"""Tests for duplicating work packages (aioresponses, no network)."""

import pytest
from aioresponses import aioresponses

from src.client import OpenProjectClient
from src.utils.cache import TTLCache

BASE = "https://op.example.test"
API = f"{BASE}/api/v3"

SOURCE = {
    "id": 42,
    "subject": "Naprawić logowanie",
    "description": {"raw": "Opis źródłowy", "format": "markdown"},
    "scheduleManually": True,
    "startDate": "2026-01-01",
    "dueDate": "2026-01-31",
    "estimatedTime": "PT8H",
    "remainingTime": "PT3H",
    "percentageDone": 60,
    "spentTime": "PT5H",
    "lockVersion": 7,
    "createdAt": "2026-01-01T10:00:00Z",
    "customField56": True,
    "customField20": {"raw": "Kroki testowe"},
    "_links": {
        "self": {"href": "/api/v3/work_packages/42"},
        "project": {"href": "/api/v3/projects/5"},
        "type": {"href": "/api/v3/types/6"},
        "status": {"href": "/api/v3/statuses/1"},
        "priority": {"href": "/api/v3/priorities/8"},
        "assignee": {"href": "/api/v3/users/11"},
        "author": {"href": "/api/v3/users/99"},
        "version": {"href": "/api/v3/versions/3"},
        "customField40": {"href": "/api/v3/custom_options/77", "title": "Opcja"},
    },
}


@pytest.fixture
def client():
    c = OpenProjectClient(base_url=BASE, api_key="secret")
    c.cache = TTLCache(ttl=0)
    return c


@pytest.fixture
def http():
    with aioresponses() as m:
        yield m


def sent_json(m, method, url_suffix=None):
    for (req_method, url), items in m.requests.items():
        if req_method == method and (url_suffix is None or str(url).endswith(url_suffix)):
            return items[-1].kwargs["json"]
    raise AssertionError(f"no {method} request sent")


def test_copy_payload_carries_fields_and_custom_fields(client):
    data = client.build_work_package_copy(SOURCE)

    assert data["project"] == 5
    assert data["subject"] == "Naprawić logowanie"
    assert data["description"] == "Opis źródłowy"
    assert data["scheduleManually"] is True
    assert data["type"] == 6
    assert data["status_id"] == 1
    assert data["priority_id"] == 8
    assert data["assignee_id"] == 11
    assert data["version_id"] == 3
    assert data["custom_fields"] == {56: True, 20: {"raw": "Kroki testowe"}}
    assert data["custom_field_links"] == {40: {"href": "/api/v3/custom_options/77"}}
    assert data["notify"] is False


def test_copy_payload_resets_time_and_progress(client):
    data = client.build_work_package_copy(SOURCE)

    for field in ("startDate", "dueDate", "estimatedTime", "remainingTime", "percentageDone", "duration"):
        assert field not in data


def test_copy_payload_skips_read_only_fields(client):
    data = client.build_work_package_copy(SOURCE)

    for field in ("id", "lockVersion", "createdAt", "updatedAt", "spentTime", "author_id"):
        assert field not in data


def test_copy_payload_honours_overrides(client):
    data = client.build_work_package_copy(SOURCE, target_project_id=9, subject="Kopia")

    assert data["project"] == 9
    assert data["subject"] == "Kopia"


def test_copy_payload_without_project_raises(client):
    with pytest.raises(ValueError):
        client.build_work_package_copy({"subject": "Bez projektu", "_links": {}})


async def test_duplicate_work_package_posts_copy(client, http):
    http.get(f"{API}/work_packages/42", payload=SOURCE)
    http.post(f"{API}/work_packages/form", payload={"payload": {"_links": {}}, "lockVersion": 0})
    http.post(f"{API}/work_packages?notify=false", payload={"id": 101, "subject": "Naprawić logowanie"})

    result = await client.duplicate_work_package(42)

    assert result["id"] == 101
    body = sent_json(http, "POST", url_suffix="notify=false")
    assert body["customField56"] is True
    assert body["_links"]["customField40"] == {"href": "/api/v3/custom_options/77"}
    assert "percentageDone" not in body
    assert "startDate" not in body
