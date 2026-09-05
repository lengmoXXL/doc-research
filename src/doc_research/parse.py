"""用阿里云 DocMind 将本地文档（PDF、EPUB 等）转换为 Markdown，并裁剪出图片。"""

import json
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path
from urllib.request import urlopen

from alibabacloud_docmind_api20220711 import models as docmind_models
from alibabacloud_docmind_api20220711.client import Client as DocMindClient
from alibabacloud_tea_openapi import models as open_api_models
from darabonba.runtime import RuntimeOptions
from dotenv import load_dotenv
from PIL import Image

DOCMIND_ENDPOINT = "docmind-api.cn-hangzhou.aliyuncs.com"
POLL_INTERVAL_SECONDS = 5.0
TIMEOUT_SECONDS = 1800.0


def run(args) -> int:
    load_dotenv(Path.cwd() / ".env")

    doc_path = Path(args.file_path).expanduser().resolve()
    if not doc_path.is_file():
        print(f"文件不存在：{doc_path}", file=sys.stderr)
        return 1

    try:
        access_key_id = os.environ["ALIBABA_CLOUD_ACCESS_KEY_ID"]
        access_key_secret = os.environ["ALIBABA_CLOUD_ACCESS_KEY_SECRET"]
    except KeyError as error:
        key = error.args[0]
        print(f"缺少凭据 {key}：设为环境变量，或写入当前目录的 .env", file=sys.stderr)
        return 1

    output_dir = (
        Path(args.output).expanduser().resolve() if args.output else Path.cwd() / doc_path.stem
    )

    with tempfile.TemporaryDirectory(prefix="pdf-markdown-") as temp_dir:
        temp_path = Path(temp_dir)
        pages_dir = temp_path / "pages"
        result_dir = temp_path / "result"
        images_dir = result_dir / "images"
        pages_dir.mkdir()
        images_dir.mkdir(parents=True)

        config = open_api_models.Config(
            access_key_id=access_key_id,
            access_key_secret=access_key_secret,
        )
        config.endpoint = DOCMIND_ENDPOINT
        client = DocMindClient(config)

        print(f"提交 DocMind 任务：{doc_path} ...")
        with doc_path.open("rb") as doc_file:
            request = docmind_models.SubmitDocParserJobAdvanceRequest(
                file_name=doc_path.name,
                file_name_extension=doc_path.suffix.lstrip("."),
                file_url_object=doc_file,
                formula_enhancement=True,
                output_format=["visualLayoutInfo"],
                llm_enhancement=True,
            )
            request.enhancement_mode = "VLM"
            response = client.submit_doc_parser_job_advance(request, RuntimeOptions())
        job_id = response.body.data.id
        if not job_id:
            print("DocMind 未返回任务 ID", file=sys.stderr)
            return 1
        print(f"任务 ID：{job_id}")

        started_at = time.monotonic()
        while True:
            response = client.query_doc_parser_status(
                docmind_models.QueryDocParserStatusRequest(id=job_id)
            )
            status_data = response.body.data.to_map()
            status = status_data["Status"]
            progress = status_data["Processing"]
            print(f"状态：{status}" + (f"（{progress}%）" if progress is not None else ""))

            if status == "success":
                break
            if status == "fail":
                print(json.dumps(status_data, ensure_ascii=False, indent=2), file=sys.stderr)
                return 1
            if time.monotonic() - started_at >= TIMEOUT_SECONDS:
                print(f"超时（{TIMEOUT_SECONDS:.0f} 秒）", file=sys.stderr)
                return 1
            time.sleep(POLL_INTERVAL_SECONDS)

        output_format_result = status_data.get("OutputFormatResult") or []
        page_records = output_format_result[0]["Pages"] if output_format_result else []

        layouts = []
        layout_offset = 0
        layout_step_size = 300
        while True:
            response = client.get_doc_parser_result(
                docmind_models.GetDocParserResultRequest(
                    id=job_id,
                    layout_num=layout_offset,
                    layout_step_size=layout_step_size,
                )
            )
            batch = (response.body.data or {}).get("layouts")
            if not batch:
                break
            layouts.extend(batch)
            layout_offset += len(batch)
            if len(batch) < layout_step_size:
                break

        figure_pages = {layout["pageNum"] for layout in layouts if layout["type"] == "figure"}
        pages_by_number = {}
        for page in page_records:
            page_number = page["PageIdCurDoc"]
            if page_number not in figure_pages:
                continue
            page_path = pages_dir / f"page-{page_number:04d}"
            with urlopen(page["ImageUrl"], timeout=120) as source, page_path.open("wb") as target:
                shutil.copyfileobj(source, target)
            pages_by_number[page_number] = {
                "path": page_path,
                "width": page["ImageWidth"],
                "height": page["ImageHeight"],
            }

        local_markdown = []
        figure_number = 0
        for layout in layouts:
            layout_type = layout["type"]
            if layout_type != "figure":
                text = layout["markdownContent"]
                if text:
                    local_markdown.append(text)
                continue
            page_number = layout["pageNum"]
            points = layout["pos"]

            page_info = pages_by_number[page_number]

            xs = [point["x"] for point in points]
            ys = [point["y"] for point in points]
            with Image.open(page_info["path"]) as page_image:
                source_width = page_info["width"]
                source_height = page_info["height"]
                box = (
                    round(min(xs) * page_image.width / source_width),
                    round(min(ys) * page_image.height / source_height),
                    round(max(xs) * page_image.width / source_width),
                    round(max(ys) * page_image.height / source_height),
                )
                figure_number += 1
                image_path = images_dir / f"{layout_type}-{figure_number:04d}.png"
                page_image.crop(box).save(image_path)
                local_image = image_path.relative_to(result_dir).as_posix()
                local_markdown.append(f"![{layout_type}]({local_image})")

        rendered_markdown = (
            "\n\n".join(block.rstrip("\n") for block in local_markdown).strip() + "\n"
        )
        (result_dir / "raw.md").write_text(rendered_markdown, encoding="utf-8")

        output_dir.mkdir(parents=True, exist_ok=True)

        # 只覆盖脚本产物（raw.md、images/），输出目录下的其它文件不动
        target_raw = output_dir / "raw.md"
        target_images = output_dir / "images"
        if target_raw.exists():
            target_raw.unlink()
        if target_images.exists():
            shutil.rmtree(target_images)

        shutil.move(str(result_dir / "raw.md"), str(target_raw))
        shutil.move(str(result_dir / "images"), str(target_images))

    print(f"已保存到 {output_dir}")
    print(f"- Markdown：{output_dir / 'raw.md'}")
    print(f"- 裁剪图片：{output_dir / 'images'}（{figure_number} 张）")
    return 0
