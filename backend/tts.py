import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

import numpy as np
import soundfile as sf
import pyttsx3

VOICES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "voices")
CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tts_cache")

os.makedirs(VOICES_DIR, exist_ok=True)
os.makedirs(CACHE_DIR, exist_ok=True)

# Configuração da voz feminina fofa (ajustável)
DEFAULT_VOICE = "female_fofinha"

# Configurações para pyttsx3
VOICE_SETTINGS = {
    "rate": 200,  # Words per minute
    "volume": 0.9,  # Volume (0.0 to 1.0)
    "voice_id": None,  # Will be set to female voice if available
}


@dataclass
class TTSResult:
    audio: np.ndarray
    sample_rate: int
    phonemes: Optional[list] = None


class TTSEngine:
    def __init__(self):
        self.engine = pyttsx3.init()
        self._configure_voice()
        
    def _configure_voice(self):
        """Configure the TTS engine with female voice settings."""
        # Get available voices
        voices = self.engine.getProperty('voices')
        
        # Try to find a female voice
        female_voice = None
        for voice in voices:
            if 'female' in voice.name.lower() or 'woman' in voice.name.lower():
                female_voice = voice
                break
        
        # Set voice properties
        if female_voice:
            self.engine.setProperty('voice', female_voice.id)
        else:
            # Use first available voice if no female voice found
            if voices:
                self.engine.setProperty('voice', voices[0].id)
        
        self.engine.setProperty('rate', VOICE_SETTINGS["rate"])
        self.engine.setProperty('volume', VOICE_SETTINGS["volume"])

    def synthesize(self, text: str, speed: Optional[float] = None) -> TTSResult:
        """Synthesize text to speech using pyttsx3."""
        if not text.strip():
            return TTSResult(np.zeros(22050), 22050)

        output_path = os.path.join(CACHE_DIR, f"tts_{hash(text) % 1000000}.wav")
        
        # Check cache first
        if os.path.exists(output_path):
            audio, sample_rate = sf.read(output_path)
            return TTSResult(audio, sample_rate)

        try:
            # Save to file
            self.engine.save_to_file(text, output_path)
            self.engine.runAndWait()
            
            # Load the generated audio
            audio, sample_rate = sf.read(output_path)
            
            # Convert to mono if needed
            if len(audio.shape) > 1:
                audio = np.mean(audio, axis=1)
            
            return TTSResult(audio, sample_rate)
        except Exception as e:
            print(f"Erro ao gerar áudio: {e}")
            return TTSResult(np.zeros(22050), 22050)


tts_engine = TTSEngine()


def get_tts() -> TTSEngine:
    return tts_engine


if __name__ == "__main__":
    # Teste local
    tts = get_tts()
    result = tts.synthesize("Olá! Eu sou uma assistente virtual fofa!")
    print(f"Áudio gerado com sucesso! Taxa de amostragem: {result.sample_rate} Hz")
    print(f"Duração: {len(result.audio) / result.sample_rate:.2f} segundos")
