#!/usr/bin/env python3
import argparse
import json
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFont, ImageOps


WIDTH = 1080
HEIGHT = 1440
FONT_CANDIDATES = [
    Path("/System/Library/Fonts/STHeiti Medium.ttc"),
    Path("/System/Library/Fonts/PingFang.ttc"),
    Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
]


def parse_args():
    parser = argparse.ArgumentParser(description="按项目视觉配置渲染小红书 3:4 封面")
    parser.add_argument("--spec", required=True, type=Path)
    parser.add_argument(
        "--allow-unconfirmed",
        action="store_true",
        help="仅用于三版视觉候选；每日生产不得使用",
    )
    return parser.parse_args()


def open_image(path: Path) -> Image.Image:
    try:
        return Image.open(path).convert("RGB")
    except Exception:
        if path.suffix.lower() not in {".heic", ".heif"}:
            raise
        if not Path("/usr/bin/sips").is_file():
            raise RuntimeError("当前环境不能转换 HEIC；请先转成 JPEG 或 PNG")
        with tempfile.TemporaryDirectory(prefix="xhs-cover-") as temp_dir:
            converted = Path(temp_dir) / "source.jpg"
            subprocess.run(
                ["/usr/bin/sips", "-s", "format", "jpeg", str(path), "--out", str(converted)],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return Image.open(converted).convert("RGB")


def color(value: str, alpha: int = 255):
    text = str(value).strip().lstrip("#")
    if len(text) != 6:
        raise ValueError(f"颜色必须使用 #RRGGBB：{value}")
    return tuple(int(text[index : index + 2], 16) for index in (0, 2, 4)) + (alpha,)


def load_font(theme: dict, size: int):
    typography = theme.get("typography", {})
    configured = str(typography.get("font_path", "")).strip()
    candidates = [Path(configured).expanduser()] if configured else []
    candidates.extend(FONT_CANDIDATES)
    font_index = int(typography.get("font_index", 0))
    for candidate in candidates:
        if candidate.is_file():
            return ImageFont.truetype(str(candidate), size=size, index=font_index)
    raise FileNotFoundError("未找到可用字体；请在视觉模板/cover-theme.json 设置 typography.font_path")


def split_title(text: str, requested=None):
    if requested:
        lines = [str(line).strip() for line in requested if str(line).strip()]
        if "".join(lines) == text:
            return lines
        raise ValueError("title_lines 必须按顺序完整拼接为 title")
    if len(text) <= 6:
        return [text]
    line_count = 2 if len(text) <= 12 else 3
    base, extra = divmod(len(text), line_count)
    lines = []
    start = 0
    for index in range(line_count):
        length = base + (1 if index < extra else 0)
        lines.append(text[start : start + length])
        start += length
    return lines


def split_subtitle(text: str):
    if not text:
        return []
    if len(text) <= 11:
        return [text]
    for mark in ("，", "；", "。", ",", ";"):
        if mark in text:
            left, right = text.split(mark, 1)
            if left and right:
                return [left + mark, right]
    midpoint = (len(text) + 1) // 2
    return [text[:midpoint], text[midpoint:]]


def fit_font(draw, theme, requested_size, lines, max_width, minimum):
    size = requested_size
    face = load_font(theme, size)
    while any(draw.textbbox((0, 0), line, font=face)[2] > max_width for line in lines):
        size -= 4
        if size < minimum:
            raise ValueError("文字过长，无法在安全区域内排版；请缩短标题或调整断行")
        face = load_font(theme, size)
    return face


def draw_subtitle(draw, theme, lines, top, margin, width, palette):
    if not lines:
        return
    requested_size = int(theme.get("typography", {}).get("subtitle_size", 46))
    face = fit_font(draw, theme, requested_size, lines, width - 96, 30)
    line_height = face.size + 10
    box_height = len(lines) * line_height + 38
    draw.rounded_rectangle(
        (margin, top + 8, margin + width, top + box_height + 8),
        radius=18,
        fill=color(palette["shadow"], 32),
    )
    draw.rounded_rectangle(
        (margin, top, margin + width, top + box_height),
        radius=18,
        fill=color(palette["primary"], 238),
    )
    draw.rectangle(
        (margin + 24, top + 16, margin + 34, top + box_height - 16),
        fill=color(palette["accent"]),
    )
    y = top + 16
    for line in lines:
        draw.text((margin + 58, y), line, font=face, fill=color(palette["text_on_primary"]))
        y += line_height


def render(spec_path: Path, allow_unconfirmed: bool) -> Path:
    spec_path = spec_path.expanduser().resolve()
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    day_dir = spec_path.parent.parent.parent
    project_root = day_dir.parent.parent
    theme_path = (project_root / str(spec.get("theme", "视觉模板/cover-theme.json"))).resolve()
    if project_root != theme_path and project_root not in theme_path.parents:
        raise ValueError("视觉配置必须位于项目根目录内")
    theme = json.loads(theme_path.read_text(encoding="utf-8"))
    if theme.get("status") != "confirmed" and not allow_unconfirmed:
        raise ValueError("视觉尚未确认；每日生产前请把 cover-theme.json 的 status 设为 confirmed")
    if theme.get("placeholder_only", True) and not allow_unconfirmed:
        raise ValueError("当前仍是测试占位视觉；请先根据对标或已选风格完成视觉确认")
    generation_method = str(theme.get("generation", {}).get("method", "pending"))
    if generation_method != "local-renderer" and not allow_unconfirmed:
        raise ValueError("当前项目没有选择 local-renderer；请按视觉配置调用指定的外部 Skill")

    title = str(spec.get("title", "")).strip()
    subtitle = str(spec.get("subtitle", "")).strip()
    if not title or len(title) > 20:
        raise ValueError("封面标题必须为 1—20 个字符")

    source = (project_root / str(spec.get("source_image", ""))).resolve()
    if project_root != source and project_root not in source.parents:
        raise ValueError("封面素材必须位于项目根目录内")
    if not source.is_file():
        raise FileNotFoundError(f"找不到根目录素材：{source}")
    output = (day_dir / str(spec.get("output", ""))).resolve()
    if day_dir not in output.parents:
        raise ValueError("封面输出必须位于当天日期目录内")

    image_options = theme.get("image", {})
    photo = open_image(source)
    photo = ImageEnhance.Brightness(photo).enhance(float(image_options.get("brightness", 1.0)))
    photo = ImageEnhance.Contrast(photo).enhance(float(image_options.get("contrast", 1.0)))
    canvas = ImageOps.fit(photo, (WIDTH, HEIGHT), method=Image.Resampling.LANCZOS)
    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    palette = theme["palette"]
    margin = int(theme.get("spacing", {}).get("safe_margin", 72))
    layout = str(spec.get("layout") or theme.get("layout", "editorial-cards"))
    title_lines = split_title(title, spec.get("title_lines"))
    requested_title_size = int(theme.get("typography", {}).get("title_size", 108))
    title_face = fit_font(draw, theme, requested_title_size, title_lines, WIDTH - margin * 2 - 54, 68)
    title_line_height = title_face.size + 12
    subtitle_lines = split_subtitle(subtitle)

    if layout == "photo-title":
        top = margin
        for index, line in enumerate(title_lines):
            text_width = draw.textbbox((0, 0), line, font=title_face)[2]
            left = margin + index * 18
            band_top = top + index * (title_line_height + 18)
            band_width = text_width + 52
            draw.rounded_rectangle(
                (left, band_top + 7, left + band_width, band_top + title_line_height + 31),
                radius=15,
                fill=color(palette["shadow"], 34),
            )
            draw.rounded_rectangle(
                (left, band_top, left + band_width, band_top + title_line_height + 24),
                radius=15,
                fill=color(palette["surface"], 238),
            )
            draw.text((left + 26, band_top + 8), line, font=title_face, fill=color(palette["primary"]))
        subtitle_top = top + len(title_lines) * (title_line_height + 18) + 20
        draw_subtitle(draw, theme, subtitle_lines, subtitle_top, margin, min(800, WIDTH - margin * 2), palette)

    elif layout == "editorial-cards":
        top = margin
        for index, line in enumerate(title_lines):
            text_width = draw.textbbox((0, 0), line, font=title_face)[2]
            left = margin + (index % 2) * 30
            card_width = text_width + 64
            card_top = top + index * (title_line_height + 34)
            surface_key = "surface" if index % 2 == 0 else "surface_alt"
            draw.rounded_rectangle(
                (left, card_top + 8, left + card_width, card_top + title_line_height + 38),
                radius=20,
                fill=color(palette["shadow"], 32),
            )
            draw.rounded_rectangle(
                (left, card_top, left + card_width, card_top + title_line_height + 30),
                radius=20,
                fill=color(palette[surface_key], 242),
                outline=color(palette["accent"], 220),
                width=2,
            )
            draw.text((left + 32, card_top + 10), line, font=title_face, fill=color(palette["primary"]))
        subtitle_top = top + len(title_lines) * (title_line_height + 34) + 18
        draw_subtitle(draw, theme, subtitle_lines, subtitle_top, margin, min(820, WIDTH - margin * 2), palette)

    elif layout == "brand-panel":
        subtitle_size = int(theme.get("typography", {}).get("subtitle_size", 46))
        subtitle_face = fit_font(
            draw,
            theme,
            subtitle_size,
            subtitle_lines or [""],
            WIDTH - margin * 2 - 64,
            30,
        )
        subtitle_height = len(subtitle_lines) * (subtitle_face.size + 10)
        panel_height = len(title_lines) * title_line_height + subtitle_height + 118
        panel = (margin, margin, WIDTH - margin, margin + panel_height)
        draw.rounded_rectangle(
            (panel[0], panel[1] + 10, panel[2], panel[3] + 10),
            radius=30,
            fill=color(palette["shadow"], 40),
        )
        draw.rounded_rectangle(panel, radius=30, fill=color(palette["surface"], 240))
        draw.rectangle(
            (margin + 28, margin + 28, margin + 40, margin + panel_height - 28),
            fill=color(palette["accent"]),
        )
        y = margin + 36
        for line in title_lines:
            draw.text((margin + 70, y), line, font=title_face, fill=color(palette["primary"]))
            y += title_line_height
        y += 18
        for line in subtitle_lines:
            draw.text((margin + 70, y), line, font=subtitle_face, fill=color(palette["primary"]))
            y += subtitle_face.size + 10
    else:
        raise ValueError(f"不支持的布局：{layout}")

    result = Image.alpha_composite(canvas.convert("RGBA"), overlay).convert("RGB")
    output.parent.mkdir(parents=True, exist_ok=True)
    result.save(output, format="PNG", optimize=True)
    return output


def main():
    args = parse_args()
    print(render(args.spec, args.allow_unconfirmed))


if __name__ == "__main__":
    main()
