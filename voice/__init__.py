"""
Voice Module - 语音交互

提供语音输入（STT）和语音输出（TTS）功能。
对应 Claude Code 源码: src/voice/*.ts

功能：
- Text-to-Speech (TTS): 文字转语音
- Speech-to-Text (STT): 语音转文字
- 语音录制和播放
"""

from __future__ import annotations

import io
import os
import platform
import subprocess
import threading
import wave
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Union

# ============================================================================
# TTS - Text to Speech
# ============================================================================

class TTSEngine(ABC):
    """TTS 引擎基类"""
    
    @abstractmethod
    def speak(self, text: str, blocking: bool = True) -> None:
        """朗读文本"""
        ...
    
    @abstractmethod
    def stop(self) -> None:
        """停止朗读"""
        ...
    
    @abstractmethod
    def set_rate(self, rate: int) -> None:
        """设置语速 (words per minute)"""
        ...
    
    @abstractmethod
    def set_volume(self, volume: float) -> None:
        """设置音量 (0.0 - 1.0)"""
        ...
    
    @abstractmethod
    def set_voice(self, voice_id: str) -> None:
        """设置语音"""
        ...
    
    @abstractmethod
    def list_voices(self) -> List["VoiceInfo"]:
        """列出可用语音"""
        ...


@dataclass
class VoiceInfo:
    """语音信息"""
    id: str
    name: str
    language: str
    gender: str = ""


class Pyttsx3TTS(TTSEngine):
    """
    pyttsx3 TTS 引擎。
    
    跨平台 TTS 库，支持 Windows/macOS/Linux。
    """
    
    def __init__(self) -> None:
        try:
            import pyttsx3
            self._engine = pyttsx3.init()
            self._locked = threading.Lock()
        except ImportError:
            self._engine = None
    
    @property
    def available(self) -> bool:
        return self._engine is not None
    
    def speak(self, text: str, blocking: bool = True) -> None:
        if not self._engine:
            return
        
        if blocking:
            self._engine.say(text)
            self._engine.runAndWait()
        else:
            def run():
                with self._locked:
                    self._engine.say(text)
                    self._engine.runAndWait()
            threading.Thread(target=run, daemon=True).start()
    
    def stop(self) -> None:
        if self._engine:
            self._engine.stop()
    
    def set_rate(self, rate: int) -> None:
        if self._engine:
            self._engine.setProperty("rate", rate)
    
    def set_volume(self, volume: float) -> None:
        if self._engine:
            self._engine.setProperty("volume", max(0.0, min(1.0, volume)))
    
    def set_voice(self, voice_id: str) -> None:
        if self._engine:
            self._engine.setProperty("voice", voice_id)
    
    def list_voices(self) -> List[VoiceInfo]:
        if not self._engine:
            return []
        
        voices = self._engine.getProperty("voices")
        return [
            VoiceInfo(
                id=v.id,
                name=v.name,
                language=getattr(v, "languages", [""])[0] if hasattr(v, "languages") else "",
                gender=getattr(v, "gender", "") if hasattr(v, "gender") else "",
            )
            for v in voices
        ]
    
    def save_to_file(self, text: str, filename: str) -> bool:
        """保存为音频文件"""
        if not self._engine:
            return False
        
        try:
            self._engine.save_to_file(text, filename)
            self._engine.runAndWait()
            return True
        except Exception:
            return False


class PytesseractFallback(TTSEngine):
    """空实现（当没有 TTS 引擎时）"""
    
    @property
    def available(self) -> bool:
        return False
    
    def speak(self, text: str, blocking: bool = True) -> None:
        pass
    
    def stop(self) -> None:
        pass
    
    def set_rate(self, rate: int) -> None:
        pass
    
    def set_volume(self, volume: float) -> None:
        pass
    
    def set_voice(self, voice_id: str) -> None:
        pass
    
    def list_voices(self) -> List[VoiceInfo]:
        return []


def get_tts_engine() -> TTSEngine:
    """获取可用的 TTS 引擎"""
    engine = Pyttsx3TTS()
    if engine.available:
        return engine
    return PytesseractFallback()


# ============================================================================
# STT - Speech to Text
# ============================================================================

class STTEngine(ABC):
    """STT 引擎基类"""
    
    @abstractmethod
    def listen(self, timeout: float = 5.0) -> Optional[str]:
        """监听语音输入"""
        ...
    
    @abstractmethod
    def recognize(self, audio_data: bytes) -> Optional[str]:
        """识别音频"""
        ...
    
    @abstractmethod
    def list_microphones(self) -> List["MicrophoneInfo"]:
        """列出可用麦克风"""
        ...


@dataclass
class MicrophoneInfo:
    """麦克风信息"""
    index: int
    name: str


class SpeechRecognitionSTT(STTEngine):
    """
    SpeechRecognition STT 引擎。
    
    支持多种后端：Google Speech Recognition, Sphinx, etc.
    """
    
    def __init__(self) -> None:
        try:
            import speech_recognition as sr
            self._recognizer = sr.Recognizer()
            self._microphone = sr.Microphone()
            self._recognizer.energy_threshold = 300
        except ImportError:
            self._recognizer = None
            self._microphone = None
    
    @property
    def available(self) -> bool:
        return self._recognizer is not None
    
    def listen(self, timeout: float = 5.0) -> Optional[str]:
        if not self._recognizer or not self._microphone:
            return None
        
        import speech_recognition as sr
        
        try:
            with self._microphone as source:
                self._recognizer.adjust_for_ambient_noise(source, duration=0.5)
                audio = self._recognizer.listen(source, timeout=timeout)
            
            # 使用 Google Speech Recognition
            text = self._recognizer.recognize_google(audio)
            return text
        
        except Exception:
            return None
    
    def recognize(self, audio_data: bytes) -> Optional[str]:
        # 这个需要 AudioData 对象，简化的占位实现
        return None
    
    def list_microphones(self) -> List[MicrophoneInfo]:
        if not self._recognizer:
            return []
        
        try:
            import speech_recognition as sr
            mics = sr.Microphone.list_microphone_names()
            return [
                MicrophoneInfo(index=i, name=name)
                for i, name in enumerate(mics)
            ]
        except Exception:
            return []


def get_stt_engine() -> STTEngine:
    """获取可用的 STT 引擎"""
    engine = SpeechRecognitionSTT()
    if engine.available:
        return engine
    return None  # 无 STT 引擎时返回 None


# ============================================================================
# VoiceManager - 统一管理
# ============================================================================

class VoiceManager:
    """
    语音管理器。
    
    统一管理 TTS 和 STT。
    """
    
    def __init__(self) -> None:
        self.tts = get_tts_engine()
        self.stt: Optional[STTEngine] = get_stt_engine()
    
    @property
    def tts_available(self) -> bool:
        return isinstance(self.tts, Pyttsx3TTS)
    
    @property
    def stt_available(self) -> bool:
        return self.stt is not None
    
    def speak(self, text: str, blocking: bool = True) -> None:
        """朗读文本"""
        self.tts.speak(text, blocking=blocking)
    
    def listen(self, timeout: float = 5.0) -> Optional[str]:
        """监听语音输入"""
        if self.stt:
            return self.stt.listen(timeout=timeout)
        return None
    
    def say(self, format_str: str, **kwargs) -> None:
        """格式化输出语音"""
        text = format_str.format(**kwargs)
        self.speak(text)


# ============================================================================
# 音频播放
# ============================================================================

class AudioPlayer:
    """音频播放器"""
    
    @staticmethod
    def play_wav(file_path: Union[str, Path]) -> bool:
        """播放 WAV 文件"""
        path = Path(file_path)
        if not path.exists():
            return False
        
        system = platform.system()
        
        if system == "Windows":
            import winsound
            try:
                winsound.PlaySound(str(path), winsound.SND_FILENAME)
                return True
            except Exception:
                return False
        
        elif system == "Darwin":  # macOS
            try:
                subprocess.run(["afplay", str(path)], check=True)
                return True
            except Exception:
                return False
        
        else:  # Linux
            try:
                subprocess.run(["aplay", str(path)], check=True)
                return True
            except Exception:
                return False
    
    @staticmethod
    def play_mp3(file_path: Union[str, Path]) -> bool:
        """播放 MP3 文件"""
        path = Path(file_path)
        if not path.exists():
            return False
        
        system = platform.system()
        
        if system == "Windows":
            import winsound
            try:
                winsound.PlaySound(str(path), winsound.SND_FILENAME)
                return True
            except Exception:
                return False
        
        elif system == "Darwin":
            try:
                subprocess.run(["afplay", str(path)], check=True)
                return True
            except Exception:
                return False
        
        else:  # Linux
            try:
                subprocess.run(["mpg123", str(path)], check=True)
                return True
            except Exception:
                try:
                    subprocess.run(["mpg321", str(path)], check=True)
                    return True
                except Exception:
                    return False
        
        return False


# ============================================================================
# 全局实例
# ============================================================================

_voice_manager: Optional[VoiceManager] = None


def get_voice_manager() -> VoiceManager:
    """获取全局语音管理器"""
    global _voice_manager
    if _voice_manager is None:
        _voice_manager = VoiceManager()
    return _voice_manager


__all__ = [
    # TTS
    "TTSEngine",
    "VoiceInfo",
    "Pyttsx3TTS",
    "PytesseractFallback",
    "get_tts_engine",
    # STT
    "STTEngine",
    "MicrophoneInfo",
    "SpeechRecognitionSTT",
    "get_stt_engine",
    # Manager
    "VoiceManager",
    "get_voice_manager",
    # Player
    "AudioPlayer",
]
