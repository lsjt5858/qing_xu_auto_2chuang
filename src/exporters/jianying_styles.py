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


@dataclass(frozen=True)
class JianyingStyleTemplate:
    key: str
    label: str
    chinese_layer: SubtitleLayerStyle
    english_layer: SubtitleLayerStyle | None = None
    attach_media_support_materials: bool = False


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
    ),
)


EMOTION_STYLE_TEMPLATE = JianyingStyleTemplate(
    key="emotion",
    label="情绪类视频模版",
    chinese_layer=SubtitleLayerStyle(
        track_name="中文字幕",
        track_type="sticker",
        language="zh-CN",
        group_id="7734FAAB-474D-4F38-8575-3C6C3C6F3AD4",
        transform_y=-0.73,
        render_index_base=14000,
    ),
    english_layer=SubtitleLayerStyle(
        track_name="英文字幕",
        track_type="sticker",
        language="en-US",
        group_id="en-US_1775483128",
        transform_y=-0.90,
        render_index_base=14020,
    ),
    attach_media_support_materials=True,
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
