"""Tests for link-typed custom fields, initial status, Work (estimatedTime) and the schema tool."""

import json

import pytest
from aioresponses import aioresponses

from src.client import OpenProjectClient, hours_to_duration
from src.tools.context import schema_fields
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


@pytest.mark.parametrize(
    "hours, expected",
    [(160, "PT160H"), (8.0, "PT8H"), (1.5, "PT1H30M"), (0, "PT0H"), (0.25, "PT0H15M")],
)
def test_hours_to_duration(hours, expected):
    assert hours_to_duration(hours) == expected


async def test_create_sends_status_estimated_time_and_link_fields(client, http):
    http.post(f"{API}/work_packages/form", payload={"payload": {"_links": {}}, "lockVersion": 0})
    http.post(f"{API}/work_packages", payload={"id": 1})

    await client.create_work_package(
        {
            "project": 21,
            "subject": "Nowe",
            "type": 7,
            "status_id": 13,
            "estimated_hours": 160,
            "custom_fields": {49: "Krótki opis"},
            "custom_field_links": {54: "/api/v3/versions/3237", 1: {"href": "/api/v3/custom_options/5"}},
        }
    )

    body = sent_json(http, "POST", url_suffix="/work_packages")
    assert body["_links"]["status"] == {"href": "/api/v3/statuses/13"}
    assert body["estimatedTime"] == "PT160H"
    assert body["customField49"] == "Krótki opis"
    assert body["_links"]["customField54"] == {"href": "/api/v3/versions/3237"}
    assert body["_links"]["customField1"] == {"href": "/api/v3/custom_options/5"}


async def test_create_without_new_fields_sends_none_of_them(client, http):
    http.post(f"{API}/work_packages/form", payload={"payload": {"_links": {}}, "lockVersion": 0})
    http.post(f"{API}/work_packages", payload={"id": 1})

    await client.create_work_package({"project": 21, "subject": "Nowe", "type": 7})

    body = sent_json(http, "POST", url_suffix="/work_packages")
    assert "estimatedTime" not in body
    assert "status" not in body.get("_links", {})


async def test_update_sends_link_fields_and_estimated_time_only(client, http):
    http.get(f"{API}/work_packages/5", payload={"id": 5, "lockVersion": 3})
    http.patch(f"{API}/work_packages/5", payload={"id": 5})

    await client.update_work_package(
        5, {"estimated_hours": 24, "custom_field_links": {54: "/api/v3/versions/3297"}}
    )

    body = sent_json(http, "PATCH")
    assert body == {
        "lockVersion": 3,
        "estimatedTime": "PT24H",
        "_links": {"customField54": {"href": "/api/v3/versions/3297"}},
    }


def test_input_models_accept_new_fields():
    create = CreateWorkPackageInput(
        project_id=21, subject="Nowe", type_id=7, status_id=13, estimated_hours=8,
        custom_field_links={"54": "/api/v3/versions/3237"},
    )
    update = UpdateWorkPackageInput(work_package_id=5, custom_field_links={"1": "/api/v3/custom_options/5"})

    assert create.custom_field_links == {54: "/api/v3/versions/3237"}
    assert update.custom_field_links == {1: "/api/v3/custom_options/5"}


def test_input_rejects_negative_hours():
    with pytest.raises(ValueError):
        CreateWorkPackageInput(project_id=21, subject="Nowe", type_id=7, estimated_hours=-1)


async def test_create_tool_passes_status_links_and_hours(mock_client, call_tool):
    mock_client.create_work_package.return_value = {"id": 9, "subject": "Nowe", "estimatedTime": "PT8H"}

    text = await call_tool(
        "create_work_package",
        input=CreateWorkPackageInput(
            project_id=21, subject="Nowe", type_id=7, status_id=13, estimated_hours=8,
            custom_field_links={54: "/api/v3/versions/3237"},
        ),
    )

    data = mock_client.create_work_package.await_args.args[0]
    assert data["status_id"] == 13
    assert data["estimated_hours"] == 8
    assert data["custom_field_links"] == {54: "/api/v3/versions/3237"}
    assert "PT8H" in text


async def test_update_tool_accepts_only_link_fields(mock_client, call_tool):
    mock_client.update_work_package.return_value = {"id": 5, "subject": "X"}

    text = await call_tool(
        "update_work_package",
        input=UpdateWorkPackageInput(work_package_id=5, custom_field_links={54: "/api/v3/versions/3237"}),
    )

    mock_client.update_work_package.assert_awaited_once_with(
        5, {"custom_field_links": {54: "/api/v3/versions/3237"}}
    )
    assert "updated successfully" in text


SCHEMA = {
    "subject": {"type": "String", "name": "Subject", "required": True},
    "customField54": {
        "type": "Version",
        "name": "Wersja ADD (tylko PO)",
        "required": False,
        "_links": {"allowedValues": [{"href": "/api/v3/versions/3237", "title": "3.00.002. (planowana)"}]},
    },
    "customField40": {
        "type": "CustomOption",
        "name": "Kategoria (rozwój)",
        "required": True,
        "_embedded": {"allowedValues": [
            {"value": "06. Ulepszenie UI i UX", "_links": {"self": {"href": "/api/v3/custom_options/77"}}}
        ]},
    },
    "customField49": {"type": "String", "name": "Krótki opis biznesowy (tylko PO)", "required": False},
    "_links": {},
}


def test_schema_fields_lists_custom_fields_with_allowed_values():
    fields = {f["key"]: f for f in schema_fields(SCHEMA)}

    assert set(fields) == {"customField54", "customField40", "customField49"}
    assert fields["customField54"]["allowed_values"] == [
        {"href": "/api/v3/versions/3237", "title": "3.00.002. (planowana)"}
    ]
    assert fields["customField40"]["allowed_values"] == [
        {"href": "/api/v3/custom_options/77", "title": "06. Ulepszenie UI i UX"}
    ]
    assert fields["customField40"]["required"] is True
    assert "allowed_values" not in fields["customField49"]


def test_schema_fields_includes_standard_fields_when_requested():
    keys = [f["key"] for f in schema_fields(SCHEMA, only_custom=False)]
    assert "subject" in keys


async def test_get_work_package_schema_tool_json(mock_client, call_tool):
    mock_client.get_work_package_schema.return_value = SCHEMA

    text = await call_tool("get_work_package_schema", project_id=21, type_id=7, format="json")

    mock_client.get_work_package_schema.assert_awaited_once_with(21, 7)
    data = json.loads(text)
    assert data["project_id"] == 21
    assert len(data["fields"]) == 3


async def test_get_work_package_schema_tool_markdown(mock_client, call_tool):
    mock_client.get_work_package_schema.return_value = SCHEMA

    text = await call_tool("get_work_package_schema", project_id=21, type_id=7)

    assert "customField54" in text
    assert "/api/v3/versions/3237" in text
