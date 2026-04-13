"""
Split long transcript segments into subtitle-friendly chunks.
"""
from __future__ import annotations

import re
from typing import Any

from .audio_silence import AudioSilenceProfile, SilenceInterval
from .text_normalizer import normalize_chinese_text


STRONG_DELIMITERS = "。！？!?；;"
WEAK_DELIMITERS = "，,、：:"
ALL_DELIMITERS = STRONG_DELIMITERS + WEAK_DELIMITERS
DEFAULT_MAX_CHARS = 18
DEFAULT_MIN_DURATION = 0.8
DEFAULT_MIN_GAP = 0.12
DEFAULT_EDGE_SILENCE = 0.18
REALIGN_BOUNDARY_WINDOW = 1.2


def _clean_text(text: str) -> str:
    text = normalize_chinese_text(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _visible_len(text: str) -> int:
    return len(text.replace(" ", ""))


def _split_text_chunks(text: str, *, max_chars: int = DEFAULT_MAX_CHARS) -> list[str]:
    text = _clean_text(text)
    if not text:
        return []

    tokens = re.findall(rf"[^{re.escape(ALL_DELIMITERS)}]+[{re.escape(ALL_DELIMITERS)}]?", text)
    if not tokens:
        return [text]

    chunks: list[str] = []
    current = ""

    for token in tokens:
        token = token.strip()
        if not token:
            continue

        if current and _visible_len(current) + _visible_len(token) > max_chars:
            chunks.append(current)
            current = ""

        if _visible_len(token) <= max_chars:
            current += token
        else:
            token_body = token
            trailing = ""
            if token_body[-1] in ALL_DELIMITERS:
                trailing = token_body[-1]
                token_body = token_body[:-1]

            while _visible_len(token_body) > max_chars:
                chunks.append(token_body[:max_chars])
                token_body = token_body[max_chars:]

            current += token_body + trailing

        if current and current[-1] in STRONG_DELIMITERS:
            chunks.append(current)
            current = ""
        elif current and current[-1] in WEAK_DELIMITERS and _visible_len(current) >= max_chars // 2:
            chunks.append(current)
            current = ""

    if current:
        chunks.append(current)

    return _merge_short_chunks(chunks, max_chars=max_chars)


def _merge_short_chunks(chunks: list[str], *, max_chars: int) -> list[str]:
    if not chunks:
        return []

    merged: list[str] = []
    for chunk in chunks:
        chunk = chunk.strip()
        if not chunk:
            continue

        if merged and _visible_len(chunk) <= 4 and _visible_len(merged[-1]) + _visible_len(chunk) <= max_chars + 4:
            merged[-1] += chunk
        else:
            merged.append(chunk)

    if len(merged) >= 2 and _visible_len(merged[-1]) <= 4 and _visible_len(merged[-2]) + _visible_len(merged[-1]) <= max_chars + 4:
        merged[-2] += merged[-1]
        merged.pop()

    return merged


def _merge_adjacent_chunks(chunks: list[str], *, target_count: int) -> list[str]:
    chunks = list(chunks)
    while len(chunks) > target_count and len(chunks) >= 2:
        best_index = 0
        best_score = None
        for i in range(len(chunks) - 1):
            score = _visible_len(chunks[i]) + _visible_len(chunks[i + 1])
            if best_score is None or score < best_score:
                best_score = score
                best_index = i
        chunks[best_index:best_index + 2] = [chunks[best_index] + chunks[best_index + 1]]
    return chunks


def _weighted_boundary_times(
    chunks: list[str],
    start: float,
    end: float,
) -> list[float]:
    total_weight = sum(max(1, _visible_len(chunk)) for chunk in chunks)
    consumed_weight = 0
    boundaries: list[float] = []
    duration = max(0.0, end - start)
    for chunk in chunks[:-1]:
        consumed_weight += max(1, _visible_len(chunk))
        boundaries.append(start + duration * (consumed_weight / total_weight))
    return boundaries


def _align_boundaries_to_silences(
    start: float,
    end: float,
    chunks: list[str],
    silences: list[SilenceInterval],
    *,
    min_duration: float,
) -> list[dict[str, Any]]:
    if not chunks:
        return []

    local_silences = [item for item in silences if item.duration >= DEFAULT_MIN_GAP]
    effective_start = start
    effective_end = end

    if local_silences and local_silences[0].start <= start + DEFAULT_EDGE_SILENCE:
        effective_start = max(effective_start, local_silences[0].end)
        local_silences = local_silences[1:]

    if local_silences and local_silences[-1].end >= end - DEFAULT_EDGE_SILENCE:
        effective_end = min(effective_end, local_silences[-1].start)
        local_silences = local_silences[:-1]

    if effective_end - effective_start <= min_duration:
        effective_start = start
        effective_end = end

    boundaries = _weighted_boundary_times(chunks, effective_start, effective_end)
    selected: list[tuple[float, float]] = []
    used_indexes: set[int] = set()
    cursor = effective_start

    for boundary_index, ideal_time in enumerate(boundaries):
        remaining_chunks = len(boundaries) - boundary_index
        earliest = cursor + min_duration
        latest = effective_end - (remaining_chunks * min_duration)
        feasible: list[tuple[int, SilenceInterval]] = [
            (index, silence)
            for index, silence in enumerate(local_silences)
            if index not in used_indexes
            and silence.start >= earliest
            and silence.end <= latest
        ]

        if feasible:
            chosen_index, chosen_silence = min(
                feasible,
                key=lambda item: (
                    abs(item[1].midpoint - ideal_time) - item[1].duration * 0.25,
                    abs(item[1].midpoint - ideal_time),
                ),
            )
            used_indexes.add(chosen_index)
            selected.append((chosen_silence.start, chosen_silence.end))
            cursor = chosen_silence.end
            continue

        point = min(max(ideal_time, earliest), latest)
        selected.append((point, point))
        cursor = point

    result: list[dict[str, Any]] = []
    cursor = effective_start
    for chunk, (boundary_start, boundary_end) in zip(chunks[:-1], selected):
        result.append({"start": cursor, "end": boundary_start, "text": chunk})
        cursor = boundary_end

    result.append({"start": cursor, "end": effective_end, "text": chunks[-1]})
    return [item for item in result if (item["end"] - item["start"]) >= 0.2 and item["text"].strip()]


def _realign_existing_segments(
    segments: list[dict[str, Any]],
    silence_profile: AudioSilenceProfile,
    *,
    min_duration: float,
) -> list[dict[str, Any]]:
    if len(segments) <= 1:
        return segments

    aligned = [
        {
            "start": float(item["start"]),
            "end": float(item["end"]),
            "text": item["text"],
        }
        for item in segments
    ]

    leading = silence_profile.between(
        aligned[0]["start"],
        min(aligned[0]["end"], aligned[0]["start"] + REALIGN_BOUNDARY_WINDOW),
    )
    if leading and leading[0].start <= aligned[0]["start"] + DEFAULT_EDGE_SILENCE:
        candidate_start = leading[0].end
        if aligned[0]["end"] - candidate_start >= min_duration * 0.5:
            aligned[0]["start"] = candidate_start

    trailing = silence_profile.between(
        max(aligned[-1]["start"], aligned[-1]["end"] - REALIGN_BOUNDARY_WINDOW),
        aligned[-1]["end"],
    )
    if trailing and trailing[-1].end >= aligned[-1]["end"] - DEFAULT_EDGE_SILENCE:
        candidate_end = trailing[-1].start
        if candidate_end - aligned[-1]["start"] >= min_duration * 0.5:
            aligned[-1]["end"] = candidate_end

    for index in range(len(aligned) - 1):
        left = aligned[index]
        right = aligned[index + 1]
        ideal_boundary = left["end"]
        search_start = max(left["start"], ideal_boundary - REALIGN_BOUNDARY_WINDOW)
        search_end = min(right["end"], ideal_boundary + REALIGN_BOUNDARY_WINDOW)
        candidates = silence_profile.between(search_start, search_end)
        if not candidates:
            continue

        chosen = min(
            candidates,
            key=lambda item: (
                abs(item.midpoint - ideal_boundary) - item.duration * 0.25,
                abs(item.midpoint - ideal_boundary),
            ),
        )
        next_left_end = chosen.start
        next_right_start = chosen.end
        if next_left_end - left["start"] < min_duration * 0.5:
            continue
        if right["end"] - next_right_start < min_duration * 0.5:
            continue
        left["end"] = next_left_end
        right["start"] = next_right_start

    return [item for item in aligned if item["end"] - item["start"] >= 0.2]


def split_subtitle_segment(
    start: float,
    end: float,
    text: str,
    *,
    max_chars: int = DEFAULT_MAX_CHARS,
    min_duration: float = DEFAULT_MIN_DURATION,
    silence_profile: AudioSilenceProfile | None = None,
) -> list[dict[str, Any]]:
    text = _clean_text(text)
    if not text:
        return []

    duration = max(0.0, float(end) - float(start))
    if duration <= 0:
        return [{"start": float(start), "end": float(end), "text": text}]

    chunks = _split_text_chunks(text, max_chars=max_chars)
    if not chunks:
        return [{"start": float(start), "end": float(end), "text": text}]

    max_segments = max(1, int(duration / min_duration))
    if len(chunks) > max_segments:
        chunks = _merge_adjacent_chunks(chunks, target_count=max_segments)

    if silence_profile is not None and len(chunks) > 1:
        silences = silence_profile.between(float(start), float(end))
        aligned = _align_boundaries_to_silences(
            float(start),
            float(end),
            chunks,
            silences,
            min_duration=min_duration,
        )
        if aligned:
            return aligned

    total_weight = sum(max(1, _visible_len(chunk)) for chunk in chunks)
    result: list[dict[str, Any]] = []
    cursor = float(start)
    consumed_weight = 0

    for index, chunk in enumerate(chunks):
        weight = max(1, _visible_len(chunk))
        if index == len(chunks) - 1:
            chunk_end = float(end)
        else:
            consumed_weight += weight
            chunk_end = float(start) + duration * (consumed_weight / total_weight)
        result.append({"start": cursor, "end": chunk_end, "text": chunk})
        cursor = chunk_end

    return result


def split_transcript_segments(
    segments: list[dict[str, Any]],
    *,
    max_chars: int = DEFAULT_MAX_CHARS,
    min_duration: float = DEFAULT_MIN_DURATION,
    silence_profile: AudioSilenceProfile | None = None,
) -> list[dict[str, Any]]:
    split_segments: list[dict[str, Any]] = []
    for item in segments:
        split_segments.extend(
            split_subtitle_segment(
                float(item.get("start", 0.0)),
                float(item.get("end", 0.0)),
                str(item.get("text", "")),
                max_chars=max_chars,
                min_duration=min_duration,
                silence_profile=silence_profile,
            )
        )
    if silence_profile is not None and len(split_segments) > 1:
        split_segments = _realign_existing_segments(
            split_segments,
            silence_profile,
            min_duration=min_duration,
        )
    return split_segments
