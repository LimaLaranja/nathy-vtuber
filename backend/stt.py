import os
from dataclasses import dataclass
from typing import Optional, Tuple

import numpy as np
import torch
import torchaudio
from faster_whisper import WhisperModel

MODEL_SIZE = "small"  # Good balance between speed and accuracy
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
COMPUTE_TYPE = "float16" if DEVICE == "cuda" else "int8"
MODEL_CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "whisper_models")


@dataclass
class STTResult:
    text: str
    language: str
    confidence: float
    segments: list


class SpeechToText:
    def __init__(self, model_size: str = MODEL_SIZE, device: str = DEVICE):
        self.model_size = model_size
        self.device = device
        self.model = None
        self._load_model()

    def _load_model(self):
        if self.model is None:
            print(f"Loading Whisper model ({self.model_size})...")
            self.model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=COMPUTE_TYPE,
                download_root=MODEL_CACHE_DIR,
            )
            print("Whisper model loaded!")

    def transcribe(
        self,
        audio_data: np.ndarray,
        sample_rate: int = 16000,
        language: Optional[str] = "pt",
        initial_prompt: Optional[str] = None,
    ) -> STTResult:
        """Transcribe audio data to text using Whisper.
        
        Args:
            audio_data: Numpy array of audio samples (mono, 16kHz)
            sample_rate: Sample rate of the audio data
            language: Language code (e.g., 'pt' for Portuguese)
            initial_prompt: Optional prompt to guide the model
            
        Returns:
            STTResult containing the transcription and metadata
        """
        if self.model is None:
            self._load_model()

        # Resample if needed
        if sample_rate != 16000:
            audio_data = self._resample_audio(audio_data, sample_rate)

        # Convert to mono if needed
        if len(audio_data.shape) > 1:
            audio_data = np.mean(audio_data, axis=0)

        # Convert to float32 for Whisper
        if audio_data.dtype != np.float32:
            audio_data = audio_data.astype(np.float32) / 32768.0

        # Transcribe
        segments, info = self.model.transcribe(
            audio_data,
            language=language,
            initial_prompt=initial_prompt,
            beam_size=5,  # Good balance between speed and accuracy
            condition_on_previous_text=False,  # Disable for better performance
        )

        # Convert segments to list and get full text
        segments_list = []
        full_text = []
        for segment in segments:
            segments_list.append({
                "start": segment.start,
                "end": segment.end,
                "text": segment.text,
                "words": [{"word": w.word, "start": w.start, "end": w.end, "score": w.probability} 
                         for w in (segment.words or [])]
            })
            full_text.append(segment.text)

        return STTResult(
            text="".join(full_text).strip(),
            language=info.language,
            confidence=info.language_probability,
            segments=segments_list,
        )

    def _resample_audio(self, audio_data: np.ndarray, original_rate: int) -> np.ndarray:
        """Resample audio to 16kHz if needed."""
        if original_rate == 16000:
            return audio_data
            
        # Convert to PyTorch tensor for resampling
        audio_tensor = torch.from_numpy(audio_data).float()
        if len(audio_tensor.shape) == 1:
            audio_tensor = audio_tensor.unsqueeze(0)  # Add channel dimension
            
        # Resample
        resampler = torchaudio.transforms.Resample(
            orig_freq=original_rate,
            new_freq=16000,
            resampling_method="kaiser_window",
            lowpass_filter_width=6,
            rolloff=0.99,
            dtype=audio_tensor.dtype,
        )
        
        resampled = resampler(audio_tensor)
        return resampled.squeeze().numpy()


# Global instance
stt_engine = SpeechToText()


def get_stt() -> SpeechToText:
    return stt_engine


if __name__ == "__main__":
    # Test with a sample audio file (uncomment to test)
    # audio_path = "sample_pt.wav"
    # audio, sr = torchaudio.load(audio_path)
    # stt = get_stt()
    # result = stt.transcribe(audio[0].numpy(), sr)
    # print(f"Transcription: {result.text}")
    pass
