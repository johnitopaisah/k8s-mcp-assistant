from __future__ import annotations

from kubernetes import client, config
from kubernetes.config.config_exception import ConfigException

from k8s_mcp_assistant.config import Settings


class KubernetesClientError(Exception):
    """Raised when Kubernetes client initialization or configuration fails."""


def load_kube_configuration(settings: Settings) -> None:
    """
    Load Kubernetes configuration once with the following preference order:
    1. Explicit kubeconfig content / context from settings
    2. Default kubeconfig file (~/.kube/config)
    3. In-cluster configuration (when running inside a Kubernetes pod)
    """
    try:
        if settings.kubeconfig or settings.kube_context:
            config.load_kube_config(
                config_file=settings.kubeconfig_path,
                context=settings.kube_context,
            )
            return

        try:
            config.load_kube_config(config_file=settings.kubeconfig_path or None)
            return
        except ConfigException:
            config.load_incluster_config()
    except Exception as exc:
        raise KubernetesClientError(
            "Failed to load Kubernetes configuration. "
            "Check your kubeconfig, context, and in-cluster configuration settings."
        ) from exc


# Module-level cache: configuration is loaded once per process.
_config_loaded: bool = False


def _ensure_config(settings: Settings) -> None:
    global _config_loaded
    if not _config_loaded:
        load_kube_configuration(settings)
        _config_loaded = True


def get_core_v1_api(settings: Settings) -> client.CoreV1Api:
    _ensure_config(settings)
    return client.CoreV1Api()


def get_apps_v1_api(settings: Settings) -> client.AppsV1Api:
    _ensure_config(settings)
    return client.AppsV1Api()
