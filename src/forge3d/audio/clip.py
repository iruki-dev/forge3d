"""AudioClip — WAV/OGG 파일 로드 + PCM 버퍼."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass
class AudioClip:
    """PCM 오디오 데이터를 담는 불변 데이터 클래스."""

    name: str
    samples: np.ndarray  # (N,) 또는 (N, channels) float32, [-1.0, 1.0]
    sample_rate: int
    channels: int

    @classmethod
    def load(cls, path: str | Path) -> AudioClip:
        """WAV/OGG/FLAC 파일을 float32 PCM 배열로 로드한다.

        soundfile이 없으면 순수 Python WAV 파서(stdlib)로 폴백.
        """
        path = Path(path)
        try:
            import soundfile as sf

            data, sr = sf.read(str(path), dtype="float32", always_2d=False)
        except ImportError:
            data, sr = _load_wav_stdlib(path)

        ch = 1 if data.ndim == 1 else data.shape[1]
        return cls(name=path.stem, samples=data, sample_rate=sr, channels=ch)

    @classmethod
    def from_sine(
        cls,
        freq: float = 440.0,
        duration: float = 0.5,
        sample_rate: int = 44100,
        name: str = "sine",
    ) -> AudioClip:
        """테스트용: 사인파 AudioClip 생성."""
        t = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
        samples = (np.sin(2 * np.pi * freq * t) * 0.5).astype(np.float32)
        return cls(name=name, samples=samples, sample_rate=sample_rate, channels=1)

    @property
    def duration(self) -> float:
        n = self.samples.shape[0]
        return n / self.sample_rate

    def to_pcm16(self) -> bytes:
        """16-bit PCM bytes 변환 (OpenAL AL_FORMAT_MONO16 등)."""
        s = np.clip(self.samples.flatten(), -1.0, 1.0)
        return (s * 32767).astype(np.int16).tobytes()


def _load_wav_stdlib(path: Path) -> tuple[np.ndarray, int]:
    """stdlib wave 모듈로 WAV를 float32로 읽는다."""
    import wave

    with wave.open(str(path), "rb") as wf:
        n_frames = wf.getnframes()
        n_channels = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        sr = wf.getframerate()
        raw = wf.readframes(n_frames)

    dtype_map: dict[int, type[np.signedinteger]] = {1: np.int8, 2: np.int16, 4: np.int32}
    dtype = dtype_map.get(sampwidth, np.int16)
    data = np.frombuffer(raw, dtype=dtype).astype(np.float32)
    # 정규화
    data /= float(np.iinfo(dtype).max)
    if n_channels > 1:
        data = data.reshape(-1, n_channels)
    return data, sr
