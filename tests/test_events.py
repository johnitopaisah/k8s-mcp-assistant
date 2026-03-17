from __future__ import annotations

from unittest.mock import MagicMock
import pytest

from k8s_mcp_assistant.config import Settings
from k8s_mcp_assistant.kubernetes.events import list_events
from k8s_mcp_assistant.kubernetes.pods import (
    KubernetesOperationsError,
    NamespaceAccessError,
)
from kubernetes.client.exceptions import ApiException


def _settings(allowed: list[str] | None = None) -> Settings:
    return Settings(
        allowed_namespaces=allowed or [],
        read_only=True,
        kubeconfig_path=None, kubeconfig=None, kube_context=None,
        kube_api_server=None, kube_user=None, kube_cluster=None,
        default_log_tail_lines=100, max_log_tail_lines=1000,
    )


def _mock_event(
    reason: str = "Pulling",
    message: str = "Pulling image nginx",
    event_type: str = "Normal",
    obj_name: str = "my-pod",
    obj_kind: str = "Pod",
    count: int = 1,
    last_time: str = "2026-01-01T00:01:00",
    first_time: str = "2026-01-01T00:00:00",
) -> MagicMock:
    e = MagicMock()
    e.type = event_type
    e.reason = reason
    e.message = message
    e.count = count
    e.first_timestamp.isoformat.return_value = first_time
    e.last_timestamp.isoformat.return_value = last_time
    e.source.component = "kubelet"
    e.involved_object.name = obj_name
    e.involved_object.kind = obj_kind
    return e


class TestListEvents:
    def test_returns_event_list(self):
        api = MagicMock()
        api.list_namespaced_event.return_value.items = [_mock_event()]
        result = list_events(settings=_settings(), api=api, namespace="default")
        assert result["namespace"] == "default"
        assert result["event_count"] == 1
        assert result["events"][0]["reason"] == "Pulling"

    def test_event_fields_present(self):
        api = MagicMock()
        api.list_namespaced_event.return_value.items = [_mock_event()]
        result = list_events(settings=_settings(), api=api, namespace="default")
        evt = result["events"][0]
        assert evt["type"] == "Normal"
        assert evt["message"] == "Pulling image nginx"
        assert evt["count"] == 1
        assert evt["source"] == "kubelet"
        assert evt["involved_object"] == "my-pod"
        assert evt["involved_object_kind"] == "Pod"

    def test_events_sorted_newest_first(self):
        api = MagicMock()
        old = _mock_event(reason="OldEvent", last_time="2026-01-01T00:00:00")
        new = _mock_event(reason="NewEvent", last_time="2026-01-01T01:00:00")
        api.list_namespaced_event.return_value.items = [old, new]
        result = list_events(settings=_settings(), api=api, namespace="default")
        assert result["events"][0]["reason"] == "NewEvent"
        assert result["events"][1]["reason"] == "OldEvent"

    def test_empty_namespace_returns_empty_list(self):
        api = MagicMock()
        api.list_namespaced_event.return_value.items = []
        result = list_events(settings=_settings(), api=api, namespace="default")
        assert result["event_count"] == 0
        assert result["events"] == []

    def test_field_selector_passed_through(self):
        api = MagicMock()
        api.list_namespaced_event.return_value.items = []
        list_events(
            settings=_settings(), api=api, namespace="default",
            field_selector="involvedObject.name=my-pod"
        )
        _, kwargs = api.list_namespaced_event.call_args
        assert kwargs["field_selector"] == "involvedObject.name=my-pod"

    def test_no_field_selector_passes_none(self):
        api = MagicMock()
        api.list_namespaced_event.return_value.items = []
        list_events(settings=_settings(), api=api, namespace="default", field_selector=None)
        _, kwargs = api.list_namespaced_event.call_args
        assert kwargs["field_selector"] is None

    def test_warning_events_included(self):
        api = MagicMock()
        api.list_namespaced_event.return_value.items = [
            _mock_event(event_type="Warning", reason="Failed", message="Failed to pull image"),
        ]
        result = list_events(settings=_settings(), api=api, namespace="default")
        assert result["events"][0]["type"] == "Warning"
        assert result["events"][0]["reason"] == "Failed"

    def test_multiple_events_correct_count(self):
        api = MagicMock()
        api.list_namespaced_event.return_value.items = [
            _mock_event(reason="Scheduled", last_time="2026-01-01T00:00:00"),
            _mock_event(reason="Pulling", last_time="2026-01-01T00:01:00"),
            _mock_event(reason="Pulled", last_time="2026-01-01T00:02:00"),
            _mock_event(reason="Created", last_time="2026-01-01T00:03:00"),
            _mock_event(reason="Started", last_time="2026-01-01T00:04:00"),
        ]
        result = list_events(settings=_settings(), api=api, namespace="default")
        assert result["event_count"] == 5
        assert result["events"][0]["reason"] == "Started"  # newest first

    def test_namespace_access_denied(self):
        api = MagicMock()
        with pytest.raises(NamespaceAccessError):
            list_events(settings=_settings(["kube-system"]), api=api, namespace="default")

    def test_api_exception_raises_operations_error(self):
        api = MagicMock()
        api.list_namespaced_event.side_effect = ApiException(status=403, reason="Forbidden")
        with pytest.raises(KubernetesOperationsError):
            list_events(settings=_settings(), api=api, namespace="default")
