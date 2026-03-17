from __future__ import annotations

import pytest
from k8s_mcp_assistant.config import Settings


class TestSettingsLoad:
    def test_defaults_when_no_env(self, monkeypatch):
        for key in [
            "K8S_ALLOWED_NAMESPACES", "K8S_READ_ONLY",
            "K8S_DEFAULT_LOG_TAIL_LINES", "K8S_MAX_LOG_TAIL_LINES",
        ]:
            monkeypatch.delenv(key, raising=False)
        s = Settings.load()
        assert s.allowed_namespaces == []
        assert s.read_only is True
        assert s.default_log_tail_lines == 100
        assert s.max_log_tail_lines == 1000

    def test_allowed_namespaces_parsed(self, monkeypatch):
        monkeypatch.setenv("K8S_ALLOWED_NAMESPACES", "default, kube-system, argocd")
        s = Settings.load()
        assert s.allowed_namespaces == ["default", "kube-system", "argocd"]

    def test_empty_allowed_namespaces(self, monkeypatch):
        monkeypatch.setenv("K8S_ALLOWED_NAMESPACES", "")
        s = Settings.load()
        assert s.allowed_namespaces == []

    def test_read_only_false(self, monkeypatch):
        monkeypatch.setenv("K8S_READ_ONLY", "false")
        s = Settings.load()
        assert s.read_only is False

    def test_read_only_truthy_values(self, monkeypatch):
        for val in ("1", "true", "yes", "on", "True", "YES"):
            monkeypatch.setenv("K8S_READ_ONLY", val)
            assert Settings.load().read_only is True

    def test_log_tail_lines_custom(self, monkeypatch):
        monkeypatch.setenv("K8S_DEFAULT_LOG_TAIL_LINES", "50")
        monkeypatch.setenv("K8S_MAX_LOG_TAIL_LINES", "500")
        s = Settings.load()
        assert s.default_log_tail_lines == 50
        assert s.max_log_tail_lines == 500

    def test_invalid_tail_lines_clamped_to_default(self, monkeypatch):
        monkeypatch.setenv("K8S_DEFAULT_LOG_TAIL_LINES", "0")
        monkeypatch.setenv("K8S_MAX_LOG_TAIL_LINES", "-1")
        s = Settings.load()
        assert s.default_log_tail_lines == 100
        assert s.max_log_tail_lines == 1000


class TestIsNamespaceAllowed:
    def _settings(self, namespaces: list[str]) -> Settings:
        return Settings(
            allowed_namespaces=namespaces,
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

    def test_empty_list_allows_all(self):
        s = self._settings([])
        assert s.is_namespace_allowed("default") is True
        assert s.is_namespace_allowed("kube-system") is True
        assert s.is_namespace_allowed("anything") is True

    def test_explicit_list_allows_only_listed(self):
        s = self._settings(["default", "kube-system"])
        assert s.is_namespace_allowed("default") is True
        assert s.is_namespace_allowed("kube-system") is True
        assert s.is_namespace_allowed("argocd") is False

    def test_single_namespace(self):
        s = self._settings(["production"])
        assert s.is_namespace_allowed("production") is True
        assert s.is_namespace_allowed("staging") is False
