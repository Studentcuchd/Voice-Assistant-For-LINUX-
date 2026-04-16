"""Speech capture and text fallback helpers."""

from __future__ import annotations

import os
import sys
from contextlib import contextmanager
from typing import Generator, Optional

try:
    import speech_recognition as sr  # type: ignore[import-not-found]
    SPEECH_RECOGNITION_AVAILABLE = True
except ImportError:
    SPEECH_RECOGNITION_AVAILABLE = False

from utils.logger import get_logger

log = get_logger(__name__)


@contextmanager
def _silence_native_stderr() -> Generator[None, None, None]:
    """Temporarily suppress native-library stderr noise from ALSA/PyAudio."""
    try:
        stderr_fd = sys.stderr.fileno()
    except (AttributeError, OSError, ValueError):
        yield
        return

    saved_fd = os.dup(stderr_fd)
    devnull = os.open(os.devnull, os.O_WRONLY)
    try:
        os.dup2(devnull, stderr_fd)
        yield
    finally:
        os.dup2(saved_fd, stderr_fd)
        os.close(saved_fd)
        os.close(devnull)


class SpeechCapture:
    """Capture microphone input and convert it to text."""

    def __init__(
        self,
        energy_threshold: int = 300,
        pause_threshold: float = 0.8,
        phrase_time_limit: int = 10,
        language: str = "en-US",
    ) -> None:
        self.language = language
        self.phrase_time_limit = phrase_time_limit
        self.mic_available = False

        if not SPEECH_RECOGNITION_AVAILABLE:
            log.warning(
                "SpeechRecognition not installed. Voice input disabled. Install SpeechRecognition and pyaudio."
            )
            return

        self._recognizer = sr.Recognizer()
        self._recognizer.energy_threshold = energy_threshold
        self._recognizer.pause_threshold = pause_threshold
        self._recognizer.dynamic_energy_threshold = True

        try:
            with _silence_native_stderr():
                with sr.Microphone() as _:
                    pass
            self.mic_available = True
            log.info("Microphone detected and ready.")
        except (OSError, AttributeError) as exc:
            log.warning("No microphone detected (%s). Falling back to text input.", exc)

    def listen(self) -> Optional[str]:
        if not self.mic_available:
            return None

        log.info("Listening for speech input.")
        try:
            with _silence_native_stderr():
                with sr.Microphone() as source:
                    self._recognizer.adjust_for_ambient_noise(source, duration=0.3)
                    audio = self._recognizer.listen(source, phrase_time_limit=self.phrase_time_limit)

            text = self._recognizer.recognize_google(audio, language=self.language)
            text = text.strip().lower()
            log.info("Recognised: %s", text)
            return text
        except sr.WaitTimeoutError:
            log.warning("No speech detected within timeout.")
        except sr.UnknownValueError:
            log.warning("Could not understand the audio.")
        except sr.RequestError as exc:
            log.error("Google STT request failed: %s", exc)
        except Exception as exc:  # noqa: BLE001
            log.exception("Unexpected error during speech recognition: %s", exc)
        return None

    def calibrate(self, duration: float = 1.5) -> None:
        if not self.mic_available:
            log.warning("Cannot calibrate because microphone is not available.")
            return

        print("Calibrating for ambient noise. Please stay quiet.")
        try:
            with _silence_native_stderr():
                with sr.Microphone() as source:
                    self._recognizer.adjust_for_ambient_noise(source, duration=duration)
            log.info("Calibration complete. Energy threshold: %d", self._recognizer.energy_threshold)
        except Exception as exc:  # noqa: BLE001
            log.error("Calibration failed: %s", exc)


def get_text_input(prompt: str = "You: ") -> Optional[str]:
    try:
        raw = input(prompt)
        text = raw.strip().lower()
        return text if text else None
    except EOFError:
        return None
    except KeyboardInterrupt:
        print()
        return None


def get_input(capture: SpeechCapture, force_text: bool = False) -> Optional[str]:
    if force_text or not capture.mic_available:
        if not force_text:
            print("\nVoice input unavailable. Switching to text mode.\n")
        return get_text_input()
    return capture.listen()
