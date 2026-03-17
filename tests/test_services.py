from __future__ import annotations

from unittest.mock import MagicMock
import pytest

from k8s_mcp_assistant.config import Settings
from k8s_mcp_assistant.kubernetes.services import list_services
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


def _mock_port(port: int = 80, protocol: str = "TCP",
               name: str = "http", node_port: int | None = None) -> MagicMock:
    p = MagicMock()
    p.port = port
    p.protocol = protocol
    p.name = name
    p.target_port = port
    p.node_port = node_port
    return p


def _mock_service(name: str = "my-svc", namespace: str = "default",
                  svc_type: str = "ClusterIP") -> MagicMock:
    s = MagicMock()
    s.metadata.name = name
    s.metadata.namespace = namespace
    s.metadata.labels = {"app": name}
    s.metadata.creation_timestamp.isoformat.return_value = "2026-01-01T00:00:00"
    s.spec.type = svc_type
    s.spec.cluster_ip = "10.96.0.1"
    s.spec.selector = {"app": name}
    s.spec.ports = [_mock_port()]
    s.spec.external_i_ps = None
    s.status.load_balancer.ingress = None
    return s


class TestListServices:
    def test_returns_service_list(self):
        api = MagicMock()
        api.list_namespaced_service.return_value.items = [_mock_service()]
        result = list_services(settings=_settings(), api=api, namespace="default")
        assert result["namespace"] == "default"
        assert result["service_count"] == 1
        assert result["services"][0]["name"] == "my-svc"

    def test_service_type_included(self):
        api = MagicMock()
        api.list_namespaced_service.return_value.items = [_mock_service(svc_type="NodePort")]
        result = list_services(settings=_settings(), api=api, namespace="default")
        assert result["services"][0]["type"] == "NodePort"

    def test_cluster_ip_included(self):
        api = MagicMock()
        api.list_namespaced_service.return_value.items = [_mock_service()]
        result = list_services(settings=_settings(), api=api, namespace="default")
        assert result["services"][0]["cluster_ip"] == "10.96.0.1"

    def test_ports_included(self):
        api = MagicMock()
        api.list_namespaced_service.return_value.items = [_mock_service()]
        result = list_services(settings=_settings(), api=api, namespace="default")
        ports = result["services"][0]["ports"]
        assert len(ports) == 1
        assert ports[0]["port"] == 80
        assert ports[0]["protocol"] == "TCP"

    def test_loadbalancer_external_ip_from_ingress(self):
        api = MagicMock()
        svc = _mock_service(svc_type="LoadBalancer")
        ingress = MagicMock()
        ingress.hostname = None
        ingress.ip = "203.0.113.10"
        svc.status.load_balancer.ingress = [ingress]
        api.list_namespaced_service.return_value.items = [svc]
        result = list_services(settings=_settings(), api=api, namespace="default")
        assert result["services"][0]["external_ip"] == "203.0.113.10"

    def test_loadbalancer_external_hostname(self):
        api = MagicMock()
        svc = _mock_service(svc_type="LoadBalancer")
        ingress = MagicMock()
        ingress.hostname = "a1b2c3.us-east-1.elb.amazonaws.com"
        ingress.ip = None
        svc.status.load_balancer.ingress = [ingress]
        api.list_namespaced_service.return_value.items = [svc]
        result = list_services(settings=_settings(), api=api, namespace="default")
        assert result["services"][0]["external_ip"] == "a1b2c3.us-east-1.elb.amazonaws.com"

    def test_no_external_ip_is_none(self):
        api = MagicMock()
        api.list_namespaced_service.return_value.items = [_mock_service()]
        result = list_services(settings=_settings(), api=api, namespace="default")
        assert result["services"][0]["external_ip"] is None

    def test_empty_namespace_returns_empty_list(self):
        api = MagicMock()
        api.list_namespaced_service.return_value.items = []
        result = list_services(settings=_settings(), api=api, namespace="default")
        assert result["service_count"] == 0
        assert result["services"] == []

    def test_namespace_access_denied(self):
        api = MagicMock()
        with pytest.raises(NamespaceAccessError):
            list_services(settings=_settings(["kube-system"]), api=api, namespace="default")

    def test_api_exception_raises_operations_error(self):
        api = MagicMock()
        api.list_namespaced_service.side_effect = ApiException(status=403, reason="Forbidden")
        with pytest.raises(KubernetesOperationsError):
            list_services(settings=_settings(), api=api, namespace="default")

    def test_selector_included(self):
        api = MagicMock()
        api.list_namespaced_service.return_value.items = [_mock_service()]
        result = list_services(settings=_settings(), api=api, namespace="default")
        assert result["services"][0]["selector"] == {"app": "my-svc"}

    def test_multiple_services(self):
        api = MagicMock()
        api.list_namespaced_service.return_value.items = [
            _mock_service("svc-a"),
            _mock_service("svc-b", svc_type="NodePort"),
            _mock_service("svc-c", svc_type="LoadBalancer"),
        ]
        result = list_services(settings=_settings(), api=api, namespace="default")
        assert result["service_count"] == 3
        names = [s["name"] for s in result["services"]]
        assert "svc-a" in names
        assert "svc-b" in names
        assert "svc-c" in names
