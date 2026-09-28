"""Tests for work package custom field support (aioresponses, no network)."""

import pytest
from aioresponses import aioresponses

from src.client import OpenProjectClient
from src.tools.work_packages import CreateWorkPackageInput, UpdateWorkPackageInput
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


def sent_json(m, method, url_suffix=None):
    for (req_method, url), items in m.requests.items():
        if req_method == method and (url_suffix is None or str(url).endswith(url_suffix)):
            return items[-1].kwargs["json"]
    raise AssertionError(f"no {method} request sent")


async def test_create_work_package_sends_custom_fields(client, http):
    http.post(
        f"{API}/work_packages/form",
        payload={"payload": {"_links": {}}, "lockVersion": 0},
    )
    http.post(f"{API}/work_packages", payload={"id": 1, "customField20": {"raw": "Steps"}})

    await client.create_work_package(
        {
            "project": 5,
            "subject": "Fix login",
            "type": 6,
            "custom_fields": {20: {"raw": "Steps to reproduce"}},
        }
    )

    body = sent_json(http, "POST", url_suffix="/work_packages")
    assert body["customField20"] == {"raw": "Steps to reproduce"}


async def test_create_work_package_without_custom_fields_sends_none(client, http):
    http.post(
        f"{API}/work_packages/form",
        payload={"payload": {"_links": {}}, "lockVersion": 0},
    )
    http.post(f"{API}/work_packages", payload={"id": 1})

    await client.create_work_package({"project": 5, "subject": "Fix login", "type": 6})

    body = sent_json(http, "POST", url_suffix="/work_packages")
    assert not [key for key in body if key.startswith("customField")]


async def test_update_work_package_sends_custom_fields_with_lock_version(client, http):
    http.get(f"{API}/work_packages/5", payload={"id": 5, "lockVersion": 3})
    http.patch(f"{API}/work_packages/5", payload={"id": 5, "customField20": {"raw": "Steps"}})

    await client.update_work_package(5, {"custom_fields": {20: {"raw": "Steps to reproduce"}}})

    body = sent_json(http, "PATCH")
    assert body == {"lockVersion": 3, "customField20": {"raw": "Steps to reproduce"}}


def test_input_models_accept_string_keys_for_custom_fields():
    create = CreateWorkPackageInput(
        project_id=5, subject="Fix login", type_id=6, custom_fields={"20": {"raw": "Steps"}}
    )
    update = UpdateWorkPackageInput(work_package_id=1, custom_fields={"20": {"raw": "Steps"}})

    assert create.custom_fields == {20: {"raw": "Steps"}}
    assert update.custom_fields == {20: {"raw": "Steps"}}
