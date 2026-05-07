from __future__ import annotations

from typing import Iterable

from .models import JmTaskRecord


def render_album_detail(album) -> str:
    photo_lines = []
    for idx, photo in enumerate(list(album)[:5], start=1):
        photo_lines.append(f"{idx}. {photo.id} | {photo.name}")
    photo_text = "\n".join(photo_lines) if photo_lines else "无章节信息"
    return (
        f"本子详情\n"
        f"ID: {album.id}\n"
        f"标题: {album.name}\n"
        f"作者: {', '.join(album.authors) if getattr(album, 'authors', None) else '未知'}\n"
        f"章节数: {len(album)}\n"
        f"页数: {getattr(album, 'page_count', '未知')}\n"
        f"标签: {', '.join(album.tags[:8]) if getattr(album, 'tags', None) else '无'}\n"
        f"前5章:\n{photo_text}"
    )


def render_photo_detail(photo) -> str:
    return (
        f"章节详情\n"
        f"ID: {photo.id}\n"
        f"所属本子: {photo.album_id}\n"
        f"标题: {photo.name}\n"
        f"图片数: {len(photo)}\n"
        f"章节序号: {getattr(photo, 'album_index', '未知')}"
    )


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
