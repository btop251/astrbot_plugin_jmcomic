from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from astrbot import logger

from .settings import get_setting


class ConfigMapper:
    def __init__(self, plugin_name: str, config: dict | None, data_dir: Path) -> None:
        self.plugin_name = plugin_name
        self.config = config or {}
        self.data_dir = data_dir

    def ensure_import_path(self) -> None:
        jm_project_path = str(get_setting(self.config, "jm_project_path", "")).strip()
        if not jm_project_path:
            return
        if jm_project_path not in sys.path:
            sys.path.insert(0, jm_project_path)
            logger.info("[%s] added jm project path: %s", self.plugin_name, jm_project_path)

    def build_option_dict(self) -> dict[str, Any]:
        base_dir = str(get_setting(self.config, "download_base_dir", "")).strip()
        if not base_dir:
            base_dir = str((self.data_dir / "cache").resolve())

        normalize_zh = str(get_setting(self.config, "normalize_zh", "")).strip() or None
        image_suffix = None

        proxy_value = str(get_setting(self.config, "proxy", "system")).strip()
        if proxy_value.lower() in {"", "none", "null"}:
            proxies: Any = None
        elif proxy_value.lower() == "system":
            proxies = None
        else:
            proxies = proxy_value

        cookies = {}
        avs = str(get_setting(self.config, "cookies_avs", "")).strip()
        if avs:
            cookies["AVS"] = avs

        option_dict: dict[str, Any] = {
            "log": bool(get_setting(self.config, "enable_jm_log", False)),
            "dir_rule": {
                "rule": str(get_setting(self.config, "dir_rule", "Bd_Aid_Pindex")).strip() or "Bd_Aid_Pindex",
                "base_dir": base_dir,
                "normalize_zh": normalize_zh,
            },
            "download": {
                "cache": bool(get_setting(self.config, "download_cache", True)),
                "image": {
                    "decode": bool(get_setting(self.config, "decode_image", True)),
                    "suffix": image_suffix,
                },
                "threading": {
                    "image": int(get_setting(self.config, "thread_image", 10) or 10),
                    "photo": int(get_setting(self.config, "thread_photo", 4) or 4),
                },
            },
            "client": {
                "impl": str(get_setting(self.config, "client_impl", "api")).strip() or "api",
                "retry_times": int(get_setting(self.config, "retry_times", 5) or 5),
                "cache": None,
                "domain": [],
                "postman": {
                    "type": "curl_cffi",
                    "meta_data": {
                        "impersonate": "chrome",
                        "headers": None,
                        "proxies": proxies,
                        "cookies": cookies or None,
                    },
                },
            },
            "plugins": {
                "valid": "log",
            },
        }
        return option_dict

    def build_runtime_summary(self) -> str:
        base_dir = str(get_setting(self.config, "download_base_dir", "")).strip()
        if not base_dir:
            base_dir = str((self.data_dir / "cache").resolve())
        return (
            f"JM 配置摘要\n"
            f"默认下载格式: {get_setting(self.config, 'default_download_format', 'pdf')}\n"
            f"搜索返回条数: {get_setting(self.config, 'search_default_limit', 5)}\n"
            f"图片分批回传数量: {get_setting(self.config, 'image_batch_size', 10)}\n"
            f"PDF 分批合成数量: {get_setting(self.config, 'pdf_merge_batch_size', 20)}\n"
            f"客户端实现: {get_setting(self.config, 'client_impl', 'api')}\n"
            f"重试次数: {get_setting(self.config, 'retry_times', 5)}\n"
            f"代理: {get_setting(self.config, 'proxy', 'system')}\n"
            f"缓存目录: {base_dir}\n"
            f"目录规则: {get_setting(self.config, 'dir_rule', 'Bd_Aid_Pindex')}\n"
            f"保留缓存次数: {get_setting(self.config, 'cache_keep_last', 3)}\n"
            f"群聊可查询: {get_setting(self.config, 'allow_group_read', True)}\n"
            f"群聊可下载: {get_setting(self.config, 'allow_group_download', False)}\n"
            f"下载仅管理员: {get_setting(self.config, 'download_admin_only', True)}"
        )
