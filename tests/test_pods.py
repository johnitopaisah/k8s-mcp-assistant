from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch
from k8s_mcp_assistant.config import Settings
from k8s_mcp_assistant.kubernetes.pods import (
    list_pods,
    describe_pod,
    get_pod_logs,
    NamespaceAccessError,
    KubernetesOperationsError,
)
from kubernetes.client.exceptions import ApiException


def _settings(allowed: list[str] | None = None) -> Settings:
    return Settings(
        allowed_namespaces=allowed or [],
        read_only=True,
        kubeconfig_path=None,
        kubeconfig=None,
        kube_context=None,
        kube_api_server=None,
        kube_user=None,
        kube_cluster=None,
        default_log_tail_lines=100,
        max_log_tail_lines=1000,
    )


def _mock_pod(name: str = "my-pod", namespace: str = "default", phase: str = "Running"):
    pod = MagicMock()
    pod.metadata.name = name
    pod.metadata.namespace = namespace
    pod.metadata.labels = {"app": name}
    pod.metadata.creation_timestamp.isoformat.return_value = "2026-01-01T00:00:00"
    pod.status.phase = phase
    pod.status.pod_ip = "10.0.0.1"
    pod.status.host_ip = "192.168.1.1"
    pod.status.start_time.isoformat.return_value = "2026-01-01T00:00:00"
    pod.status.container_statuses = []
    pod.status.conditions = []
    pod.spec.node_name = "node-1"
    pod.spec.containers = []
    pod.metadata.annotations = {}
    return pod


class TestListPods:
    def test_returns_pod_list(self):
        api = MagicMock()
        pod = _mock_pod()
        api.list_namespaced_pod.return_value.items = [pod]
        result = list_pods(settings=_settings(), api=api, namespace="default")
        assert result["namespace"] == "default"
        assert result["pod_count"] == 1
        assert result["pods"][0]["name"] == "my-pod"

    def test_namespace_access_denied(self):
        api = MagicMock()
        with pytest.raises(NamespaceAccessError):
            list_pods(settings=_settings(allowed=["kube-system"]), api=api, namespace="default")

    def test_api_exception_raises_operations_error(self):
        api = MagicMock()
        api.list_namespaced_pod.side_effect = ApiException(status=403, reason="Forbidden")
        with pytest.raises(KubernetesOperationsError):
            list_pods(settings=_settings(), api=api, namespace="default")

    def test_empty_namespace_returns_empty_list(self):
        api = MagicMock()
        api.list_namespaced_pod.return_value.items = []
        result = list_pods(settings=_settings(), api=api, namespace="default")
        assert result["pod_count"] == 0
        assert result["pods"] == []


class TestDescribePod:
    def test_returns_pod_detail(self):
        api = MagicMock()
        pod = _mock_pod()
        api.read_namespaced_pod.return_value = pod
        api.list_namespaced_event.return_value.items = []
        result = describe_pod(settings=_settings(), api=api, namespace="default", pod_name="my-pod")
        assert result["name"] == "my-pod"
        assert result["status"] == "Running"

    def test_namespace_access_denied(self):
        api = MagicMock()
        with pytest.raises(NamespaceAccessError):
            describe_pod(
                settings=_settings(allowed=["kube-system"]),
                api=api,
                namespace="default",
                pod_name="my-pod",
            )

    def test_pod_not_found_raises_operations_error(self):
        api = MagicMock()
        api.read_namespaced_pod.side_effect = ApiException(status=404, reason="Not Found")
        with pytest.raises(KubernetesOperationsError):
            describe_pod(settings=_settings(), api=api, namespace="default", pod_name="missing")

    def test_events_failure_does_not_raise(self):
        api = MagicMock()
        pod = _mock_pod()
        api.read_namespaced_pod.return_value = pod
        api.list_namespaced_event.side_effect = Exception("event API down")
        # Should not raise — events are best-effort
        result = describe_pod(settings=_settings(), api=api, namespace="default", pod_name="my-pod")
        assert result["events"] == []


class TestGetPodLogs:
    def test_returns_logs(self):
        api = MagicMock()
        api.read_namespaced_pod_log.return_value = "log line 1\nlog line 2\n"
        result = get_pod_logs(settings=_settings(), api=api, namespace="default", pod_name="my-pod")
        assert result["pod_name"] == "my-pod"
        assert result["namespace"] == "default"
        assert "log line 1" in result["logs"]

    def test_container_name_passed_through(self):
        api = MagicMock()
        api.read_namespaced_pod_log.return_value = ""
        get_pod_logs(
            settings=_settings(),
            api=api,
            namespace="default",
            pod_name="my-pod",
            container_name="sidecar",
        )
        _, kwargs = api.read_namespaced_pod_log.call_args
        assert kwargs["container"] == "sidecar"

    def test_tail_lines_exceeds_max_raises(self):
        api = MagicMock()
        with pytest.raises(KubernetesOperationsError):
            get_pod_logs(
                settings=_settings(), api=api, namespace="default", pod_name="my-pod", tail_lines=9999
            )

    def test_namespace_access_denied(self):
        api = MagicMock()
        with pytest.raises(NamespaceAccessError):
            get_pod_logs(
                settings=_settings(allowed=["kube-system"]),
                api=api,
                namespace="default",
                pod_name="my-pod",
            )
