"""Testes de voz local do chat sem usar microfone ou síntese real."""

import base64
import threading

from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication

from pestinha.mind import chat_voice


class _FakeProcess:
    returncode = 0

    def __init__(self, output="", stderr=""):
        self.output = output
        self.stderr = stderr
        self.terminated = False

    def communicate(self, timeout=None):
        return self.output, self.stderr

    def terminate(self):
        self.terminated = True

    def kill(self):
        self.terminated = True


def test_microfone_usa_reconhecimento_local_e_thread_worker(monkeypatch):
    app_qt = QApplication.instance() or QApplication([])
    app_qt.setQuitOnLastWindowClosed(False)
    monkeypatch.setattr(chat_voice.sys, "platform", "win32")
    monkeypatch.setattr(chat_voice, "_no_console_options", lambda: {"creationflags": 0x08000000})
    observed = {}

    def popen(command, **kwargs):
        observed["command"] = command
        observed["kwargs"] = kwargs
        observed["thread"] = threading.get_ident()
        return _FakeProcess("pergunta reconhecida\n")

    monkeypatch.setattr(chat_voice.subprocess, "Popen", popen)
    service = chat_voice.ChatVoice()
    received = []
    loop = QEventLoop()
    timeout = QTimer()
    timeout.setSingleShot(True)
    timeout.timeout.connect(loop.quit)
    service.transcribed.connect(lambda text: (received.append(text), loop.quit()))
    main_thread = threading.get_ident()
    assert service.listen()
    timeout.start(2500)
    loop.exec()
    decoded = base64.b64decode(observed["command"][-1]).decode("utf-16le")
    assert "SpeechRecognitionEngine" in decoded
    assert "DictationGrammar" in decoded
    assert "pt-BR" in decoded
    assert observed["kwargs"]["creationflags"] == 0x08000000
    assert observed["thread"] != main_thread
    assert received == ["pergunta reconhecida"]
    service.shutdown()


def test_resposta_falada_escapa_aspas_e_eh_local(monkeypatch):
    app_qt = QApplication.instance() or QApplication([])
    app_qt.setQuitOnLastWindowClosed(False)
    monkeypatch.setattr(chat_voice.sys, "platform", "win32")
    monkeypatch.setattr(chat_voice, "_no_console_options", lambda: {})
    observed = {}

    def popen(command, **_kwargs):
        observed["command"] = command
        return _FakeProcess()

    monkeypatch.setattr(chat_voice.subprocess, "Popen", popen)
    service = chat_voice.ChatVoice()
    loop = QEventLoop()
    timeout = QTimer()
    timeout.setSingleShot(True)
    timeout.timeout.connect(loop.quit)
    service.activity_changed.connect(lambda state: loop.quit() if state == "parada" else None)
    assert service.speak("resposta d'água")
    timeout.start(2500)
    loop.exec()
    script = base64.b64decode(observed["command"][-1]).decode("utf-16le")
    assert "Speak('resposta d''água')" in script
    assert "http://" not in script
    service.shutdown()


def test_play_wav_toca_audio_do_llm_e_remove_temporario(monkeypatch):
    import os
    app_qt = QApplication.instance() or QApplication([])
    app_qt.setQuitOnLastWindowClosed(False)
    monkeypatch.setattr(chat_voice.sys, "platform", "win32")
    monkeypatch.setattr(chat_voice, "_no_console_options", lambda: {"creationflags": 0x08000000})
    observed = {}
    wav = b"RIFF" + b"\x24\x00\x00\x00" + b"WAVE" + b"\x00" * 200

    def popen(command, **kwargs):
        observed["command"] = command
        observed["kwargs"] = kwargs
        return _FakeProcess()

    monkeypatch.setattr(chat_voice.subprocess, "Popen", popen)
    service = chat_voice.ChatVoice()
    loop = QEventLoop()
    timeout = QTimer()
    timeout.setSingleShot(True)
    timeout.timeout.connect(loop.quit)
    service.activity_changed.connect(lambda state: loop.quit() if state == "parada" else None)
    assert service.play_wav(wav)
    timeout.start(2500)
    loop.exec()
    script = base64.b64decode(observed["command"][-1]).decode("utf-16le")
    assert "SoundPlayer" in script and "PlaySync" in script
    assert observed["kwargs"]["creationflags"] == 0x08000000
    temp_path = script.split("'")[1]
    assert temp_path.endswith(".wav")
    assert not os.path.exists(temp_path)
    service.shutdown()


def test_play_wav_rejeita_audio_invalido_sem_abrir_processo(monkeypatch):
    monkeypatch.setattr(chat_voice.sys, "platform", "win32")
    called = []
    monkeypatch.setattr(
        chat_voice.subprocess, "Popen", lambda *a, **k: called.append(True)
    )
    service = chat_voice.ChatVoice()
    errors = []
    service.error.connect(errors.append)
    assert not service.play_wav(b"nao e riff")
    assert errors and "WAV" in errors[0]
    assert called == []


def test_erro_clixml_do_powershell_vira_mensagem_amigavel(monkeypatch):
    monkeypatch.setattr(chat_voice.sys, "platform", "win32")
    monkeypatch.setattr(chat_voice, "_no_console_options", lambda: {})

    class FailingProcess(_FakeProcess):
        returncode = 1

    monkeypatch.setattr(
        chat_voice.subprocess, "Popen",
        lambda *a, **k: FailingProcess(
            stderr="#< CLIXML\n<Objs Version=\"1.1.0.1\"><Obj S=\"progress\"/>"
        ),
    )
    service = chat_voice.ChatVoice()
    errors = []
    loop = QEventLoop()
    timeout = QTimer()
    timeout.setSingleShot(True)
    timeout.timeout.connect(loop.quit)
    service.error.connect(lambda msg: (errors.append(msg), loop.quit()))
    service.speak("teste")
    timeout.start(2500)
    loop.exec()
    assert errors and "CLIXML" not in errors[0] and "Objs" not in errors[0]
    assert "mecanismo local de voz" in errors[0]
    service.shutdown()


def test_entrada_de_voz_explicita_em_plataforma_sem_sapi(monkeypatch):
    monkeypatch.setattr(chat_voice.sys, "platform", "linux")
    service = chat_voice.ChatVoice()
    errors = []
    service.error.connect(errors.append)
    assert not service.listen()
    assert errors and "disponível no Windows" in errors[0]
