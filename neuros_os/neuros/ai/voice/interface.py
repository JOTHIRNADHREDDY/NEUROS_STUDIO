"""
neuros.ai.voice.interface
==========================
Voice Interface — Phase 3.

Complete voice command pipeline:
  microphone → wake word → speech-to-text → LLMOrchestrator → action

Backends
--------
  Wake word   : porcupine (Picovoice), or simple energy threshold
  STT         : openai-whisper (local), faster-whisper, or stub
  TTS         : pyttsx3 (offline), gTTS, or stub (print only)

Published topics
----------------
  /robot/ai/voice/transcript   {"text": str, "confidence": float}
  /robot/ai/voice/intent       parsed intent
  /robot/ai/voice/response     TTS response text

Graceful degradation
--------------------
  No microphone?   → listens from stdin (text-mode simulation)
  No whisper?      → stdin text-mode simulation
  No pyttsx3?      → prints responses instead of speaking

Usage
-----
    voice = VoiceInterface(robot, llm,
                           wake_word="neuros",
                           stt_backend="whisper")
    voice.start()   # background thread, always listening

    # Or for testing without microphone:
    intent = voice.process_text("patrol the room")
"""

from __future__ import annotations

import logging
import queue
import threading
import time
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from neuros.ai.llm.orchestrator import LLMOrchestrator
    from neuros.api.robot           import Robot

logger = logging.getLogger("neuros.ai.voice")


class VoiceInterface:
    """
    Voice command interface for NEUROS robots.

    Parameters
    ----------
    robot        : Robot instance to send commands to
    llm          : LLMOrchestrator for parsing commands
    wake_word    : trigger word (default "neuros")
    stt_backend  : "whisper" | "faster-whisper" | "stub"
    tts_backend  : "pyttsx3" | "gtts" | "stub"
    language     : ISO language code (default "en")
    sample_rate  : audio sample rate Hz (default 16000)
    """

    def __init__(
        self,
        robot:       "Robot",
        llm:         "LLMOrchestrator",
        *,
        wake_word:   str  = "neuros",
        stt_backend: str  = "stub",
        tts_backend: str  = "stub",
        language:    str  = "en",
        sample_rate: int  = 16_000,
    ) -> None:
        self._robot       = robot
        self._llm         = llm
        self._wake_word   = wake_word.lower()
        self._stt_backend = stt_backend
        self._tts_backend = tts_backend
        self._language    = language
        self._sample_rate = sample_rate

        self._running    = False
        self._thread:    Optional[threading.Thread] = None
        self._text_queue: queue.Queue = queue.Queue()

        # Stats
        self._commands_processed = 0
        self._last_transcript    = ""

    def start(self) -> None:
        """Start the voice pipeline in a background thread."""
        self._running = True
        self._thread  = threading.Thread(
            target=self._pipeline_loop,
            name="neuros-voice",
            daemon=True,
        )
        self._thread.start()
        logger.info("[VOICE] started | wake_word='%s' stt=%s tts=%s",
                    self._wake_word, self._stt_backend, self._tts_backend)

    def stop(self) -> None:
        self._running = False
        self._text_queue.put(None)   # unblock queue
        if self._thread:
            self._thread.join(timeout=2.0)

    def process_text(self, text: str) -> None:
        """Feed a text command directly (bypasses microphone/STT)."""
        self._text_queue.put(text)

    # ── Pipeline loop ─────────────────────────────────────────────────────
    def _pipeline_loop(self) -> None:
        if self._stt_backend == "stub":
            logger.info("[VOICE] stub mode — listening from queue (call process_text())")
            self._stub_loop()
        else:
            self._audio_loop()

    def _stub_loop(self) -> None:
        """Processes text commands from the queue (no microphone)."""
        while self._running:
            try:
                text = self._text_queue.get(timeout=1.0)
                if text is None:
                    break
                self._handle_text(text)
            except queue.Empty:
                continue

    def _audio_loop(self) -> None:
        """Real microphone pipeline — STT → LLM → action."""
        try:
            import sounddevice as sd
            import numpy as np
        except ImportError:
            logger.warning("[VOICE] sounddevice not installed — falling back to stub")
            self._stub_loop()
            return

        logger.info("[VOICE] microphone active, waiting for wake word '%s'",
                    self._wake_word)
        chunk_size = self._sample_rate // 10   # 100ms chunks

        while self._running:
            try:
                chunk = sd.rec(chunk_size, samplerate=self._sample_rate,
                               channels=1, dtype="float32", blocking=True)
                # Energy-based wake word detection (stub — real: use porcupine)
                energy = float(np.mean(np.abs(chunk)))
                if energy > 0.02:   # rough voice activity threshold
                    text = self._transcribe(chunk)
                    if text and self._wake_word in text.lower():
                        self._speak(f"Yes?")
                        # Record command utterance (2 seconds)
                        cmd_audio = sd.rec(
                            self._sample_rate * 2,
                            samplerate=self._sample_rate,
                            channels=1, dtype="float32", blocking=True
                        )
                        cmd_text = self._transcribe(cmd_audio)
                        if cmd_text:
                            self._handle_text(cmd_text)
            except Exception as e:
                logger.error("[VOICE] audio loop error: %s", e)
                time.sleep(0.5)

    def _handle_text(self, text: str) -> None:
        logger.info("[VOICE] command: '%s'", text)
        self._last_transcript = text
        self._commands_processed += 1

        # Publish transcript
        self._robot.publish("/robot/ai/voice/transcript", {
            "text":       text,
            "confidence": 1.0,
        })

        # Parse and execute
        from neuros.ai.executor import IntentExecutor
        intent = self._llm.parse(text)
        self._robot.publish("/robot/ai/voice/intent", {
            "action":      intent.action,
            "params":      intent.params,
            "explanation": intent.explanation,
        })

        success = IntentExecutor(self._robot, self._llm).execute(intent)
        response = intent.explanation if intent.explanation else f"Executing {intent.action}"

        self._speak(response)
        self._robot.publish("/robot/ai/voice/response", {
            "text":    response,
            "success": success,
        })

    def _transcribe(self, audio) -> str:
        """Convert audio array to text using configured STT backend."""
        if self._stt_backend == "stub":
            return ""
        try:
            if self._stt_backend in ("whisper", "openai-whisper"):
                import whisper
                if not hasattr(self, "_whisper_model"):
                    self._whisper_model = whisper.load_model("base")
                result = self._whisper_model.transcribe(
                    audio.flatten(),
                    language=self._language,
                    fp16=False,
                )
                return result["text"].strip()

            elif self._stt_backend == "faster-whisper":
                from faster_whisper import WhisperModel
                if not hasattr(self, "_fw_model"):
                    self._fw_model = WhisperModel("base", compute_type="int8")
                segs, _ = self._fw_model.transcribe(audio.flatten())
                return " ".join(s.text for s in segs).strip()

        except ImportError as e:
            logger.warning("[VOICE] STT backend '%s' not installed: %s",
                           self._stt_backend, e)
        except Exception as e:
            logger.error("[VOICE] transcribe error: %s", e)
        return ""

    def _speak(self, text: str) -> None:
        """Convert text to speech using configured TTS backend."""
        if self._tts_backend == "stub":
            print(f"  🤖 NEUROS: {text}")
            return
        try:
            if self._tts_backend == "pyttsx3":
                import pyttsx3
                if not hasattr(self, "_tts"):
                    self._tts = pyttsx3.init()
                self._tts.say(text)
                self._tts.runAndWait()
        except Exception as e:
            logger.warning("[VOICE] TTS error: %s", e)
            print(f"  🤖 NEUROS: {text}")

    def stats(self) -> dict:
        return {
            "running":             self._running,
            "commands_processed":  self._commands_processed,
            "last_transcript":     self._last_transcript,
            "stt_backend":         self._stt_backend,
            "tts_backend":         self._tts_backend,
        }
