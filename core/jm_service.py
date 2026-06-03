from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any

from .config_mapper import ConfigMapper
from .exceptions import JmImportError, JmPluginError
from .parsers import normalize_format_name, normalize_rank_name
from .settings import get_setting


class JmService:
    def __init__(self, mapper: ConfigMapper) -> None:
        self.mapper = mapper
        self.mapper.ensure_import_path()
        try:
            import jmcomic  # type: ignore
        except Exception as e:  # pragma: no cover
            raise JmImportError(f"导入 jmcomic 失败: {e}") from e

        self.jmcomic = jmcomic
        self.option_dict = mapper.build_option_dict()

    def create_option(self):
        return self.jmcomic.JmOption.construct(self.option_dict)

    def create_client(self, login_if_possible: bool = False):
        option = self.create_option()
        client = option.new_jm_client()
        if login_if_possible:
            username = str(get_setting(self.mapper.config, "username", "")).strip()
            password = str(get_setting(self.mapper.config, "password", "")).strip()
            if username and password:
                client.login(username, password)
        return option, client

    def get_album(self, album_id: str):
        _option, client = self.create_client(login_if_possible=True)
        return client.get_album_detail(album_id)

    def get_photo(self, photo_id: str):
        _option, client = self.create_client(login_if_possible=True)
        return client.get_photo_detail(photo_id)

    def search(self, query: str):
        _option, client = self.create_client(login_if_possible=True)
        return client.search_site(query)

    def rank(self, rank_name: str):
        _option, client = self.create_client(login_if_possible=True)
        normalized = normalize_rank_name(rank_name)
        if normalized == "month":
            return client.month_ranking(1)
        if normalized == "week":
            return client.week_ranking(1)
        if normalized == "day":
            return client.day_ranking(1)
        raise JmPluginError(f"不支持的排行类型: {rank_name}")

    def get_album_cover_url(self, album_id: str) -> str:
        return self.jmcomic.JmcomicText.get_album_cover_url(album_id)

    def download_album_cover(self, album_id: str, save_path: str) -> str:
        _option, client = self.create_client(login_if_possible=True)
        target_path = Path(save_path)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = target_path.with_name(f"{target_path.stem}.tmp{target_path.suffix or '.jpg'}")

        try:
            if temp_path.exists():
                temp_path.unlink()
            client.download_album_cover(album_id, str(temp_path))
            if not temp_path.exists() or temp_path.stat().st_size == 0:
                raise JmPluginError("封面下载失败：缓存文件不存在或为空。")
            if target_path.exists():
                target_path.unlink()
            os.replace(temp_path, target_path)
            return str(target_path)
        finally:
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except Exception:
                    pass

    def _build_download_option(self, output_format: str, base_dir: str | None = None):
        option = self.create_option()
        normalized = normalize_format_name(output_format)
        if base_dir:
            option.dir_rule.base_dir = base_dir

        if normalized == "jpg":
            option.download.image.suffix = ".jpg"
        elif normalized == "png":
            option.download.image.suffix = ".png"
        elif normalized == "raw":
            option.download.image.suffix = None
        elif normalized == "pdf":
            option.download.image.suffix = None
        else:
            raise JmPluginError(f"不支持的输出格式: {output_format}")
        return option, normalized

    def _collect_image_files(self, root_dir: Path) -> list[Path]:
        exts = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif"}
        files = [path for path in root_dir.rglob("*") if path.is_file() and path.suffix.lower() in exts]
        files.sort(key=lambda item: str(item))
        return files

    def _image_to_rgb(self, image):
        if image.mode == "RGB":
            return image
        if image.mode in {"RGBA", "LA"}:
            from PIL import Image

            background = Image.new("RGB", image.size, (255, 255, 255))
            alpha = image.getchannel("A") if "A" in image.getbands() else None
            background.paste(image, mask=alpha)
            return background
        return image.convert("RGB")

    def _save_image_batch_pdf(self, image_paths: list[Path], batch_pdf_path: Path) -> None:
        from PIL import Image

        if not image_paths:
            raise JmPluginError("批次 PDF 生成失败：当前批次没有图片。")

        converted_images = []
        try:
            for image_path in image_paths:
                with Image.open(image_path) as image:
                    converted = self._image_to_rgb(image)
                    if converted is image:
                        converted = image.copy()
                    converted_images.append(converted)

            first = converted_images[0]
            rest = converted_images[1:]
            batch_pdf_path.parent.mkdir(parents=True, exist_ok=True)
            first.save(
                batch_pdf_path,
                format="PDF",
                save_all=True,
                append_images=rest,
            )
        finally:
            for image in converted_images:
                try:
                    image.close()
                except Exception:
                    pass

    def _build_pdf(self, image_files: list[Path], pdf_path: Path) -> Path:
        if not image_files:
            raise JmPluginError("未找到可用于生成 PDF 的图片。")

        from pypdf import PdfReader, PdfWriter

        batch_size = int(get_setting(self.mapper.config, "pdf_merge_batch_size", 20) or 20)
        batch_size = max(1, batch_size)

        temp_pdf_path = pdf_path.with_name(f"{pdf_path.stem}.tmp.pdf")
        temp_batch_dir = pdf_path.parent / f".{pdf_path.stem}_batches_tmp"

        try:
            pdf_path.parent.mkdir(parents=True, exist_ok=True)
            if temp_pdf_path.exists():
                temp_pdf_path.unlink()
            if temp_batch_dir.exists():
                shutil.rmtree(temp_batch_dir, ignore_errors=True)
            temp_batch_dir.mkdir(parents=True, exist_ok=True)

            batch_pdf_files: list[Path] = []
            for start in range(0, len(image_files), batch_size):
                batch = image_files[start : start + batch_size]
                batch_index = start // batch_size + 1
                batch_pdf_path = temp_batch_dir / f"batch_{batch_index:04d}.pdf"
                self._save_image_batch_pdf(batch, batch_pdf_path)
                batch_pdf_files.append(batch_pdf_path)

            writer = PdfWriter()
            try:
                for batch_pdf in batch_pdf_files:
                    writer.append(str(batch_pdf))

                with open(temp_pdf_path, "wb") as fp:
                    writer.write(fp)
            finally:
                try:
                    writer.close()
                except Exception:
                    pass

            reader = PdfReader(str(temp_pdf_path))
            if len(reader.pages) == 0:
                raise JmPluginError("PDF 生成失败：生成结果没有任何页面。")

            if pdf_path.exists():
                pdf_path.unlink()
            os.replace(temp_pdf_path, pdf_path)
            return pdf_path
        finally:
            if temp_pdf_path.exists():
                try:
                    temp_pdf_path.unlink()
                except Exception:
                    pass
            if temp_batch_dir.exists():
                shutil.rmtree(temp_batch_dir, ignore_errors=True)

    def download_album(self, album_id: str, output_format: str, base_dir: str | None = None) -> dict[str, Any]:
        option, normalized = self._build_download_option(output_format, base_dir)
        album, _dler = self.jmcomic.download_album(album_id, option=option)
        save_dir = option.dir_rule.decide_album_root_dir(album)
        result: dict[str, Any] = {
            "save_dir": save_dir,
            "summary": f"本子 {album.id} 下载完成",
            "result_type": normalized,
        }

        if normalized == "pdf":
            album_root = Path(save_dir)
            pdf_path = self._build_pdf(
                self._collect_image_files(album_root),
                album_root / f"{album.id}.pdf",
            )
            result["pdf_path"] = str(pdf_path)
            result["save_dir"] = str(album_root)
            result["summary"] = f"本子 {album.id} 下载并生成 PDF 完成"
            return result

        result["image_files"] = [str(path) for path in self._collect_image_files(Path(save_dir))]
        return result

    def download_photo(self, photo_id: str, output_format: str, base_dir: str | None = None) -> dict[str, Any]:
        option, normalized = self._build_download_option(output_format, base_dir)
        photo, _dler = self.jmcomic.download_photo(photo_id, option=option)
        save_dir = option.decide_image_save_dir(photo)
        result: dict[str, Any] = {
            "save_dir": save_dir,
            "summary": f"章节 {photo.id} 下载完成",
            "result_type": normalized,
        }

        if normalized == "pdf":
            photo_root = Path(save_dir)
            pdf_path = self._build_pdf(
                self._collect_image_files(photo_root),
                photo_root / f"{photo.id}.pdf",
            )
            result["pdf_path"] = str(pdf_path)
            result["save_dir"] = str(photo_root)
            result["summary"] = f"章节 {photo.id} 下载并生成 PDF 完成"
            return result

        result["image_files"] = [str(path) for path in self._collect_image_files(Path(save_dir))]
        return result
