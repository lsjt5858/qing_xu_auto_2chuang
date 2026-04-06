"""
语音转文字模块 - 负责音频转录
"""
import whisper


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
            self.model = whisper.load_model(self.model_size)
    
    def transcribe(self, audio_path, language="zh"):
        """
        转录音频文件
        
        Args:
            audio_path: 音频文件路径
            language: 语言代码 (默认: zh 中文)
            
        Returns:
            dict: 转录结果，包含 text 和 segments
        """
        self.load_model()
        print("正在转录音频...")
        
        result = self.model.transcribe(audio_path, language=language)
        
        # 格式化 segments
        segments = []
        for segment in result["segments"]:
            segments.append({
                "start": segment["start"],
                "end": segment["end"],
                "text": segment["text"].strip()
            })
        
        return {
            "text": result["text"],
            "segments": segments
        }
