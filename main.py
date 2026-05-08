from __future__ import annotations

import asyncio
from pathlib import Path

from astrbot.api import logger, star
from astrbot.api.event import AstrMessageEvent, MessageEventResult, filter
from astrbot.api.message_components import File, Image

from .core.cache_manager import CacheManager
from .core.config_mapper import ConfigMapper
from .core.exceptions import JmPermissionError, JmPluginError, JmTaskNotFoundError
from .core.jm_service import JmService
from .core.parsers import GreedyStr
from .core.renderers import (
    render_album_detail,
    render_photo_detail,
    render_rank_page,
    render_search_page,
    render_task_detail,
    render_task_list,
)
from .core.settings import get_setting
from .core.task_manager import TaskManager
from .store.state_store import StateStore


class Main(star.Star):
    """JMComic AstrBot 插件。

    首版实现重点：
    - JM 搜索与详情查询
    - 下载后直接回传到当前平台
    - 本地仅保留最近三次下载缓存
    """

    def __init__(self, context: star.Context, config=None) -> None:
        super().__init__(context, config)
        self.context = context
        self.config = config or {}
        self.data_dir = star.StarTools.get_data_dir("astrbot_plugin_jmcomic")
        self.mapper = ConfigMapper("astrbot_plugin_jmcomic", self.config, self.data_dir)
        self.jm_service = JmService(self.mapper)
        self.state_store = StateStore(
            self.data_dir / "state",
            int(get_setting(self.config, "task_history_limit", 100) or 100),
        )
        self.task_manager = TaskManager(
            self.state_store,
            int(get_setting(self.config, "max_concurrent_tasks", 2) or 2),
        )
        self.cache_manager = CacheManager(
            self.data_dir / "cache",
            int(get_setting(self.config, "cache_keep_last", 3) or 3),
        )

    def _result(self, text: str, stop: bool = True) -> MessageEventResult:
        result = MessageEventResult().message(text).use_t2i(False)
        if stop:
            result.stop_event()
        return result

    def _default_download_format(self) -> str:
        return str(get_setting(self.config, "default_download_format", "pdf")).strip() or "pdf"

    def _ensure_read_allowed(self, event: AstrMessageEvent) -> None:
        if event.is_private_chat():
            if not bool(get_setting(self.config, "allow_private_read", True)):
                raise JmPermissionError("当前配置不允许私聊使用该命令。")
            return

        if not bool(get_setting(self.config, "allow_group_read", True)):
            raise JmPermissionError("当前配置不允许群聊使用该命令。")

    def _ensure_download_allowed(self, event: AstrMessageEvent) -> None:
        if bool(get_setting(self.config, "download_admin_only", True)) and not event.is_admin():
            raise JmPermissionError("下载命令仅管理员可用。")

        if event.is_private_chat():
            return

        if not bool(get_setting(self.config, "allow_group_download", False)):
            raise JmPermissionError("当前配置不允许群聊执行下载命令。")

    async def _send_text_proactively(self, event: AstrMessageEvent, text: str) -> None:
        ok = await self.context.send_message(
            event.unified_msg_origin,
            MessageEventResult().message(text).use_t2i(False),
        )
        if not ok:
            raise JmPluginError("主动发送文本消息失败：未找到可用平台或会话。")

    async def _upload_pdf_via_aiocqhttp(self, event: AstrMessageEvent, pdf_path: str) -> None:
        platform = self.context.get_platform_inst(event.get_platform_id())
        if platform is None or not hasattr(platform, "bot"):
            raise JmPluginError("未找到 aiocqhttp 平台实例，无法上传 PDF。")

        pdf_file = str(Path(pdf_path).resolve())
        pdf_name = Path(pdf_file).name

        if event.is_private_chat():
            user_id = event.get_sender_id()
            if not user_id.isdigit():
                raise JmPluginError(f"私聊 user_id 非法，无法上传文件: {user_id}")
            await asyncio.wait_for(
                platform.bot.call_action(  # type: ignore[attr-defined]
                    "upload_private_file",
                    user_id=int(user_id),
                    file=pdf_file,
                    name=pdf_name,
                ),
                timeout=120,
            )
            return

        group_id = event.get_group_id()
        if not group_id.isdigit():
            raise JmPluginError(f"群号非法，无法上传群文件: {group_id}")
        await asyncio.wait_for(
            platform.bot.call_action(  # type: ignore[attr-defined]
                "upload_group_file",
                group_id=int(group_id),
                file=pdf_file,
                name=pdf_name,
            ),
            timeout=120,
        )

    async def _send_pdf(self, event: AstrMessageEvent, task_id: str, pdf_path: str) -> None:
        await self._send_text_proactively(
            event,
            f"下载完成，正在回传 PDF。\n任务ID: {task_id}",
        )

        # NapCat / OneBot 场景优先走原生文件上传 action，避免 file 段被当成异常消息处理。
        if event.get_platform_name() == "aiocqhttp":
            await self._upload_pdf_via_aiocqhttp(event, pdf_path)
            return

        payload = MessageEventResult().use_t2i(False)
        payload.chain.append(File(name=Path(pdf_path).name, file=pdf_path))
        ok = await self.context.send_message(event.unified_msg_origin, payload)
        if not ok:
            raise JmPluginError("主动发送 PDF 失败：未找到可用平台或会话。")

    async def _send_images(self, event: AstrMessageEvent, task_id: str, image_files: list[str]) -> None:
        batch_size = int(get_setting(self.config, "image_batch_size", 10) or 10)
        total = len(image_files)

        await self._send_text_proactively(
            event,
            f"下载完成，开始回传图片。\n任务ID: {task_id}\n图片数: {total}",
        )

        for start in range(0, total, batch_size):
            batch = image_files[start : start + batch_size]
            payload = MessageEventResult().use_t2i(False)
            for image_path in batch:
                payload.chain.append(Image.fromFileSystem(image_path))
            ok = await self.context.send_message(event.unified_msg_origin, payload)
            if not ok:
                raise JmPluginError("主动发送图片失败：未找到可用平台或会话。")
            await asyncio.sleep(0.5)

    async def _upload_result(self, event: AstrMessageEvent, task_id: str, result: dict) -> None:
        result_type = str(result.get("result_type", "raw"))
        if result_type == "pdf":
            await self._send_pdf(event, task_id, str(result["pdf_path"]))
            return

        image_files = list(result.get("image_files", []))
        if not image_files:
            raise JmPluginError("下载结果中没有可上传的图片。")
        await self._send_images(event, task_id, image_files)

    async def _run_and_upload(self, event: AstrMessageEvent, record, func, *args) -> None:
        result = await self.task_manager.run_task(record, func, *args)
        refreshed = self.task_manager.get_task(record.task_id)

        if refreshed.status != "success":
            await self._send_text_proactively(
                event,
                f"任务执行失败。\n任务ID: {refreshed.task_id}\n"
                f"错误类型: {refreshed.error_type or '-'}\n错误信息: {refreshed.error_message or '-'}",
            )
            self.cache_manager.prune(list(self.task_manager.tasks.values()))
            return

        try:
            await self._upload_result(event, refreshed.task_id, result or {})
            refreshed.uploaded = True
            refreshed.summary = (refreshed.summary or "").strip() + "；已上传到当前平台"
            self.state_store.save_tasks(self.task_manager.tasks)
        except Exception as e:  # pragma: no cover
            logger.exception("upload result failed: %s", e)
            refreshed.status = "upload_failed"
            refreshed.error_type = type(e).__name__
            refreshed.error_message = str(e)
            refreshed.summary = (refreshed.summary or "").strip() + "；上传失败，缓存已保留"
            self.state_store.save_tasks(self.task_manager.tasks)
            await self._send_text_proactively(
                event,
                f"下载完成，但上传失败。\n任务ID: {refreshed.task_id}\n"
                f"错误类型: {refreshed.error_type}\n错误信息: {refreshed.error_message}",
            )
        finally:
            self.cache_manager.prune(list(self.task_manager.tasks.values()))

    @filter.command("jm帮助", alias={"jmhelp"})
    async def jm_help(self, event: AstrMessageEvent) -> None:
        help_text = (
            "JM 插件帮助\n"
            "/jmsearch <关键词或车号>\n"
            "/jmalbum <album_id>\n"
            "/jmphoto <photo_id>\n"
            "/jmrank <month|week|day>\n"
            "/jm下载 [原图|jpg|png|pdf] <album_id>\n"
            "/jm下载章节 [原图|jpg|png|pdf] <photo_id>\n"
            "/jm任务\n"
            "/jm任务详情 <task_id>\n"
            "/jm配置"
        )
        event.set_result(self._result(help_text))

    @filter.command("jm配置", alias={"jmconfig"})
    async def jm_config_show(self, event: AstrMessageEvent) -> None:
        try:
            self._ensure_read_allowed(event)
            event.set_result(self._result(self.mapper.build_runtime_summary()))
        except JmPermissionError as e:
            event.set_result(self._result(str(e)))

    @filter.command("jm任务", alias={"jmtasks"})
    async def jm_task_list(self, event: AstrMessageEvent) -> None:
        try:
            self._ensure_read_allowed(event)
            event.set_result(self._result(render_task_list(self.task_manager.list_tasks())))
        except JmPermissionError as e:
            event.set_result(self._result(str(e)))

    @filter.command("jm任务详情", alias={"jmtask"})
    async def jm_task_detail(self, event: AstrMessageEvent, task_id: str) -> None:
        try:
            self._ensure_read_allowed(event)
            event.set_result(self._result(render_task_detail(self.task_manager.get_task(task_id))))
        except (JmPermissionError, JmTaskNotFoundError) as e:
            event.set_result(self._result(str(e)))

    @filter.command("jmsearch")
    async def jm_search(self, event: AstrMessageEvent, query: GreedyStr) -> None:
        try:
            self._ensure_read_allowed(event)
            page = await asyncio.to_thread(self.jm_service.search, str(query).strip())
            text = render_search_page(page, int(get_setting(self.config, "search_default_limit", 5) or 5))
            event.set_result(self._result(text))
        except (JmPluginError, JmPermissionError) as e:
            event.set_result(self._result(str(e)))
        except Exception as e:  # pragma: no cover
            logger.exception("jmsearch failed: %s", e)
            event.set_result(self._result(f"搜索失败: {e}"))

    @filter.command("jmalbum")
    async def jm_album(self, event: AstrMessageEvent, album_id: str) -> None:
        try:
            self._ensure_read_allowed(event)
            album = await asyncio.to_thread(self.jm_service.get_album, album_id)
            event.set_result(self._result(render_album_detail(album)))
        except (JmPluginError, JmPermissionError) as e:
            event.set_result(self._result(str(e)))
        except Exception as e:  # pragma: no cover
            logger.exception("jmalbum failed: %s", e)
            event.set_result(self._result(f"查询本子失败: {e}"))

    @filter.command("jmphoto")
    async def jm_photo(self, event: AstrMessageEvent, photo_id: str) -> None:
        try:
            self._ensure_read_allowed(event)
            photo = await asyncio.to_thread(self.jm_service.get_photo, photo_id)
            event.set_result(self._result(render_photo_detail(photo)))
        except (JmPluginError, JmPermissionError) as e:
            event.set_result(self._result(str(e)))
        except Exception as e:  # pragma: no cover
            logger.exception("jmphoto failed: %s", e)
            event.set_result(self._result(f"查询章节失败: {e}"))

    @filter.command("jmrank")
    async def jm_rank(self, event: AstrMessageEvent, rank_name: str = "month") -> None:
        try:
            self._ensure_read_allowed(event)
            page = await asyncio.to_thread(self.jm_service.rank, rank_name)
            event.set_result(self._result(render_rank_page(page, rank_name)))
        except (JmPluginError, JmPermissionError) as e:
            event.set_result(self._result(str(e)))
        except Exception as e:  # pragma: no cover
            logger.exception("jmrank failed: %s", e)
            event.set_result(self._result(f"查询排行失败: {e}"))

    @filter.command("jm下载", alias={"jmdownload"})
    async def jm_download(self, event: AstrMessageEvent, arg1: str, arg2: str = "") -> None:
        try:
            self._ensure_download_allowed(event)
            if arg2:
                output_format = arg1
                album_id = arg2
            else:
                output_format = self._default_download_format()
                album_id = arg1

            record = self.task_manager.create_task(
                task_type="album_download",
                target_id=album_id,
                requested_by=event.get_sender_id(),
                request_origin=event.unified_msg_origin,
                output_format=output_format,
            )
            task_cache_dir = self.cache_manager.build_task_cache_dir(record.task_id)
            asyncio.create_task(
                self._run_and_upload(
                    event,
                    record,
                    self.jm_service.download_album,
                    album_id,
                    output_format,
                    str(task_cache_dir),
                )
            )
            event.set_result(
                self._result(
                    f"下载任务已创建，完成后将上传到当前平台。\n"
                    f"任务ID: {record.task_id}\n类型: 本子下载\n目标ID: {album_id}\n格式: {output_format}"
                )
            )
        except (JmPluginError, JmPermissionError) as e:
            event.set_result(self._result(str(e)))

    @filter.command("jm下载章节", alias={"jmchapterdownload"})
    async def jm_download_photo(self, event: AstrMessageEvent, arg1: str, arg2: str = "") -> None:
        try:
            self._ensure_download_allowed(event)
            if arg2:
                output_format = arg1
                photo_id = arg2
            else:
                output_format = self._default_download_format()
                photo_id = arg1

            record = self.task_manager.create_task(
                task_type="photo_download",
                target_id=photo_id,
                requested_by=event.get_sender_id(),
                request_origin=event.unified_msg_origin,
                output_format=output_format,
            )
            task_cache_dir = self.cache_manager.build_task_cache_dir(record.task_id)
            asyncio.create_task(
                self._run_and_upload(
                    event,
                    record,
                    self.jm_service.download_photo,
                    photo_id,
                    output_format,
                    str(task_cache_dir),
                )
            )
            event.set_result(
                self._result(
                    f"下载任务已创建，完成后将上传到当前平台。\n"
                    f"任务ID: {record.task_id}\n类型: 章节下载\n目标ID: {photo_id}\n格式: {output_format}"
                )
            )
        except (JmPluginError, JmPermissionError) as e:
            event.set_result(self._result(str(e)))
