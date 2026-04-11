"""
Reusable Jianying subtitle style profiles.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SubtitleLayerStyle:
    track_name: str
    track_type: str
    language: str
    group_id: str
    transform_y: float
    render_index_base: int
    material_type: str = "subtitle"
    text_color: str = "#FFFFFF"
    border_color: str = "#000000"
    border_width: float = 0.08
    font_size: float = 5.0
    text_size: int = 30
    line_max_width: float = 0.82
    line_spacing: float = 0.0
    fixed_width_ratio: float = 0.82
    fixed_width: int = -1
    needs_animation: bool = True
    font_name: str = ""
    font_path: str = ""
    font_resource_id: str = ""
    bold: bool = False
    italic: bool = False
    underline: bool = False


@dataclass(frozen=True)
class JianyingStyleTemplate:
    key: str
    label: str
    chinese_layer: SubtitleLayerStyle
    english_layer: SubtitleLayerStyle | None = None
    attach_media_support_materials: bool = False
    merge_languages_into_single_track: bool = False
    subtitle_separator: str = "\n"


BASIC_STYLE_TEMPLATE = JianyingStyleTemplate(
    key="basic",
    label="基础字幕模版",
    chinese_layer=SubtitleLayerStyle(
        track_name="字幕",
        track_type="text",
        language="zh-CN",
        group_id="",
        transform_y=-0.78,
        render_index_base=15000,
        material_type="text",
        needs_animation=False,
        line_spacing=0.02,
        fixed_width_ratio=0.70,
        font_name="PingFang SC",
        bold=True,
    ),
)


EMOTION_STYLE_TEMPLATE = JianyingStyleTemplate(
    key="emotion",
    label="情绪类视频模版",
    chinese_layer=SubtitleLayerStyle(
        track_name="双语字幕",
        track_type="text",
        language="zh-CN",
        group_id="",
        transform_y=-0.79,
        render_index_base=15000,
        material_type="text",
        needs_animation=False,
        text_color="#FFFFFF",
        border_color="#101828",
        border_width=0.12,
        font_size=5.6,
        text_size=32,
        line_max_width=0.74,
        line_spacing=0.08,
        fixed_width_ratio=0.74,
        font_name="PingFang SC",
        bold=True,
    ),
    english_layer=SubtitleLayerStyle(
        track_name="双语字幕",
        track_type="text",
        language="en-US",
        group_id="",
        transform_y=-0.79,
        render_index_base=15000,
        material_type="text",
        needs_animation=False,
        text_color="#D7E6FF",
        border_color="#101828",
        border_width=0.08,
        font_size=3.9,
        text_size=21,
        line_max_width=0.74,
        line_spacing=0.04,
        fixed_width_ratio=0.74,
        font_name="Helvetica Neue",
    ),
    merge_languages_into_single_track=True,
)


STYLE_TEMPLATES = {
    BASIC_STYLE_TEMPLATE.key: BASIC_STYLE_TEMPLATE,
    EMOTION_STYLE_TEMPLATE.key: EMOTION_STYLE_TEMPLATE,
}


def resolve_style_template(name: str | None) -> JianyingStyleTemplate:
    key = (name or EMOTION_STYLE_TEMPLATE.key).strip().lower()
    if key not in STYLE_TEMPLATES:
        choices = ", ".join(sorted(STYLE_TEMPLATES))
        raise ValueError(f"Unknown Jianying style template: {name!r}. Expected one of: {choices}")
    return STYLE_TEMPLATES[key]
