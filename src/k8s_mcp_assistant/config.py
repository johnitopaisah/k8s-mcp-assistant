from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv

load_dotenv()


def _parse_csv_env(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _parse_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class Settings:
    allowed_namespaces: list[str]
    read_only: bool
    kubeconfig_path: Optional[str]
    kubeconfig: Optional[str]
    kube_context: Optional[str]
    kube_api_server: Optional[str]
    kube_user: Optional[str]
    kube_cluster: Optional[str]
    default_log_tail_lines: int
    max_log_tail_lines: int

    @classmethod
    def load(cls) -> "Settings":
        default_tail_lines = int(os.getenv("K8S_DEFAULT_LOG_TAIL_LINES", "100"))
        max_tail_lines = int(os.getenv("K8S_MAX_LOG_TAIL_LINES", "1000"))

        if default_tail_lines < 1:
            default_tail_lines = 100
        if max_tail_lines < 1:
            max_tail_lines = 1000

        return cls(
            allowed_namespaces=_parse_csv_env(os.getenv("K8S_ALLOWED_NAMESPACES")),
            read_only=_parse_bool(os.getenv("K8S_READ_ONLY"), default=True),
            kubeconfig_path=os.getenv("KUBECONFIG_PATH") or None,
            kubeconfig=os.getenv("KUBECONFIG") or None,
            kube_context=os.getenv("KUBE_CONTEXT") or None,
            kube_api_server=os.getenv("KUBE_API_SERVER") or None,
            kube_user=os.getenv("KUBE_USER") or None,
            kube_cluster=os.getenv("KUBE_CLUSTER") or None,
            default_log_tail_lines=default_tail_lines,
            max_log_tail_lines=max_tail_lines,
        )

    def is_namespace_allowed(self, namespace: str) -> bool:
        if not self.allowed_namespaces:
            return True
        return namespace in self.allowed_namespaces
