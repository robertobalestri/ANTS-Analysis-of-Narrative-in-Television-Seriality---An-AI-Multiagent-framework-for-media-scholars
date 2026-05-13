import os
import logging
import gc
import subprocess
from typing import Dict, List, Optional, Any
from pathlib import Path

from app.core.logging import setup_logging
from app.services.filesystem.path_handler import PathHandler

logger = setup_logging(__name__)

class TranscriptionService:
    """
    Handles audio transcription and subtitle alignment using WhisperX.
    """
    
    def __init__(self, device: str = "cpu", model_size: str = "base", compute_type: str = "int8"):
        """
        Initialize the transcription service.
        
        Args:
            device: 'cpu' or 'cuda'
            model_size: Whisper model size (tiny, base, small, medium, large-v2, large-v3)
            compute_type: compute type for transcription (int8, float16, etc.)
        """
        self.device = device
        self.model_size = model_size
        self.compute_type = compute_type
        logger.info(f"Transcription service initialized on {self.device}")

    def extract_audio_from_video(self, video_path: str, audio_path: str) -> bool:
        """
        Extracts audio from a video file using ffmpeg.
        Converted to 16kHz mono WAV format for Whisper.
        """
        if os.path.exists(audio_path):
            logger.info(f"Audio file already exists at {audio_path}, skipping extraction.")
            return True
        
        # We should use the ffmpeg binary from our bin folder if available
        ffmpeg_bin = "ffmpeg" 
        backend_dir = Path(__file__).resolve().parents[3]
        local_ffmpeg = backend_dir / "bin" / ("ffmpeg.exe" if os.name == "nt" else "ffmpeg")
        if local_ffmpeg.exists():
            ffmpeg_bin = str(local_ffmpeg)

        logger.info(f"Extracting audio from '{video_path}' to '{audio_path}'")
        try:
            os.makedirs(os.path.dirname(audio_path), exist_ok=True)
            
            cmd = [
                ffmpeg_bin, "-i", video_path,
                "-vn",                   # No video
                "-acodec", "pcm_s16le",  # PCM 16-bit little-endian
                "-ar", "16000",          # 16kHz sample rate
                "-ac", "1",              # Mono channel
                "-y",                    # Overwrite
                audio_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, encoding='utf-8', errors='ignore', check=True)
            logger.info(f"Audio extracted successfully to {audio_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to extract audio: {e}")
            return False

    async def transcribe_video(self, video_path: str, output_srt_path: str, language: Optional[str] = None) -> Dict[str, Any]:
        """
        Full workflow: extract audio -> transcribe -> align -> save SRT.
        """
        import torch
        import whisperx
        
        audio_path = video_path.rsplit('.', 1)[0] + ".wav"
        
        if not self.extract_audio_from_video(video_path, audio_path):
            return {"status": "error", "message": "Failed to extract audio from video"}

        try:
            # 1. Transcribe
            logger.info(f"Loading WhisperX model: {self.model_size}")
            model = whisperx.load_model(self.model_size, self.device, compute_type=self.compute_type)
            
            logger.info("Loading audio")
            audio = whisperx.load_audio(audio_path)
            
            logger.info("Starting transcription")
            result = model.transcribe(audio, batch_size=16, language=language)
            
            # Clean up model
            del model
            if self.device == "cuda":
                gc.collect()
                torch.cuda.empty_cache()

            # 2. Align
            actual_language = result["language"]
            logger.info(f"Aligning transcription (language: {actual_language})")
            model_a, metadata = whisperx.load_align_model(language_code=actual_language, device=self.device)
            result = whisperx.align(result["segments"], model_a, metadata, audio, self.device, return_char_alignments=False)
            
            # Clean up alignment model
            del model_a
            if self.device == "cuda":
                gc.collect()
                torch.cuda.empty_cache()

            # 3. Convert to SRT
            srt_content = self._segments_to_srt(result["segments"])
            
            with open(output_srt_path, 'w', encoding='utf-8') as f:
                f.write(srt_content)
                
            logger.info(f"SRT saved to {output_srt_path}")
            
            # Cleanup audio file after success
            if os.path.exists(audio_path):
                os.remove(audio_path)
                
            return {
                "status": "success",
                "message": "Transcription completed",
                "srt_path": output_srt_path,
                "language": actual_language
            }

        except Exception as e:
            logger.error(f"Transcription failed: {e}")
            return {"status": "error", "message": str(e)}

    def _segments_to_srt(self, segments: List[Dict]) -> str:
        srt_content = ""
        for i, segment in enumerate(segments, 1):
            start = segment.get("start", 0)
            end = segment.get("end", 0)
            text = segment.get("text", "").strip()
            
            srt_content += f"{i}\n"
            srt_content += f"{self._format_timestamp(start)} --> {self._format_timestamp(end)}\n"
            srt_content += f"{text}\n\n"
        return srt_content

    def _format_timestamp(self, seconds: float) -> str:
        td = float(seconds)
        hours = int(td // 3600)
        minutes = int((td % 3600) // 60)
        secs = int(td % 60)
        millis = int((td % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"
