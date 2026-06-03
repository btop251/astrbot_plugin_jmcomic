from __future__ import annotations

import math
from typing import Iterable

from .exceptions import JmPluginError
from .models import JmTaskRecord


def _album_authors(album) -> str:
    return ", ".join(album.authors) if getattr(album, "authors", None) else "未知"


def _album_tags(album, limit: int = 8) -> str:
    return ", ".join(album.tags[:limit]) if getattr(album, "tags", None) else "无"


def _normalize_page(page: int, total_pages: int) -> int:
    if page < 1:
        raise JmPluginError("页码不能小于 1。")
    if total_pages > 0 and page > total_pages:
        raise JmPluginError(f"页码超出范围，当前共有 {total_pages} 页。")
    return page


def _chapter_tuple_at(album, index: int) -> tuple[str, str, str]:
    item = album.episode_list[index]
    photo_id = str(item[0])
    chapter_index = str(item[1])
    title = str(item[2]).strip() if len(item) >= 3 else ""
    return photo_id, chapter_index, title or "未命名章节"


def render_album_chapter_page(album, page: int = 1, page_size: int = 10, include_header: bool = True) -> str:
    page_size = max(1, page_size)
    total = len(album)
    total_pages = max(1, math.ceil(total / page_size))
    page = _normalize_page(page, total_pages)

    start = (page - 1) * page_size
    end = min(start + page_size, total)
    lines: list[str] = []

    if include_header:
        lines.extend(
            [
                "漫画章节列表",
                f"本子ID: {album.id}",
                f"标题: {album.name}",
                f"总章节: {total}",
                f"当前页: {page}/{total_pages}",
                "",
            ]
        )
    else:
        lines.append(f"章节列表: {page}/{total_pages}")

    if total == 0:
        lines.append("无章节信息。")
    else:
        for idx in range(start, end):
            photo_id, chapter_index, title = _chapter_tuple_at(album, idx)
            lines.append(f"{chapter_index}. {photo_id} | {title}")

    lines.extend(
        [
            "",
            f"翻页: /jm章节列表 {album.id} <页码>",
            f"按序号选章: /jm章节 {album.id} <序号>",
        ]
    )
    return "\n".join(lines)


def render_album_detail(album, page: int = 1, page_size: int = 10) -> str:
    chapter_text = render_album_chapter_page(album, page, page_size, include_header=False)
    download_hint = (
        f"/jm下载 pdf {album.episode_list[0][0]}"
        if len(album) >= 1 and getattr(album, "episode_list", None)
        else "/jm下载 pdf <photo_id>"
    )
    return (
        f"本子详情\n"
        f"ID: {album.id}\n"
        f"标题: {album.name}\n"
        f"作者: {_album_authors(album)}\n"
        f"章节数: {len(album)}\n"
        f"页数: {getattr(album, 'page_count', '未知')}\n"
        f"标签: {_album_tags(album)}\n"
        f"\n{chapter_text}\n"
        f"\n单章下载: {download_hint}\n"
        f"整本下载: /jm下载整本 pdf {album.id}"
    )


def render_photo_detail(photo) -> str:
    return (
        f"章节详情\n"
        f"ID: {photo.id}\n"
        f"所属本子: {photo.album_id}\n"
        f"标题: {photo.name}\n"
        f"图片数: {len(photo)}\n"
        f"章节序号: {getattr(photo, 'album_index', '未知')}\n"
        f"下载命令: /jm下载 pdf {photo.id}"
    )


def render_chapter_pick(album, chapter_index: int) -> str:
    if chapter_index < 1:
        raise JmPluginError("章节序号必须是正整数。")

    for idx in range(len(album)):
        photo_id, current_index, title = _chapter_tuple_at(album, idx)
        try:
            current_index_number = int(current_index)
        except ValueError:
            continue

        if current_index_number == chapter_index:
            return (
                f"章节详情\n"
                f"本子ID: {album.id}\n"
                f"章节序号: {current_index}\n"
                f"章节ID: {photo_id}\n"
                f"标题: {title}\n"
                f"\n下载命令: /jm下载 pdf {photo_id}"
            )

    raise JmPluginError(f"未找到章节序号 {chapter_index}，请先使用 /jm章节列表 {album.id} 查看可用序号。")


def render_search_page(page, limit: int) -> str:
    lines = [f"搜索结果，共 {getattr(page, 'total', '未知')} 条，展示前 {limit} 条："]
    for idx, item in enumerate(list(page)[:limit], start=1):
        aid, title = item[0], item[1]
        lines.append(f"{idx}. {aid} | {title}")
    return "\n".join(lines)


def render_rank_page(page, rank_name: str, limit: int = 10) -> str:
    lines = [f"{rank_name} 排行，展示前 {limit} 条："]
    for idx, item in enumerate(list(page)[:limit], start=1):
        aid, title = item[0], item[1]
        lines.append(f"{idx}. {aid} | {title}")
    return "\n".join(lines)


def render_task_list(tasks: Iterable[JmTaskRecord]) -> str:
    task_list = list(tasks)
    if not task_list:
        return "当前没有任务记录。"
    lines = ["任务列表："]
    for task in task_list:
        lines.append(
            f"{task.task_id} | {task.task_type} | {task.target_id} | {task.output_format or '-'} | {task.status}"
        )
    return "\n".join(lines)


def render_task_detail(task: JmTaskRecord) -> str:
    return (
        f"任务详情\n"
        f"任务ID: {task.task_id}\n"
        f"类型: {task.task_type}\n"
        f"目标ID: {task.target_id}\n"
        f"输出格式: {task.output_format or '-'}\n"
        f"状态: {task.status}\n"
        f"是否已上传: {'是' if task.uploaded else '否'}\n"
        f"创建时间: {task.created_at}\n"
        f"开始时间: {task.started_at or '-'}\n"
        f"完成时间: {task.finished_at or '-'}\n"
        f"保存目录: {task.save_dir or '-'}\n"
        f"结果摘要: {task.summary or '-'}\n"
        f"错误类型: {task.error_type or '-'}\n"
        f"错误信息: {task.error_message or '-'}"
    )
