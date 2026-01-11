"""
WhisperWorker - Audio/video transcription using OpenAI Whisper.

Pool: gpu-whisper
Purpose: Transcribe audio and video files to text with timestamps.
"""

from typing import Dict, Any, List, Optional
import logging
import os
import tempfile
import base64
import json

from .base import BaseWorker

logger = logging.getLogger(__name__)


class WhisperWorker(BaseWorker):
    """
    Worker for audio/video transcription using Whisper.

    Uses faster-whisper (CTranslate2 optimized) for better performance,
    with fallback to openai-whisper if faster-whisper is not available.

    Environment variables:
    - WHISPER_MODEL: Model size (tiny, base, small, medium, large-v2, large-v3)
    - WHISPER_DEVICE: Device to use (cuda, cpu, auto)
    - WHISPER_COMPUTE_TYPE: Compute precision (float16, int8, float32)

    Operations:
    1. transcribe - Basic transcription
       Input: {"audio_path": "...", "language": null, "task": "transcribe"}
       Output: {"text": "...", "segments": [...], "language": "en", "duration": 120.5}

    2. transcribe_with_timestamps - Word-level timestamps
       Input: {"audio_path": "...", "word_timestamps": true}
       Output: {"text": "...", "words": [{"word": "hello", "start": 0.0, "end": 0.5}]}

    3. translate - Transcribe and translate to English
       Input: {"audio_path": "...", "task": "translate"}
       Output: {"text": "...", "original_language": "fr"}

    4. detect_language - Detect spoken language
       Input: {"audio_path": "..."}
       Output: {"language": "en", "probability": 0.98}

    5. segments - Get timed segments for subtitles
       Input: {"audio_path": "...", "format": "srt|vtt|json"}
       Output: {"segments": [...], "subtitle_text": "1\n00:00:00,000 --> ..."}
    """

    pool = "gpu-whisper"
    name = "WhisperWorker"
    job_timeout = 600.0  # Transcription can take a while

    # Model configuration from environment
    DEFAULT_MODEL = os.environ.get("WHISPER_MODEL", "base")
    DEFAULT_DEVICE = os.environ.get("WHISPER_DEVICE", "auto")
    DEFAULT_COMPUTE_TYPE = os.environ.get("WHISPER_COMPUTE_TYPE", "float16")

    # Supported audio/video formats
    AUDIO_FORMATS = {".mp3", ".wav", ".m4a", ".flac", ".ogg", ".webm"}
    VIDEO_FORMATS = {".mp4", ".mkv", ".avi", ".mov", ".webm"}

    # Class-level lazy-loaded model
    _model = None
    _model_name = None
    _device = None
    _using_faster_whisper = False

    @classmethod
    def _get_model(cls):
        """
        Get or initialize the Whisper model.

        Lazy loads the model on first use. Tries faster-whisper first,
        falls back to openai-whisper if not available.

        Returns:
            Tuple of (model, model_name, device, using_faster_whisper)
        """
        if cls._model is None:
            # Determine device
            device = cls.DEFAULT_DEVICE
            if device == "auto":
                try:
                    import torch
                    device = "cuda" if torch.cuda.is_available() else "cpu"
                except ImportError:
                    device = "cpu"

            # Try faster-whisper first (CTranslate2, more efficient)
            try:
                from faster_whisper import WhisperModel

                logger.info(
                    f"Loading Whisper model (faster-whisper): {cls.DEFAULT_MODEL} "
                    f"on {device} with {cls.DEFAULT_COMPUTE_TYPE}"
                )

                # For CPU, use int8 or float32
                compute_type = cls.DEFAULT_COMPUTE_TYPE
                if device == "cpu" and compute_type == "float16":
                    compute_type = "int8"
                    logger.info(f"Adjusted compute_type to {compute_type} for CPU")

                cls._model = WhisperModel(
                    cls.DEFAULT_MODEL,
                    device=device,
                    compute_type=compute_type
                )
                cls._model_name = cls.DEFAULT_MODEL
                cls._device = device
                cls._using_faster_whisper = True

                logger.info(
                    f"Loaded faster-whisper model {cls._model_name} on {cls._device}"
                )

            except ImportError:
                logger.warning(
                    "faster-whisper not available, falling back to openai-whisper"
                )
                try:
                    import whisper

                    logger.info(
                        f"Loading Whisper model (openai-whisper): {cls.DEFAULT_MODEL}"
                    )

                    cls._model = whisper.load_model(cls.DEFAULT_MODEL, device=device)
                    cls._model_name = cls.DEFAULT_MODEL
                    cls._device = device
                    cls._using_faster_whisper = False

                    logger.info(
                        f"Loaded openai-whisper model {cls._model_name} on {cls._device}"
                    )

                except ImportError:
                    raise ImportError(
                        "Neither faster-whisper nor openai-whisper is installed. "
                        "Install with: pip install faster-whisper OR pip install openai-whisper"
                    )
                except Exception as e:
                    raise RuntimeError(f"Failed to load whisper model: {e}")

        return cls._model, cls._model_name, cls._device, cls._using_faster_whisper

    def _validate_audio_path(self, audio_path: str) -> bool:
        """
        Validate that the audio file exists and has a supported format.

        Args:
            audio_path: Path to audio/video file

        Returns:
            True if valid

        Raises:
            ValueError: If path is invalid or format unsupported
        """
        if not os.path.exists(audio_path):
            raise ValueError(f"Audio file not found: {audio_path}")

        ext = os.path.splitext(audio_path)[1].lower()
        if ext not in self.AUDIO_FORMATS and ext not in self.VIDEO_FORMATS:
            raise ValueError(
                f"Unsupported format: {ext}. "
                f"Supported: {self.AUDIO_FORMATS | self.VIDEO_FORMATS}"
            )

        return True

    def _save_base64_audio(self, audio_base64: str, format: str) -> str:
        """
        Save base64-encoded audio to a temporary file.

        Args:
            audio_base64: Base64-encoded audio data
            format: Audio format (mp3, wav, etc.)

        Returns:
            Path to temporary file

        Raises:
            ValueError: If format is invalid
        """
        if not format.startswith("."):
            format = f".{format}"

        if format.lower() not in self.AUDIO_FORMATS and format.lower() not in self.VIDEO_FORMATS:
            raise ValueError(f"Unsupported format: {format}")

        # Decode base64
        audio_data = base64.b64decode(audio_base64)

        # Save to temp file
        with tempfile.NamedTemporaryFile(
            mode="wb", suffix=format, delete=False
        ) as f:
            f.write(audio_data)
            temp_path = f.name

        logger.info(f"Saved base64 audio to temp file: {temp_path}")
        return temp_path

    def _format_timestamp(self, seconds: float) -> str:
        """
        Format seconds to SRT/VTT timestamp (HH:MM:SS,mmm).

        Args:
            seconds: Time in seconds

        Returns:
            Formatted timestamp string
        """
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        millis = int((seconds % 1) * 1000)
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

    def _format_timestamp_vtt(self, seconds: float) -> str:
        """
        Format seconds to VTT timestamp (HH:MM:SS.mmm).

        Args:
            seconds: Time in seconds

        Returns:
            Formatted timestamp string
        """
        timestamp = self._format_timestamp(seconds)
        return timestamp.replace(",", ".")

    def _segments_to_srt(self, segments: List[Dict[str, Any]]) -> str:
        """
        Convert segments to SRT subtitle format.

        Args:
            segments: List of segment dicts with start, end, text

        Returns:
            SRT-formatted string
        """
        srt_lines = []
        for i, seg in enumerate(segments, 1):
            start = self._format_timestamp(seg["start"])
            end = self._format_timestamp(seg["end"])
            text = seg["text"].strip()

            srt_lines.append(f"{i}")
            srt_lines.append(f"{start} --> {end}")
            srt_lines.append(text)
            srt_lines.append("")  # Blank line between segments

        return "\n".join(srt_lines)

    def _segments_to_vtt(self, segments: List[Dict[str, Any]]) -> str:
        """
        Convert segments to WebVTT subtitle format.

        Args:
            segments: List of segment dicts with start, end, text

        Returns:
            VTT-formatted string
        """
        vtt_lines = ["WEBVTT", ""]

        for seg in segments:
            start = self._format_timestamp_vtt(seg["start"])
            end = self._format_timestamp_vtt(seg["end"])
            text = seg["text"].strip()

            vtt_lines.append(f"{start} --> {end}")
            vtt_lines.append(text)
            vtt_lines.append("")  # Blank line between segments

        return "\n".join(vtt_lines)

    async def _transcribe_faster_whisper(
        self,
        model,
        audio_path: str,
        language: Optional[str] = None,
        task: str = "transcribe",
        word_timestamps: bool = False,
    ) -> Dict[str, Any]:
        """
        Transcribe using faster-whisper.

        Args:
            model: faster-whisper model instance
            audio_path: Path to audio file
            language: Language code (None for auto-detect)
            task: "transcribe" or "translate"
            word_timestamps: Whether to include word-level timestamps

        Returns:
            Dict with transcription results
        """
        segments_list = []
        full_text = []

        # Transcribe
        segments, info = model.transcribe(
            audio_path,
            language=language,
            task=task,
            beam_size=5,
            word_timestamps=word_timestamps,
        )

        # Process segments
        for segment in segments:
            seg_dict = {
                "id": segment.id,
                "start": segment.start,
                "end": segment.end,
                "text": segment.text,
                "avg_logprob": segment.avg_logprob,
                "no_speech_prob": segment.no_speech_prob,
            }

            # Add word-level timestamps if requested
            if word_timestamps and hasattr(segment, "words") and segment.words:
                seg_dict["words"] = [
                    {
                        "word": word.word,
                        "start": word.start,
                        "end": word.end,
                        "probability": word.probability,
                    }
                    for word in segment.words
                ]

            segments_list.append(seg_dict)
            full_text.append(segment.text)

        result = {
            "text": " ".join(full_text).strip(),
            "segments": segments_list,
            "language": info.language,
            "language_probability": info.language_probability,
            "duration": info.duration,
        }

        return result

    async def _transcribe_openai_whisper(
        self,
        model,
        audio_path: str,
        language: Optional[str] = None,
        task: str = "transcribe",
        word_timestamps: bool = False,
    ) -> Dict[str, Any]:
        """
        Transcribe using openai-whisper.

        Args:
            model: openai-whisper model instance
            audio_path: Path to audio file
            language: Language code (None for auto-detect)
            task: "transcribe" or "translate"
            word_timestamps: Whether to include word-level timestamps

        Returns:
            Dict with transcription results
        """
        # Transcribe
        result = model.transcribe(
            audio_path,
            language=language,
            task=task,
            word_timestamps=word_timestamps,
        )

        # Extract segments
        segments_list = []
        for seg in result.get("segments", []):
            seg_dict = {
                "id": seg["id"],
                "start": seg["start"],
                "end": seg["end"],
                "text": seg["text"],
                "avg_logprob": seg.get("avg_logprob", 0.0),
                "no_speech_prob": seg.get("no_speech_prob", 0.0),
            }

            # Add word-level timestamps if available
            if word_timestamps and "words" in seg:
                seg_dict["words"] = seg["words"]

            segments_list.append(seg_dict)

        return {
            "text": result["text"],
            "segments": segments_list,
            "language": result.get("language", "unknown"),
        }

    async def _operation_transcribe(
        self, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Operation: Basic transcription.

        Args:
            payload: Job payload with audio_path, language, task

        Returns:
            Dict with text, segments, language, duration
        """
        # Get model
        model, model_name, device, using_faster = self._get_model()

        # Get audio path (from path or base64)
        audio_path = payload.get("audio_path")
        temp_file = None

        if not audio_path:
            audio_base64 = payload.get("audio_base64")
            if not audio_base64:
                raise ValueError("Either 'audio_path' or 'audio_base64' is required")

            format = payload.get("format", "mp3")
            audio_path = self._save_base64_audio(audio_base64, format)
            temp_file = audio_path

        try:
            # Validate
            self._validate_audio_path(audio_path)

            # Get parameters
            language = payload.get("language")
            task = payload.get("task", "transcribe")

            logger.info(
                f"Transcribing {audio_path} (language={language}, task={task})"
            )

            # Transcribe
            if using_faster:
                result = await self._transcribe_faster_whisper(
                    model, audio_path, language=language, task=task
                )
            else:
                result = await self._transcribe_openai_whisper(
                    model, audio_path, language=language, task=task
                )

            result["model"] = model_name
            result["device"] = device
            result["success"] = True

            return result

        finally:
            # Clean up temp file if we created one
            if temp_file and os.path.exists(temp_file):
                try:
                    os.unlink(temp_file)
                    logger.info(f"Cleaned up temp file: {temp_file}")
                except Exception as e:
                    logger.warning(f"Failed to clean up temp file {temp_file}: {e}")

    async def _operation_transcribe_with_timestamps(
        self, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Operation: Transcription with word-level timestamps.

        Args:
            payload: Job payload with audio_path, word_timestamps=True

        Returns:
            Dict with text and word-level timestamps
        """
        # Get model
        model, model_name, device, using_faster = self._get_model()

        # Get audio path
        audio_path = payload.get("audio_path")
        temp_file = None

        if not audio_path:
            audio_base64 = payload.get("audio_base64")
            if not audio_base64:
                raise ValueError("Either 'audio_path' or 'audio_base64' is required")

            format = payload.get("format", "mp3")
            audio_path = self._save_base64_audio(audio_base64, format)
            temp_file = audio_path

        try:
            # Validate
            self._validate_audio_path(audio_path)

            language = payload.get("language")

            logger.info(f"Transcribing with word timestamps: {audio_path}")

            # Transcribe with word timestamps
            if using_faster:
                result = await self._transcribe_faster_whisper(
                    model, audio_path, language=language, word_timestamps=True
                )
            else:
                result = await self._transcribe_openai_whisper(
                    model, audio_path, language=language, word_timestamps=True
                )

            # Extract all words from segments
            all_words = []
            for seg in result["segments"]:
                if "words" in seg:
                    all_words.extend(seg["words"])

            result["words"] = all_words
            result["model"] = model_name
            result["device"] = device
            result["success"] = True

            return result

        finally:
            if temp_file and os.path.exists(temp_file):
                try:
                    os.unlink(temp_file)
                except Exception as e:
                    logger.warning(f"Failed to clean up temp file {temp_file}: {e}")

    async def _operation_translate(
        self, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Operation: Transcribe and translate to English.

        Args:
            payload: Job payload with audio_path

        Returns:
            Dict with translated text and original language
        """
        # Override task to translate
        payload["task"] = "translate"

        result = await self._operation_transcribe(payload)

        # Add original language info
        result["original_language"] = result.get("language", "unknown")

        return result

    async def _operation_detect_language(
        self, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Operation: Detect spoken language.

        Args:
            payload: Job payload with audio_path

        Returns:
            Dict with language code and probability
        """
        # Get model
        model, model_name, device, using_faster = self._get_model()

        # Get audio path
        audio_path = payload.get("audio_path")
        temp_file = None

        if not audio_path:
            audio_base64 = payload.get("audio_base64")
            if not audio_base64:
                raise ValueError("Either 'audio_path' or 'audio_base64' is required")

            format = payload.get("format", "mp3")
            audio_path = self._save_base64_audio(audio_base64, format)
            temp_file = audio_path

        try:
            # Validate
            self._validate_audio_path(audio_path)

            logger.info(f"Detecting language: {audio_path}")

            if using_faster:
                # For faster-whisper, we need to transcribe to get language
                segments, info = model.transcribe(audio_path, beam_size=5)
                # Consume first segment to trigger detection
                _ = next(segments, None)

                return {
                    "language": info.language,
                    "probability": info.language_probability,
                    "model": model_name,
                    "device": device,
                    "success": True,
                }
            else:
                # For openai-whisper, detect_language is a separate method
                import whisper

                # Load audio
                audio = whisper.load_audio(audio_path)
                audio = whisper.pad_or_trim(audio)

                # Detect language
                mel = whisper.log_mel_spectrogram(audio).to(model.device)
                _, probs = model.detect_language(mel)
                detected_language = max(probs, key=probs.get)

                return {
                    "language": detected_language,
                    "probability": probs[detected_language],
                    "model": model_name,
                    "device": device,
                    "success": True,
                }

        finally:
            if temp_file and os.path.exists(temp_file):
                try:
                    os.unlink(temp_file)
                except Exception as e:
                    logger.warning(f"Failed to clean up temp file {temp_file}: {e}")

    async def _operation_segments(
        self, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Operation: Get timed segments for subtitles.

        Args:
            payload: Job payload with audio_path, format (srt|vtt|json)

        Returns:
            Dict with segments and formatted subtitle text
        """
        # First transcribe to get segments
        transcribe_result = await self._operation_transcribe(payload)

        segments = transcribe_result["segments"]
        format = payload.get("format", "json").lower()

        logger.info(f"Formatting {len(segments)} segments as {format}")

        # Format based on requested type
        subtitle_text = None
        if format == "srt":
            subtitle_text = self._segments_to_srt(segments)
        elif format == "vtt":
            subtitle_text = self._segments_to_vtt(segments)
        elif format != "json":
            raise ValueError(f"Unsupported format: {format}. Use srt, vtt, or json")

        return {
            "segments": segments,
            "subtitle_text": subtitle_text,
            "format": format,
            "count": len(segments),
            "model": transcribe_result.get("model"),
            "device": transcribe_result.get("device"),
            "success": True,
        }

    async def process_job(self, job_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a Whisper transcription job.

        Args:
            job_id: Unique job identifier
            payload: Job data containing:
                - operation: Operation to perform (transcribe, translate, etc.)
                - audio_path: Path to audio/video file OR
                - audio_base64: Base64-encoded audio data
                - format: Audio format (if using base64)
                - language: Optional language code
                - task: "transcribe" or "translate"
                - word_timestamps: Include word-level timestamps
                - format: Subtitle format (srt, vtt, json)

        Returns:
            Dict with operation results and success flag

        Raises:
            ValueError: If payload is invalid or operation unknown
            Exception: If transcription fails
        """
        operation = payload.get("operation", "transcribe")

        logger.info(f"Job {job_id}: Whisper operation '{operation}'")

        # Route to appropriate operation handler
        if operation == "transcribe":
            return await self._operation_transcribe(payload)
        elif operation == "transcribe_with_timestamps":
            return await self._operation_transcribe_with_timestamps(payload)
        elif operation == "translate":
            return await self._operation_translate(payload)
        elif operation == "detect_language":
            return await self._operation_detect_language(payload)
        elif operation == "segments":
            return await self._operation_segments(payload)
        else:
            raise ValueError(
                f"Unknown operation: {operation}. "
                f"Valid operations: transcribe, transcribe_with_timestamps, "
                f"translate, detect_language, segments"
            )


def run_whisper_worker(database_url: str = None, worker_id: str = None):
    """
    Convenience function to run a WhisperWorker.

    Args:
        database_url: PostgreSQL connection URL (defaults to env var)
        worker_id: Optional worker ID (auto-generated if not provided)

    Example:
        python -m arkham_frame.workers.whisper_worker
    """
    import asyncio
    worker = WhisperWorker(database_url=database_url, worker_id=worker_id)
    asyncio.run(worker.run())


if __name__ == "__main__":
    # Allow running directly: python -m arkham_frame.workers.whisper_worker
    run_whisper_worker()
