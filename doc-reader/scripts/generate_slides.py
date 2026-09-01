#!/usr/bin/env python3
"""并发调用 Codex CLI 生成 Doc Reader 幻灯片图片。

脚本读取 ``slides_metadata.json``，为每张幻灯片构建提示词，并为每张图
启动一个独立的 ``codex exec`` 会话，默认 4 路并发。每个会话调用内置
``$imagegen`` skill，把结果写入临时目录。Codex 将 image_gen 产物落在
``$CODEX_HOME/generated_images/<会话 id>/`` 下，会话之间目录天然隔离，
因此并发不会互相挑错图片。全部图片校验通过后，脚本才会替换
``slides/slide_*.png``，避免失败时留下半套新产物。

前置条件：
    1. ``codex`` 已安装并位于 PATH；
    2. Codex CLI 已登录；
    3. 当前 Codex 版本和账号可使用内置 imagegen。

用法：
    python3 generate_slides.py
    python3 generate_slides.py -j 2      # 降低并发
    python3 generate_slides.py --dry-run
"""

import argparse
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import zlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Optional


DEFAULT_ASPECT_RATIO = "16:9"
TIMEOUT_PER_SLIDE_SECONDS = 900
DEFAULT_CONCURRENCY = 4
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"

ACCENT_COLORS = {
    "intro": "柔和橙黄色（#F5A623）作为主强调色",
    "problem": "柔和珊瑚红（#E57373）作为警示强调色",
    "solution": "柔和青绿色（#4DB6AC）作为正向强调色",
    "feature": "柔和蓝色（#64B5F6）作为科技感强调色",
    "benefit": "暖金黄色（#FFD54F）作为成功强调色",
    "example": "柔和薰衣草紫（#B39DDB）作为案例强调色",
    "tip": "琥珀橙色（#FFB74D）作为提示强调色",
    "conclusion": "柔和青绿与橙色作为总结强调色",
}

# 画面可见汉字预算。实测（2026-08-31，gpt-image-2 内置路径，每臂 n=4）：
# ≤120 字与 ~270 字的中文简报均 0 字形错误，~440 字整段原文 0.6 错/图，
# ChatGPT 网页版同提示词自动压缩到 140–284 字后也是 0 错。250 取安全区间上沿。
VISIBLE_CJK_BUDGET = 250


def slide_content(slide: dict) -> str:
    """兼容当前 ``description`` 合同，并读取旧数据中的 ``content``。"""
    return str(slide.get("description") or slide.get("content") or "").strip()


def build_image_prompt(
    slide: dict,
    article_title: str,
    aspect_ratio: str = DEFAULT_ASPECT_RATIO,
) -> str:
    """把一个内容块写成给 imagegen 的中文创作简报。

    原文只作素材，由图片模型提炼；关键约束是可见汉字预算——
    字形错误随画面汉字数上升，而渲染档位不受提示词控制。
    """
    slide_type = str(slide.get("type") or "feature")
    title = str(slide.get("title") or f"幻灯片 {slide.get('index', '')}").strip()
    section = str(slide.get("section") or "").strip() or title
    content = slide_content(slide)
    index = slide.get("index", 1)
    accent = ACCENT_COLORS.get(slide_type, ACCENT_COLORS["feature"])

    return f"""请画一张 {aspect_ratio} 的技术文章总结幻灯片（同一系列的第 {index} 张），风格是温暖的手绘知识地图，像 Notion 模板那种教育类信息图：米色纸质背景（#F5F0E6），深咖啡色（#5D4037）的标题、线条和简笔画图标，统一的细线条手绘图标，圆角卡片、柔和阴影、虚线箭头，模块化布局、层级清晰、留白充足，点缀少量{accent}。不要霓虹色、不要写实照片、不要 3D、不要 logo 和水印。所有可见文字都用简体中文，标题只出现一次："{title}"。

内容来自文章《{article_title}》的章节「{section}」。下面是原文，它是素材，不是要照抄到画面上的文字：
{content}

排版要求（最重要）：
- 先从原文提炼 3-5 个核心概念，组织成清晰的层级或流程，用视觉隐喻代替大段文字
- 画面上所有可见汉字总量不超过 {VISIBLE_CJK_BUDGET} 个：每个概念一个 8 字以内的短标签，可配一句 20 字以内的说明；数字、专有名词、人名保留原样
- 不要把原文整段抄上去；宁可少写字，也不要写小字
- 忠实于原文，不要编造事实、数据或品牌
""".strip()


def validate_slides(slides: list[dict]) -> Optional[str]:
    """在启动昂贵的图片生成前校验索引和必要内容。"""
    if not slides:
        return "没有找到幻灯片数据"

    seen_indexes: set[int] = set()
    for position, slide in enumerate(slides, start=1):
        if not isinstance(slide, dict):
            return f"第 {position} 个内容块必须是对象"
        index = slide.get("index")
        if not isinstance(index, int) or isinstance(index, bool) or index <= 0:
            return f"第 {position} 个内容块的 index 必须是正整数"
        if index in seen_indexes:
            return f"幻灯片 index 重复: {index}"
        seen_indexes.add(index)
        if not str(slide.get("title") or "").strip():
            return f"幻灯片 {index} 缺少 title"
        if not slide_content(slide):
            return f"幻灯片 {index} 缺少 description/content"
    return None


def validate_png(path: Path) -> Optional[str]:
    """用标准库校验 PNG 结构、CRC、尺寸和必要数据块。"""
    if not path.is_file():
        return "文件不存在"
    if path.stat().st_size < 45:
        return "文件过小，不是有效 PNG"

    data = path.read_bytes()
    if data[:8] != PNG_SIGNATURE:
        return "文件签名不是 PNG"

    offset = len(PNG_SIGNATURE)
    seen_ihdr = False
    seen_idat = False
    seen_iend = False
    try:
        while offset < len(data):
            if offset + 12 > len(data):
                return "PNG 数据块被截断"
            chunk_length = struct.unpack(">I", data[offset : offset + 4])[0]
            chunk_type = data[offset + 4 : offset + 8]
            chunk_end = offset + 12 + chunk_length
            if chunk_end > len(data):
                return "PNG 数据块长度越界"

            chunk_data = data[offset + 8 : offset + 8 + chunk_length]
            expected_crc = struct.unpack(">I", data[chunk_end - 4 : chunk_end])[0]
            actual_crc = zlib.crc32(chunk_type + chunk_data) & 0xFFFFFFFF
            if expected_crc != actual_crc:
                return f"PNG {chunk_type.decode('ascii', errors='replace')} CRC 无效"

            if chunk_type == b"IHDR":
                if seen_ihdr or offset != len(PNG_SIGNATURE) or chunk_length != 13:
                    return "PNG IHDR 结构无效"
                width, height = struct.unpack(">II", chunk_data[:8])
                if width <= 0 or height <= 0:
                    return "PNG 尺寸无效"
                seen_ihdr = True
            elif chunk_type == b"IDAT":
                seen_idat = True
            elif chunk_type == b"IEND":
                if chunk_length != 0:
                    return "PNG IEND 结构无效"
                seen_iend = True
                if chunk_end != len(data):
                    return "PNG IEND 后存在多余数据"
                break
            offset = chunk_end
    except (OSError, struct.error) as exc:
        return f"PNG 解析失败: {exc}"

    if not seen_ihdr or not seen_idat or not seen_iend:
        return "PNG 缺少 IHDR、IDAT 或 IEND"
    return None


def build_codex_prompt(manifest_path: Path) -> str:
    """构建受限的 Codex 子会话任务，图片规格保存在 manifest 中。"""
    return f"""你是 Doc Reader 的图片生成执行器，只完成下面这一项任务。

完整读取 manifest：{manifest_path}

按 jobs 数组顺序处理每一项：
1. 对每个 job 单独调用一次 $imagegen skill，并使用它默认的内置 image_gen 工具模式。
2. 将 job.prompt 作为权威视觉规格，不总结、不改写事实，也不添加新主题。
3. image_gen 完成后，从 $CODEX_HOME/generated_images 下选取本次生成的原始 PNG，复制到 job.output_path。job.output_path 是已授权写入的临时路径。
4. 不得调用 Image API、scripts/image_gen.py、curl 或自写 SDK；不得用 Python、SVG、HTML 或占位图伪造图片。
5. 某一项失败时继续处理后续项，并在最终答复中列出失败项。
6. 完成前逐个确认 job.output_path 存在且非空。除这些目标 PNG 外，不修改工作区文件。

最终只报告成功数、失败数和失败 index；不要输出文章正文。
""".strip()


def build_codex_command(codex_path: str, working_dir: Path) -> list[str]:
    """返回非交互、无持久 session、最小写权限的 Codex CLI 命令。"""
    return [
        codex_path,
        "--ask-for-approval",
        "never",
        "--sandbox",
        "workspace-write",
        "exec",
        "--ephemeral",
        "--skip-git-repo-check",
        "--color",
        "never",
        "-C",
        str(working_dir),
        "-",
    ]


def run_codex_imagegen(
    manifest_path: Path,
    working_dir: Path,
) -> tuple[int, str]:
    """为单张幻灯片启动一次 Codex CLI 调用，返回退出码与完整日志。"""
    codex_path = shutil.which("codex")
    if not codex_path:
        return 127, "未在 PATH 中找到 codex；请先安装 Codex CLI"

    timeout = TIMEOUT_PER_SLIDE_SECONDS
    command = build_codex_command(codex_path, working_dir)

    try:
        completed = subprocess.run(
            command,
            input=build_codex_prompt(manifest_path),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
            check=False,
        )
        return completed.returncode, completed.stdout or ""
    except subprocess.TimeoutExpired as exc:
        output = exc.stdout or ""
        if isinstance(output, bytes):
            output = output.decode("utf-8", errors="replace")
        return 124, f"Codex imagegen 超时（{timeout} 秒）\n{output}"
    except OSError as exc:
        return 126, f"无法启动 Codex CLI: {exc}"


def write_prompts_log(output_dir: Path, prompts: list[dict]) -> Path:
    """先写提示词日志，失败时仍可审计和复现。"""
    output_dir.mkdir(parents=True, exist_ok=True)
    prompts_path = output_dir / "prompts.json"
    prompts_path.write_text(
        json.dumps(prompts, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return prompts_path


def result_for(slide: dict, prompt: str, output_path: Path) -> dict:
    return {
        "index": slide["index"],
        "title": slide["title"],
        "prompt": prompt,
        "output_path": str(output_path),
        "success": False,
        "error": None,
    }


def generate_all_slides(
    metadata_path: str = "slides_metadata.json",
    output_dir: str = "slides",
    aspect_ratio: str = DEFAULT_ASPECT_RATIO,
    dry_run: bool = False,
    concurrency: int = 0,
) -> list[dict]:
    """并发生成整组幻灯片：一张图一个 Codex 会话，批次全部校验通过才提交。"""
    metadata_file = Path(metadata_path)
    if not metadata_file.is_file():
        print(f"❌ 元数据文件不存在: {metadata_path}")
        return []

    try:
        metadata = json.loads(metadata_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"❌ 无法读取元数据: {exc}")
        return []

    if not isinstance(metadata, dict):
        print("❌ 元数据根节点必须是对象")
        return []

    slides = metadata.get("slides", [])
    if not isinstance(slides, list):
        print("❌ slides 必须是数组")
        return []

    validation_error = validate_slides(slides)
    if validation_error:
        print(f"❌ {validation_error}")
        return []

    article_title = str(metadata.get("title") or "技术文章")
    output_path = Path(output_dir).resolve()
    prompts = [
        {
            "index": slide["index"],
            "title": slide["title"],
            "prompt": build_image_prompt(slide, article_title, aspect_ratio),
            "output_path": str(output_path / f"slide_{slide['index']:02d}.png"),
        }
        for slide in slides
    ]
    prompts_path = write_prompts_log(output_path, prompts)

    print(f"🎨 准备生成 {len(slides)} 张幻灯片图片")
    print(f"📐 目标画布: {aspect_ratio}")
    print("🤖 执行方式: 每张图一个 codex exec 会话，由 $imagegen 生成")
    print(f"💾 提示词已保存: {prompts_path}")

    results = [
        result_for(slide, prompt_data["prompt"], Path(prompt_data["output_path"]))
        for slide, prompt_data in zip(slides, prompts)
    ]

    if dry_run:
        for result in results:
            result["success"] = True
            result["dry_run"] = True
        print("🔍 Dry Run 完成：未启动 Codex CLI")
        return results

    working_dir = Path.cwd().resolve()
    workers = max(1, min(concurrency or len(prompts), len(prompts)))
    print(f"⚡ 并发度: {workers}（每张图一个独立 codex exec 会话）")

    with tempfile.TemporaryDirectory(prefix=".imagegen-staging-", dir=output_path) as temp_dir:
        staging_dir = Path(temp_dir)
        jobs = []
        for prompt_data in prompts:
            index = prompt_data["index"]
            job = {
                "index": index,
                "title": prompt_data["title"],
                "prompt": prompt_data["prompt"],
                "output_path": str(staging_dir / f"slide_{index:02d}.png"),
            }
            # 每张图独占一个 manifest，对应一个独立 codex exec 会话。
            # Codex 把 image_gen 产物写进 $CODEX_HOME/generated_images/<会话 id>/，
            # 会话之间目录天然隔离，因此并发不会互相挑错图片。
            manifest_path = staging_dir / f"imagegen_manifest_{index:02d}.json"
            manifest_path.write_text(
                json.dumps({"jobs": [job]}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            job["manifest_path"] = manifest_path
            jobs.append(job)

        logs: dict[int, tuple[int, str]] = {}
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {
                pool.submit(
                    run_codex_imagegen,
                    job["manifest_path"],
                    working_dir,
                ): job
                for job in jobs
            }
            for future in as_completed(futures):
                job = futures[future]
                returncode, codex_log = future.result()
                logs[job["index"]] = (returncode, codex_log)
                mark = "✅" if returncode == 0 else "⚠️"
                print(f"{mark} [{job['index']}] Codex 会话结束（退出码 {returncode}）")

        log_path = output_path / "codex-imagegen.log"
        log_path.write_text(
            "\n\n".join(
                f"===== slide_{index:02d} · 退出码 {logs[index][0]} =====\n{logs[index][1]}"
                for index in sorted(logs)
            ),
            encoding="utf-8",
        )
        print(f"🧾 Codex 日志已保存: {log_path}")

        staged_errors = []
        failed_sessions = []
        for job in jobs:
            index = job["index"]
            returncode = logs.get(index, (1, ""))[0]
            if returncode != 0:
                failed_sessions.append(index)
            error = validate_png(Path(job["output_path"]))
            if error:
                staged_errors.append((index, error))

        if failed_sessions or staged_errors:
            error_by_index = dict(staged_errors)
            for result in results:
                index = result["index"]
                detail = error_by_index.get(index)
                if detail:
                    result["error"] = detail
                elif index in failed_sessions:
                    result["error"] = f"Codex CLI 退出码 {logs[index][0]}"
                else:
                    result["error"] = "同批其他图片失败，整批未提交"
            print("❌ 图片批次未提交：旧图片保持不变")
            for index in failed_sessions:
                print(f"   slide_{index:02d}: Codex CLI 退出码 {logs[index][0]}")
            for index, error in staged_errors:
                print(f"   slide_{index:02d}.png: {error}")
            print(f"   完整日志见 {log_path}")
            return results

        for result, job in zip(results, jobs):
            final_path = Path(result["output_path"])
            os.replace(job["output_path"], final_path)
            result["success"] = True
            result["file_size"] = final_path.stat().st_size
            print(
                f"✅ [{result['index']}] {result['title']} "
                f"({result['file_size'] / 1024:.1f} KB)"
            )

    print(f"📊 完成: {len(results)}/{len(results)} 张图片生成成功")
    return results


def main() -> int:
    parser = argparse.ArgumentParser(
        description="通过一次 Codex CLI 会话生成 AI 幻灯片图片"
    )
    parser.add_argument(
        "-i", "--input", default="slides_metadata.json", help="元数据文件路径"
    )
    parser.add_argument("-o", "--output", default="slides", help="输出目录")
    parser.add_argument(
        "-a",
        "--aspect-ratio",
        default=DEFAULT_ASPECT_RATIO,
        help="提示词中的目标宽高比（默认: 16:9）",
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="仅生成提示词，不启动 Codex CLI"
    )
    parser.add_argument(
        "-j",
        "--concurrency",
        type=int,
        default=DEFAULT_CONCURRENCY,
        help=f"并发的 Codex 会话数（默认: {DEFAULT_CONCURRENCY}；1 即串行）",
    )
    args = parser.parse_args()

    results = generate_all_slides(
        metadata_path=args.input,
        output_dir=args.output,
        aspect_ratio=args.aspect_ratio,
        dry_run=args.dry_run,
        concurrency=args.concurrency,
    )
    if not results or any(not result["success"] for result in results):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
