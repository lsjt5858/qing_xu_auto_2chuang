"""
Feature flag registry and helpers.
"""
from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
import os


ENV_PREFIX = "CHAI_FLAG_"
TRUE_VALUES = {"1", "true", "yes", "on", "enabled"}
FALSE_VALUES = {"0", "false", "no", "off", "disabled"}


def _normalize_name(name: str) -> str:
    normalized = str(name or "").strip().lower().replace("-", "_")
    if not normalized:
        raise ValueError("Feature flag name must not be empty")
    if any(ch not in "abcdefghijklmnopqrstuvwxyz0123456789_" for ch in normalized):
        raise ValueError(
            f"Invalid feature flag name {name!r}. Use letters, numbers, '_' or '-'."
        )
    return normalized


def _default_env_var(name: str) -> str:
    return f"{ENV_PREFIX}{name.upper()}"


def _parse_bool(value: str, *, env_var: str) -> bool:
    candidate = value.strip().lower()
    if candidate in TRUE_VALUES:
        return True
    if candidate in FALSE_VALUES:
        return False
    raise ValueError(
        f"Invalid boolean value {value!r} for {env_var}. "
        f"Expected one of: {sorted(TRUE_VALUES | FALSE_VALUES)}"
    )


@dataclass(frozen=True)
class FeatureFlag:
    name: str
    default: bool = False
    description: str = ""
    env_var: str | None = None

    def __post_init__(self) -> None:
        normalized = _normalize_name(self.name)
        object.__setattr__(self, "name", normalized)
        object.__setattr__(self, "env_var", self.env_var or _default_env_var(normalized))


class FeatureFlagRegistry:
    def __init__(self, flags: Iterable[FeatureFlag] | None = None):
        self._flags: dict[str, FeatureFlag] = {}
        self._overrides: dict[str, bool] = {}
        if flags:
            self.register_many(flags)

    def register(
        self,
        name: str,
        *,
        default: bool = False,
        description: str = "",
        env_var: str | None = None,
    ) -> FeatureFlag:
        flag = FeatureFlag(
            name=name,
            default=default,
            description=description,
            env_var=env_var,
        )
        existing = self._flags.get(flag.name)
        if existing and existing != flag:
            raise ValueError(f"Feature flag {flag.name!r} is already registered differently")
        self._flags[flag.name] = flag
        return flag

    def register_many(self, flags: Iterable[FeatureFlag]) -> None:
        for flag in flags:
            self._flags[flag.name] = flag

    def require(self, name: str) -> FeatureFlag:
        normalized = _normalize_name(name)
        if normalized not in self._flags:
            raise KeyError(f"Unknown feature flag: {name!r}")
        return self._flags[normalized]

    def is_enabled(self, name: str) -> bool:
        flag = self.require(name)
        if flag.name in self._overrides:
            return self._overrides[flag.name]

        raw_value = os.getenv(flag.env_var or "")
        if raw_value is None:
            return flag.default
        return _parse_bool(raw_value, env_var=flag.env_var or "")

    def get(self, name: str) -> bool:
        return self.is_enabled(name)

    def set_override(self, name: str, value: bool | None) -> None:
        flag = self.require(name)
        if value is None:
            self._overrides.pop(flag.name, None)
            return
        self._overrides[flag.name] = bool(value)

    def update_overrides(self, overrides: Mapping[str, bool]) -> None:
        for name, value in overrides.items():
            self.set_override(name, value)

    def clear_overrides(self) -> None:
        self._overrides.clear()

    def snapshot(self) -> dict[str, bool]:
        return {
            name: self.is_enabled(name)
            for name in sorted(self._flags)
        }

    def definitions(self) -> tuple[FeatureFlag, ...]:
        return tuple(self._flags[name] for name in sorted(self._flags))

    @contextmanager
    def override(self, **overrides: bool) -> Iterator["FeatureFlagRegistry"]:
        previous = dict(self._overrides)
        try:
            self.update_overrides(overrides)
            yield self
        finally:
            self._overrides = previous


DEFAULT_FEATURE_FLAGS = (
    FeatureFlag(
        name="segment_aligned_bilingual_translation",
        default=True,
        description="Translate bilingual subtitles per subtitle segment using the source subtitle timing.",
    ),
    FeatureFlag(
        name="single_track_bilingual_subtitles",
        default=True,
        description="Render bilingual subtitles on one text track.",
    ),
    FeatureFlag(
        name="prevent_video_frame_extension",
        default=True,
        description="Split long visual slots instead of extending the last frame of a short clip.",
    ),
    FeatureFlag(
        name="shot_pool_collection_diversity",
        default=True,
        description="Prefer fresh shot collections when filling the pool timeline.",
    ),
)


feature_flags = FeatureFlagRegistry(DEFAULT_FEATURE_FLAGS)


def is_feature_enabled(name: str) -> bool:
    return feature_flags.is_enabled(name)

