from __future__ import annotations

import asyncio
from pathlib import Path

from astrbot.api import logger, star
from astrbot.api.event import AstrMessageEvent, MessageChain, MessageEventResult, filter
from astrbot.api.message_components import File, Image, Node, Nodes, Plain

from .core.cache_manager import CacheManager
from .core.config_mapper import ConfigMapper
from .core.exceptions import JmPermissionError, JmPluginError, JmTaskNotFoundError
from .core.jm_service import JmService
from .core.parsers import GreedyStr
from .core.renderers import (
    render_album_chapter_page,
    render_album_detail,
    render_chapter_pick,
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

    def _album_chapter_page_size(self) -> int:
        return max(1, int(get_setting(self.config, "album_chapter_page_size", 10) or 10))

    def _parse_positive_int(self, value: str, label: str) -> int:
        try:
            number = int(str(value).strip())
        except ValueError as e:
            raise JmPluginError(f"{label}必须是正整数。") from e
        if number < 1:
            raise JmPluginError(f"{label}必须是正整数。")
        return number

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

    def _cover_cache_path(self, album_id: str) -> Path:
        return self.data_dir / "covers" / f"{album_id}.jpg"

    async def _build_album_cover_image(self, album_id: str, cover_mode: str) -> Image | None:
        if cover_mode in {"", "none", "off", "false"}:
            return None

        if cover_mode != "download":
            image = Image.fromURL(self.jm_service.get_album_cover_url(album_id))
        else:
            cover_path = self._cover_cache_path(album_id)
            await asyncio.to_thread(self.jm_service.download_album_cover, album_id, str(cover_path))
            if not cover_path.exists() or cover_path.stat().st_size == 0:
                raise JmPluginError("封面缓存文件不存在或为空。")
            image = Image.fromFileSystem(str(cover_path))

        return image

    def _build_album_node(self, event: AstrMessageEvent, content: list) -> Node:
        return Node(
            content=content,
            uin=str(event.get_self_id() or event.get_sender_id() or "0"),
            name="JMComic",
        )

    async def _send_album_result(
        self,
        event: AstrMessageEvent,
        album,
        text: str,
    ) -> None:
        cover_mode = str(get_setting(self.config, "cover_send_mode", "url")).strip().lower()
        text_node = self._build_album_node(event, [Plain(text)])
        cover_node = None

        try:
            cover_image = await self._build_album_cover_image(str(album.id), cover_mode)
            if cover_image is not None:
                cover_node = self._build_album_node(event, [cover_image])
        except Exception as e:  # pragma: no cover
            logger.warning("album cover node skipped, text will still be sent: %s", e)

        if cover_node is not None:
            try:
                await event.send(MessageChain([Nodes([cover_node, text_node])], use_t2i_=False))
                event.stop_event()
                return
            except Exception as e:  # pragma: no cover
                logger.warning("album forward with cover failed, retrying text-only forward: %s", e)

        try:
            await event.send(MessageChain([Nodes([text_node])], use_t2i_=False))
        except Exception as e:  # pragma: no cover
            logger.warning("album text forward failed, fallback to plain text: %s", e)
            await event.send(MessageChain([Plain(text)], use_t2i_=False))

        event.stop_event()

    def _start_download_task(
        self,
        event: AstrMessageEvent,
        task_type: str,
        target_id: str,
        output_format: str,
        func,
    ):
        record = self.task_manager.create_task(
            task_type=task_type,
            target_id=target_id,
            requested_by=event.get_sender_id(),
            request_origin=event.unified_msg_origin,
            output_format=output_format,
        )
        task_cache_dir = self.cache_manager.build_task_cache_dir(record.task_id)
        asyncio.create_task(
            self._run_and_upload(
                event,
                record,
                func,
                target_id,
                output_format,
                str(task_cache_dir),
            )
        )
        return record

    def _is_task_cancelled(self, task_id: str) -> bool:
        try:
            task = self.task_manager.get_task(task_id)
        except JmTaskNotFoundError:
            return False
        return task.cancel_requested or task.status == "cancelled"

    async def _mark_upload_cancelled(self, event: AstrMessageEvent, task_id: str) -> None:
        task = self.task_manager.get_task(task_id)
        task.cancel_requested = True
        task.status = "cancelled"
        task.summary = (task.summary or "").strip() + "；已按停止请求中断后续上传"
        self.state_store.save_tasks(self.task_manager.tasks)
        await self._send_text_proactively(
            event,
            f"任务已按停止请求中断后续上传。\n任务ID: {task_id}",
        )

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

    async def _send_pdf(self, event: AstrMessageEvent, task_id: str, pdf_path: str) -> bool:
        if self._is_task_cancelled(task_id):
            await self._mark_upload_cancelled(event, task_id)
            return False

        await self._send_text_proactively(
            event,
            f"下载完成，正在回传 PDF。\n任务ID: {task_id}",
        )

        if self._is_task_cancelled(task_id):
            await self._mark_upload_cancelled(event, task_id)
            return False

        # NapCat / OneBot 场景优先走原生文件上传 action，避免 file 段被当成异常消息处理。
        if event.get_platform_name() == "aiocqhttp":
            await self._upload_pdf_via_aiocqhttp(event, pdf_path)
            return True

        payload = MessageEventResult().use_t2i(False)
        payload.chain.append(File(name=Path(pdf_path).name, file=pdf_path))
        ok = await self.context.send_message(event.unified_msg_origin, payload)
        if not ok:
            raise JmPluginError("主动发送 PDF 失败：未找到可用平台或会话。")
        return True

    async def _send_images(self, event: AstrMessageEvent, task_id: str, image_files: list[str]) -> bool:
        batch_size = int(get_setting(self.config, "image_batch_size", 10) or 10)
        total = len(image_files)

        if self._is_task_cancelled(task_id):
            await self._mark_upload_cancelled(event, task_id)
            return False

        await self._send_text_proactively(
            event,
            f"下载完成，开始回传图片。\n任务ID: {task_id}\n图片数: {total}",
        )

        for start in range(0, total, batch_size):
            if self._is_task_cancelled(task_id):
                await self._mark_upload_cancelled(event, task_id)
                return False

            batch = image_files[start : start + batch_size]
            payload = MessageEventResult().use_t2i(False)
            for image_path in batch:
                payload.chain.append(Image.fromFileSystem(image_path))
            ok = await self.context.send_message(event.unified_msg_origin, payload)
            if not ok:
                raise JmPluginError("主动发送图片失败：未找到可用平台或会话。")
            await asyncio.sleep(0.5)
        return True

    async def _upload_result(self, event: AstrMessageEvent, task_id: str, result: dict) -> bool:
        result_type = str(result.get("result_type", "raw"))
        if result_type == "pdf":
            return await self._send_pdf(event, task_id, str(result["pdf_path"]))

        image_files = list(result.get("image_files", []))
        if not image_files:
            raise JmPluginError("下载结果中没有可上传的图片。")
        return await self._send_images(event, task_id, image_files)

    async def _run_and_upload(self, event: AstrMessageEvent, record, func, *args) -> None:
        result = await self.task_manager.run_task(record, func, *args)
        refreshed = self.task_manager.get_task(record.task_id)

        if refreshed.status != "success":
            await self._send_text_proactively(
                event,
                f"任务未完成。\n任务ID: {refreshed.task_id}\n"
                f"状态: {refreshed.status}\n"
                f"错误类型: {refreshed.error_type or '-'}\n错误信息: {refreshed.error_message or '-'}",
            )
            self.cache_manager.prune(list(self.task_manager.tasks.values()))
            return

        try:
            refreshed = self.task_manager.get_task(record.task_id)
            if refreshed.cancel_requested:
                refreshed.status = "cancelled"
                refreshed.summary = (refreshed.summary or "").strip() + "；已跳过上传"
                self.state_store.save_tasks(self.task_manager.tasks)
                await self._send_text_proactively(
                    event,
                    f"任务已按停止请求结束，未上传结果。\n任务ID: {refreshed.task_id}",
                )
                return

            uploaded = await self._upload_result(event, refreshed.task_id, result or {})
            if not uploaded:
                return

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
            "/jmalbum <album_id> [页码]\n"
            "/jm章节列表 <album_id> [页码]\n"
            "/jm章节 <album_id> <章节序号>\n"
            "/jmphoto <photo_id>\n"
            "/jmrank <month|week|day>\n"
            "/jm下载 [原图|jpg|png|pdf] <photo_id>\n"
            "/jm下载整本 [原图|jpg|png|pdf] <album_id>\n"
            "/jm下载章节 [原图|jpg|png|pdf] <photo_id>\n"
            "/jm任务\n"
            "/jm任务详情 <task_id>\n"
            "/jm停止 <task_id>\n"
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

    @filter.command("jm停止", alias={"jmcancel"})
    async def jm_task_cancel(self, event: AstrMessageEvent, task_id: str) -> None:
        try:
            self._ensure_download_allowed(event)
            if not bool(get_setting(self.config, "enable_task_cancel", True)):
                raise JmPluginError("当前配置未启用任务停止命令。")
            task = self.task_manager.cancel_task(task_id)
            event.set_result(
                self._result(
                    f"任务停止请求已记录。\n任务ID: {task.task_id}\n状态: {task.status}\n说明: {task.summary or '-'}"
                )
            )
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
    async def jm_album(self, event: AstrMessageEvent, album_id: str, page: str = "1") -> None:
        try:
            self._ensure_read_allowed(event)
            page_number = self._parse_positive_int(page, "页码")
            album = await asyncio.to_thread(self.jm_service.get_album, album_id)
            text = render_album_detail(album, page_number, self._album_chapter_page_size())
            await self._send_album_result(event, album, text)
        except (JmPluginError, JmPermissionError) as e:
            event.set_result(self._result(str(e)))
        except Exception as e:  # pragma: no cover
            logger.exception("jmalbum failed: %s", e)
            event.set_result(self._result(f"查询本子失败: {e}"))

    @filter.command("jm章节列表", alias={"jmchapters"})
    async def jm_chapter_list(self, event: AstrMessageEvent, album_id: str, page: str = "1") -> None:
        try:
            self._ensure_read_allowed(event)
            page_number = self._parse_positive_int(page, "页码")
            album = await asyncio.to_thread(self.jm_service.get_album, album_id)
            event.set_result(
                self._result(render_album_chapter_page(album, page_number, self._album_chapter_page_size()))
            )
        except (JmPluginError, JmPermissionError) as e:
            event.set_result(self._result(str(e)))
        except Exception as e:  # pragma: no cover
            logger.exception("jmchapters failed: %s", e)
            event.set_result(self._result(f"查询章节列表失败: {e}"))

    @filter.command("jm章节", alias={"jmchapter"})
    async def jm_chapter_pick(self, event: AstrMessageEvent, album_id: str, chapter_index: str) -> None:
        try:
            self._ensure_read_allowed(event)
            index_number = self._parse_positive_int(chapter_index, "章节序号")
            album = await asyncio.to_thread(self.jm_service.get_album, album_id)
            event.set_result(self._result(render_chapter_pick(album, index_number)))
        except (JmPluginError, JmPermissionError) as e:
            event.set_result(self._result(str(e)))
        except Exception as e:  # pragma: no cover
            logger.exception("jmchapter failed: %s", e)
            event.set_result(self._result(f"查询章节失败: {e}"))

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
                photo_id = arg2
            else:
                output_format = self._default_download_format()
                photo_id = arg1

            record = self._start_download_task(
                event=event,
                task_type="photo_download",
                target_id=photo_id,
                output_format=output_format,
                func=self.jm_service.download_photo,
            )
            event.set_result(
                self._result(
                    f"下载任务已创建，完成后将上传到当前平台。\n"
                    f"任务ID: {record.task_id}\n类型: 章节下载\n目标ID: {photo_id}\n格式: {output_format}"
                )
            )
        except (JmPluginError, JmPermissionError) as e:
            event.set_result(self._result(str(e)))
        except Exception as e:  # pragma: no cover
            logger.exception("jmdownload failed: %s", e)
            event.set_result(self._result(f"创建下载任务失败: {e}"))

    @filter.command("jm下载整本", alias={"jmalbumdownload"})
    async def jm_download_album(self, event: AstrMessageEvent, arg1: str, arg2: str = "") -> None:
        try:
            self._ensure_download_allowed(event)
            if arg2:
                output_format = arg1
                album_id = arg2
            else:
                output_format = self._default_download_format()
                album_id = arg1

            record = self._start_download_task(
                event=event,
                task_type="album_download",
                target_id=album_id,
                output_format=output_format,
                func=self.jm_service.download_album,
            )
            event.set_result(
                self._result(
                    f"整本下载任务已创建，完成后将上传到当前平台。\n"
                    f"任务ID: {record.task_id}\n类型: 整本下载\n目标ID: {album_id}\n格式: {output_format}"
                )
            )
        except (JmPluginError, JmPermissionError) as e:
            event.set_result(self._result(str(e)))
        except Exception as e:  # pragma: no cover
            logger.exception("jmalbumdownload failed: %s", e)
            event.set_result(self._result(f"创建整本下载任务失败: {e}"))

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

            record = self._start_download_task(
                event=event,
                task_type="photo_download",
                target_id=photo_id,
                output_format=output_format,
                func=self.jm_service.download_photo,
            )
            event.set_result(
                self._result(
                    f"下载任务已创建，完成后将上传到当前平台。\n"
                    f"任务ID: {record.task_id}\n类型: 章节下载\n目标ID: {photo_id}\n格式: {output_format}"
                )
            )
        except (JmPluginError, JmPermissionError) as e:
            event.set_result(self._result(str(e)))
        except Exception as e:  # pragma: no cover
            logger.exception("jmchapterdownload failed: %s", e)
            event.set_result(self._result(f"创建章节下载任务失败: {e}"))
