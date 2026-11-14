"""Entrada/saída de voz local para o chat da ilha, sempre em processo worker."""

import base64
import os
import shutil
import subprocess
import sys
import tempfile
import threading

from PySide6.QtCore import QObject, Signal


MAX_VOICE_TEXT = 2_000
MAX_WAV_BYTES = 8_000_000


def _powershell_command(script):
    """Codifica o script UTF-16LE para evitar problemas de aspas e acentos."""
    encoded = base64.b64encode(script.encode("utf-16le")).decode("ascii")
    return ["powershell.exe", "-NoLogo", "-NoProfile", "-NonInteractive",
            "-EncodedCommand", encoded]


def _powershell_text(text):
    """Escapa texto para uma string literal PowerShell delimitada por aspas simples."""
    return text.replace("'", "''").replace("\r", " ").replace("\n", " ")[:MAX_VOICE_TEXT]


def _no_console_options():
    """Mantém os subprocessos de voz invisíveis no Windows."""
    if sys.platform != "win32":
        return {}
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = 0
    return {
        "creationflags": subprocess.CREATE_NO_WINDOW,
        "startupinfo": startup,
    }


class ChatVoice(QObject):
    """Reconhece voz localmente e fala respostas sem bloquear a interface."""

    transcribed = Signal(str)
    error = Signal(str)
    activity_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._lock = threading.Lock()
        self._busy = False
        self._cancelled = None
        self._process = None
        self._thread = None

    def listen(self, seconds=12):
        """Usa o reconhecedor offline do Windows; não grava nem envia áudio."""
        if sys.platform != "win32":
            self.error.emit("Entrada de voz local está disponível no Windows.")
            return False
        seconds = max(3, min(20, int(seconds)))
        script = (
            "$ErrorActionPreference='Stop'; "
            "[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new(); "
            "try { "
            "Add-Type -AssemblyName System.Speech; "
            "$culture = [System.Globalization.CultureInfo]::GetCultureInfo('pt-BR'); "
            "$r = [System.Speech.Recognition.SpeechRecognitionEngine]::new($culture); "
            "$r.LoadGrammar((New-Object System.Speech.Recognition.DictationGrammar)); "
            "$r.SetInputToDefaultAudioDevice(); "
            f"$x = $r.Recognize([TimeSpan]::FromSeconds({seconds})); "
            "if ($x -and $x.Text) { [Console]::Out.WriteLine($x.Text) } "
            "} catch { [Console]::Error.WriteLine($_.Exception.Message); exit 1 }"
        )
        return self._start("listen", _powershell_command(script), timeout=seconds + 8)

    def speak(self, text):
        """Fala localmente a resposta final do assistente, limitada a texto curto."""
        text = str(text).strip()[:MAX_VOICE_TEXT]
        if not text:
            return False
        if sys.platform == "win32":
            script = (
                "try { "
                "Add-Type -AssemblyName System.Speech; "
                "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                "$s.Speak('" + _powershell_text(text) + "') "
                "} catch { [Console]::Error.WriteLine($_.Exception.Message); exit 1 }"
            )
            command = _powershell_command(script)
        elif sys.platform == "darwin":
            command = ["say", text]
        else:
            command = ["spd-say", text]
        return self._start("speak", command, timeout=30)

    def play_wav(self, data):
        """Reproduz bytes WAV do TTS do LLM; o arquivo temporário é removido ao final."""
        try:
            raw = bytes(data)
        except (TypeError, ValueError):
            raw = b""
        if (
            len(raw) < 44
            or len(raw) > MAX_WAV_BYTES
            or not raw.startswith(b"RIFF")
            or raw[8:12] != b"WAVE"
        ):
            self.error.emit("Áudio WAV recebido do modelo local é inválido.")
            return False
        try:
            handle = tempfile.NamedTemporaryFile(
                prefix="pestinha-voz-", suffix=".wav", delete=False
            )
            with handle:
                handle.write(raw)
        except OSError as error:
            self.error.emit(f"Não foi possível preparar o áudio local: {error}")
            return False
        path = handle.name
        if sys.platform == "win32":
            script = (
                "try { (New-Object System.Media.SoundPlayer '"
                + _powershell_text(path)
                + "').PlaySync() } catch { "
                "[Console]::Error.WriteLine($_.Exception.Message); exit 1 }"
            )
            command = _powershell_command(script)
        elif sys.platform == "darwin":
            command = ["afplay", path]
        else:
            player = shutil.which("paplay") or shutil.which("aplay")
            if not player:
                try:
                    os.unlink(path)
                except OSError:
                    pass
                self.error.emit("Reprodução de áudio indisponível nesta plataforma.")
                return False
            command = [player, path]
        # WAV de ~16 kHz/16 bits ocupa ~32 KB/s; margem generosa para codecs lentos.
        timeout = max(15, len(raw) // 8000 + 10)
        return self._start("speak", command, timeout=timeout, cleanup=path)

    def _start(self, operation, command, timeout, cleanup=None):
        with self._lock:
            if self._busy:
                busy = True
            else:
                busy = False
                self._busy = True
                self._cancelled = threading.Event()
                cancelled = self._cancelled
                thread = threading.Thread(
                    target=self._run,
                    args=(operation, command, timeout, cancelled, cleanup),
                    name=f"pestinha-voice-{operation}",
                    daemon=True,
                )
                self._thread = thread
        if busy:
            self.error.emit("A operação de voz anterior ainda está ativa.")
            return False
        self.activity_changed.emit("ouvindo" if operation == "listen" else "falando")
        try:
            thread.start()
        except RuntimeError as error:
            with self._lock:
                self._busy = False
                self._thread = None
            if cleanup:
                try:
                    os.unlink(cleanup)
                except OSError:
                    pass
            self.activity_changed.emit("parada")
            self.error.emit(f"Não foi possível iniciar a voz local: {error}")
            return False
        return True

    def _run(self, operation, command, timeout, cancelled, cleanup=None):
        process = None
        try:
            if cancelled.is_set():
                return
            process = subprocess.Popen(
                command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                **_no_console_options(),
            )
            with self._lock:
                self._process = process
                if cancelled.is_set():
                    process.terminate()
            try:
                stdout, stderr = process.communicate(timeout=timeout)
            except subprocess.TimeoutExpired:
                process.kill()
                stdout, stderr = process.communicate()
                raise TimeoutError("O reconhecimento/síntese de voz excedeu o tempo limite.")
            if cancelled.is_set():
                return
            if process.returncode:
                detail = (stderr or "").strip().replace("\r", " ").replace("\n", " ")
                # PowerShell serializa registros de erro como CLIXML no stderr
                # redirecionado; esse ruído não ajuda o usuário, então vira genérico.
                if "#< CLIXML" in detail or "<Objs" in detail:
                    detail = ""
                raise RuntimeError(detail[:220] or "O mecanismo local de voz falhou.")
            if operation == "listen":
                text = (stdout or "").strip()[:MAX_VOICE_TEXT]
                if text:
                    self.transcribed.emit(text)
                else:
                    self.error.emit("Não reconheci fala. Tente novamente.")
        except Exception as error:
            if not cancelled.is_set():
                message = str(error).strip() or type(error).__name__
                self.error.emit(f"Voz local indisponível: {message[:220]}")
        finally:
            with self._lock:
                if self._process is process:
                    self._process = None
                self._busy = False
                self._thread = None
            if cleanup:
                try:
                    os.unlink(cleanup)
                except OSError:
                    pass
            self.activity_changed.emit("parada")

    def cancel(self):
        """Interrompe um subprocesso de voz ativo ao cancelar ou encerrar o app."""
        with self._lock:
            cancelled = self._cancelled
            process = self._process
        if cancelled is not None:
            cancelled.set()
        if process is not None:
            try:
                process.terminate()
            except OSError:
                pass

    def shutdown(self, timeout=1.0):
        """Cancela o processo e aguarda a thread por um prazo curto."""
        self.cancel()
        with self._lock:
            thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(max(0.0, float(timeout)))
