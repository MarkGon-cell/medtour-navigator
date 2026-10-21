"""
Server-side Speech-to-Text for the voice triage box.

Why this exists: the Web Speech API (SpeechRecognition) that the walk-in page
uses for dictation is Chromium-only. Firefox and Safari can RECORD audio via
getUserMedia/MediaRecorder, but they have no browser-side transcriber, so
those patients' utterances are uploaded here and transcribed on the server.

Chromium patients never reach this module -- their browser transcribes locally
and the audio never leaves the device.

Engine: faster-whisper (CTranslate2 port of OpenAI Whisper). Chosen because it
needs no API key, no GPU and no internet at request time, and because it runs
in the same process as the rest of the triage stack.

Env:
    WHISPER_MODEL   base (default) | tiny | small | medium ...
                    `base` is the sweet spot here: a few seconds of CPU per
                    utterance and accurate enough for symptom phrases in both
                    English and Hindi. `tiny` is faster but noticeably worse
                    on Indian English; `small` is better on accents.
    WHISPER_PRELOAD set to "0" to skip loading the model at import time
                    (it then loads lazily on the first transcription, which
                    makes that first request slow).
"""
import io
import logging
import os
import threading
from typing import Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

# The model is loaded once and shared: WhisperModel holds tens of megabytes of
# weights and several decode threads, so re-creating it per request would be
# both slow and memory-hungry on a CPU-only box.
_model_lock = threading.Lock()
_model = None
_load_error: Optional[str] = None

# Whisper's native input format. Anything handed to the model must already be
# 16 kHz, mono, float32 with samples in [-1, 1].
_SAMPLE_RATE = 16000

# Guard rail: a runaway recorder must not make the CPU grind for minutes.
MAX_UPLOAD_BYTES = 8 * 1024 * 1024


def _model_name() -> str:
    return os.getenv("WHISPER_MODEL", "base").strip() or "base"


def preload_model() -> None:
    """Load the model at import time so the first patient is not the one who waits."""
    if os.getenv("WHISPER_PRELOAD", "1").strip() in {"0", "false", "no"}:
        logger.info("[STT] Whisper preloading disabled (WHISPER_PRELOAD=0); loads on first use.")
        return
    # Never let a warm-up failure take the API down: triage still works without
    # voice, and the endpoint reports the real error when a patient calls it.
    threading.Thread(target=get_model, name="whisper-preload", daemon=True).start()


def get_model():
    """Return the shared WhisperModel, loading it on first use. None on failure."""
    global _model, _load_error
    if _model is not None:
        return _model

    with _model_lock:
        if _model is not None:
            return _model

        try:
            from faster_whisper import WhisperModel
        except Exception as exc:  # noqa: BLE001 - any import failure is fatal here
            _load_error = (
                "Speech-to-text is not installed on this server. "
                "Run `pip install faster-whisper` and restart it."
            )
            logger.warning("[STT] faster-whisper is not importable: %s", exc)
            return None

        try:
            name = _model_name()
            logger.info("[STT] Loading Whisper model '%s' (CPU, int8)...", name)
            _model = WhisperModel(name, device="cpu", compute_type="int8")
            logger.info("[STT] Whisper model '%s' ready.", name)
            return _model
        except Exception as exc:  # noqa: BLE001 - download/runtime failures surface to the caller
            _load_error = f"Speech-to-text failed to start on this server: {exc}"
            logger.warning("[STT] Whisper model load failed: %s", exc)
            return None


def _decode_audio(audio_bytes: bytes) -> np.ndarray:
    """
    Turn one recording into Whisper's input format, whatever container the
    browser produced (Ogg/Opus from Firefox, WebM/Opus from Chromium, MP4/AAC
    from Safari, WAV).

    Decoding happens HERE on purpose. faster-whisper's own `decode_audio()`
    calls `av.open(..., metadata_errors="ignore")`, and PyAV removed that
    keyword in 19.x -- so on a current install every transcription died with a
    TypeError before a single word was read. Handing the model a ready-made
    ndarray keeps it off that code path entirely, and as a bonus there is no
    temp file: PyAV sniffs the container from the raw bytes.
    """
    import av  # heavyweight; only needed once a patient actually dictates

    with av.open(io.BytesIO(audio_bytes)) as container:
        stream = next((s for s in container.streams if s.type == "audio"), None)
        if stream is None:
            raise ValueError("the recording has no audio track")

        # fltp = 32-bit float, planar; mono + 16 kHz is what Whisper expects,
        # so the resampler handles format, channel mix and rate in one pass.
        resampler = av.AudioResampler(format="fltp", layout="mono", rate=_SAMPLE_RATE)
        frames = []
        for frame in container.decode(stream):
            frames.extend(resampler.resample(frame))
        try:
            # Flush what the resampler still buffers, or the last syllable is
            # chopped off. Older PyAV has no flush call -- hence the guard.
            frames.extend(resampler.resample(None))
        except Exception:  # noqa: BLE001
            pass

    if not frames:
        raise ValueError("the recording contained no audio")

    # Each frame is (channels, samples) = (1, n) in mono; stitch them end to end.
    return np.concatenate([f.to_ndarray() for f in frames], axis=1).reshape(-1).astype(
        np.float32, copy=False
    )


def transcribe(audio_bytes: bytes, content_type: str = "") -> Tuple[str, Optional[str]]:
    """
    Turn one recorded utterance into text.

    Returns `(text, language)`. Raises RuntimeError with a patient-readable
    message when transcription is impossible, so the caller can pass it
    straight through as a 5xx detail instead of inventing one.
    """
    model = get_model()
    if model is None:
        raise RuntimeError(_load_error or "Speech-to-text is unavailable on this server.")

    try:
        audio = _decode_audio(audio_bytes)
    except Exception as exc:  # noqa: BLE001 - decode failures become a readable patient message
        logger.warning("[STT] could not decode %d-byte %r upload: %s", len(audio_bytes), content_type, exc)
        raise RuntimeError("That recording could not be decoded. Please try speaking again.") from exc

    def _run(use_vad: bool) -> Tuple[str, Optional[str]]:
        # Materialise the transcript INSIDE the call: model.transcribe returns
        # a generator, so decode errors only surface while it is consumed.
        segments, info = model.transcribe(
            audio,
            # Greedy decoding: a beam search buys accuracy we do not need for
            # short symptom phrases and costs real latency on CPU.
            beam_size=1,
            # Drop silence and room noise so a long pause before speaking does
            # not stretch the transcription or produce hallucinated filler.
            vad_filter=use_vad,
            vad_parameters={"min_silence_duration_ms": 500} if use_vad else None,
        )
        text = " ".join(segment.text.strip() for segment in segments).strip()
        return text, getattr(info, "language", None)

    try:
        text, language = _run(True)
    except Exception as exc:  # noqa: BLE001
        # The Silero VAD model is fetched from the HF Hub on first use; if that
        # is unreachable the transcription is still perfectly fine without it.
        logger.warning("[STT] VAD pass failed (%s); retrying without voice activity detection", exc)
        try:
            text, language = _run(False)
        except Exception as exc2:  # noqa: BLE001
            logger.warning("[STT] transcription failed: %s", exc2)
            raise RuntimeError(
                "That recording could not be transcribed. Please try speaking again."
            ) from exc2

    logger.info(
        "[STT] transcribed %d bytes (%s) -> %r (lang=%s)",
        len(audio_bytes),
        content_type,
        text[:80],
        language,
    )
    return text, language


preload_model()
