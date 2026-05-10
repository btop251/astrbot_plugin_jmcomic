from __future__ import annotations

from typing import Any


SETTING_PATHS = {
    "jm_project_path": "basic.jm_project_path",
    "default_download_format": "basic.default_download_format",
    "search_default_limit": "basic.search_default_limit",
    "image_batch_size": "basic.image_batch_size",
    "pdf_merge_batch_size": "basic.pdf_merge_batch_size",
    "client_impl": "network.client_impl",
    "retry_times": "network.retry_times",
    "proxy": "network.proxy",
    "cookies_avs": "auth.cookies_avs",
    "username": "auth.username",
    "password": "auth.password",
    "download_base_dir": "download.download_base_dir",
    "dir_rule": "download.dir_rule",
    "normalize_zh": "download.normalize_zh",
    "download_cache": "download.download_cache",
    "decode_image": "download.decode_image",
    "thread_image": "download.thread_image",
    "thread_photo": "download.thread_photo",
    "cache_keep_last": "cache.cache_keep_last",
    "allow_group_read": "permission.allow_group_read",
    "allow_private_read": "permission.allow_private_read",
    "allow_group_download": "permission.allow_group_download",
    "download_admin_only": "permission.download_admin_only",
    "max_concurrent_tasks": "advanced.max_concurrent_tasks",
    "task_history_limit": "advanced.task_history_limit",
    "enable_jm_log": "advanced.enable_jm_log",
}


def _nested_get(data: dict[str, Any], path: str) -> Any:
    current: Any = data
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def get_setting(config: dict[str, Any] | None, key: str, default: Any = None) -> Any:
    if not isinstance(config, dict):
        return default

    if key in config:
        value = config.get(key, default)
        return default if value is None else value

    path = SETTING_PATHS.get(key)
    if not path:
        return default

    value = _nested_get(config, path)
    return default if value is None else value
