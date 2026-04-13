"""
语音转文字模块 - 负责音频转录
"""
import importlib
import os
import re
import tempfile

from src.utils.audio_silence import load_audio_silence_profile
from src.utils.subtitle_segmentation import split_transcript_segments
from src.utils.text_normalizer import normalize_chinese_text


SIMPLIFIED_CHINESE_PROMPT = "以下是普通话简体中文字幕。请使用简体中文输出，不要使用繁体字。"


def _load_audio_segment():
    try:
        from pydub import AudioSegment
    except ModuleNotFoundError as exc:
        raise ModuleNotFoundError(
            "需要安装 pydub 才能启用按字幕分段的双语翻译功能。"
        ) from exc
    return AudioSegment


class Transcriber:
    """语音转文字转录器"""
    
    def __init__(self, model_size="base"):
        """
        初始化转录器
        
        Args:
            model_size: Whisper 模型大小 (tiny, base, small, medium, large)
        """
        self.model_size = model_size
        self.model = None
    
    def load_model(self):
        """加载 Whisper 模型"""
        if self.model is None:
            print(f"正在加载 Whisper 模型 ({self.model_size})...")
            try:
                whisper = importlib.import_module("whisper")
            except ModuleNotFoundError as exc:
                raise ModuleNotFoundError(
                    "Whisper 未安装。请先在虚拟环境中执行 `pip install -r requirements.txt`。"
                ) from exc
            self.model = whisper.load_model(self.model_size)
    
    def _format_result(self, raw_result, audio_path, *, normalize_chinese, task):
        """格式化 Whisper 原始输出。"""
        segments = []
        for segment in raw_result["segments"]:
            text = segment["text"].strip()
            if normalize_chinese:
                text = normalize_chinese_text(text)
            segments.append({
                "start": segment["start"],
                "end": segment["end"],
                "text": text
            })

        if task == "translate":
            silence_profile = load_audio_silence_profile(audio_path)
            segments = split_transcript_segments(
                segments,
                silence_profile=silence_profile,
                max_chars=28,
            )
        elif normalize_chinese:
            silence_profile = load_audio_silence_profile(audio_path)
            segments = split_transcript_segments(
                segments,
                silence_profile=silence_profile,
            )

        full_text = raw_result["text"]
        if normalize_chinese:
            full_text = normalize_chinese_text(full_text)

        return {
            "text": full_text,
            "segments": segments
        }

    def transcribe(self, audio_path, language="zh", task="transcribe"):
        """
        转录音频文件
        
        Args:
            audio_path: 音频文件路径
            language: 语言代码 (默认: zh 中文)
            task: Whisper 任务类型，transcribe 或 translate
            
        Returns:
            dict: 转录结果，包含 text 和 segments
        """
        self.load_model()
        print("正在转录音频...")

        transcribe_kwargs = {"task": task, "temperature": 0}
        if language:
            transcribe_kwargs["language"] = language
        normalize_chinese = task != "translate" and language.startswith("zh")
        if normalize_chinese:
            transcribe_kwargs["initial_prompt"] = SIMPLIFIED_CHINESE_PROMPT

        result = self.model.transcribe(audio_path, **transcribe_kwargs)
        return self._format_result(
            result,
            audio_path,
            normalize_chinese=normalize_chinese,
            task=task,
        )

    def translate_to_english(self, audio_path, source_language="zh"):
        """将音频翻译成英文字幕。"""
        result = self.transcribe(audio_path, language=source_language, task="translate")
        if result["text"].strip() or result["segments"]:
            return result

        self.load_model()
        print("英文翻译首轮结果为空，正在自动识别语言重试...")
        retry = self.model.transcribe(audio_path, task="translate", temperature=0)
        return self._format_result(
            retry,
            audio_path,
            normalize_chinese=False,
            task="translate",
        )

    def translate_segments_to_english(
        self,
        audio_path,
        segments,
        source_language="zh",
        *,
        pad_seconds=0.15,
    ):
        """按给定的字幕时间切分音频并逐段翻译，保留原始时间轴。"""
        self.load_model()
        audio = _load_audio_segment().from_file(audio_path)
        translated_segments = []

        for segment in segments:
            start = float(segment.get("start", 0.0))
            end = float(segment.get("end", start))
            if end <= start:
                continue

            clip_start_ms = max(0, int(round((start - pad_seconds) * 1000)))
            clip_end_ms = min(len(audio), int(round((end + pad_seconds) * 1000)))
            if clip_end_ms <= clip_start_ms:
                clip_start_ms = max(0, int(round(start * 1000)))
                clip_end_ms = min(len(audio), int(round(end * 1000)))
            if clip_end_ms <= clip_start_ms:
                continue

            temp_path = None
            try:
                clip = audio[clip_start_ms:clip_end_ms]
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                    temp_path = tmp.name
                clip.export(temp_path, format="wav")
                result = self.model.transcribe(
                    temp_path,
                    language=source_language,
                    task="translate",
                    temperature=0,
                )
                text = re.sub(r"\s+", " ", str(result.get("text", ""))).strip()
            finally:
                if temp_path and os.path.exists(temp_path):
                    os.unlink(temp_path)

            translated_segments.append(
                {
                    "start": start,
                    "end": end,
                    "text": text,
                }
            )

        return {
            "text": " ".join(
                item["text"]
                for item in translated_segments
                if item["text"].strip()
            ).strip(),
            "segments": translated_segments,
        }
