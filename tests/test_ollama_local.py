"""Cliente Ollama local: listagem, streaming incremental e execução fora da UI."""
import json
import threading
import time

from PySide6.QtCore import QEventLoop, QTimer
from PySide6.QtWidgets import QApplication

import requests
from pestinha.mind.ollama_local import (
    OLLAMA_HOST, STREAM_READ_TIMEOUT_S, OllamaLocal, _OllamaTask, normalize_models,
)


def _mock_session(monkeypatch, get=None, post=None):
    """Fornece Session falsa para testes sem sockets e sem proxy do ambiente."""
    sessions = []

    class FakeSession:
        def __init__(self):
            self.trust_env = True
            sessions.append(self)

        def get(self, *args, **kwargs):
            return get(*args, **kwargs)

        def post(self, *args, **kwargs):
            return post(*args, **kwargs)

        def close(self):
            pass

    monkeypatch.setattr(requests, "Session", FakeSession)
    return sessions


def _workers_ended(service, timeout=3):
    """Aguarda worker daemon sem depender do loop de sinais de limpeza da UI."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with service._tasks_lock:
            tasks = tuple(service._tasks)
        if all(task.thread is None or not task.thread.is_alive() for task in tasks):
            return True
        time.sleep(0.01)
    return False


def test_normaliza_modelos_e_filtra_modelos_de_embedding():
    response = {
        "data": [
            {"id": "qwen2.5:latest"},
            {"id": "llama3.2:latest"},
            {"id": "nomic-embed-text"},
            {"id": "bge-m3"},
            {"id": "clip-vision"},
        ]
    }
    assert normalize_models(response) == ["llama3.2:latest", "qwen2.5:latest"]
    assert normalize_models({"data": None}) == []
    assert normalize_models({"data": [{"id": None}, 42]}) == []
    assert normalize_models({"models": [{"name": "phi3:mini"}]}) == ["phi3:mini"]


def test_listagem_usa_v1_models_no_host_loopback_sem_proxy(monkeypatch):
    seen = {}

    class FakeResponse:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return {"data": [{"id": "mistral:latest"}]}

        def close(self):
            pass

    def fake_get(url, headers, timeout, allow_redirects):
        seen.update(url=url, headers=headers, timeout=timeout, allow_redirects=allow_redirects)
        return FakeResponse()

    sessions = _mock_session(monkeypatch, get=fake_get)
    task = _OllamaTask("list")
    received = []
    task.signals.models.connect(received.append)
    task.run()
    assert seen["url"] == f"{OLLAMA_HOST}/v1/models"
    assert seen["headers"] == {}
    assert seen["timeout"] == (2, 5)
    assert seen["allow_redirects"] is False
    assert sessions[0].trust_env is False
    assert received == [["mistral:latest"]]


def test_chave_bearer_so_e_enviada_quando_configurada(monkeypatch):
    monkeypatch.setenv("OLLAMA_API_KEY", "local-secret")
    seen = {}

    class FakeResponse:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return {"data": [{"id": "llama3.2"}]}

        def close(self):
            pass

    def fake_get(url, headers, **_kwargs):
        seen.update(url=url, headers=headers)
        return FakeResponse()

    _mock_session(monkeypatch, get=fake_get)
    task = _OllamaTask("list")
    task.run()
    assert seen["url"] == f"{OLLAMA_HOST}/v1/models"
    assert seen["headers"] == {"Authorization": "Bearer local-secret"}


def test_stream_emite_conteudo_por_fragmentos(monkeypatch):
    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def raise_for_status(self):
            pass

        def iter_lines(self, decode_unicode):
            assert decode_unicode
            return iter([
                '{"message":{"content":"resposta "}}',
                '{"message":{"content":"local"}}',
            ])

    def fake_post(url, json, stream, timeout, headers, allow_redirects):
        assert url == f"{OLLAMA_HOST}/api/chat"
        assert json["stream"] is True
        assert json["model"] == "qwen2.5:latest"
        assert stream is True
        assert timeout == (2, STREAM_READ_TIMEOUT_S)
        assert headers == {}
        assert allow_redirects is False
        return FakeResponse()

    _mock_session(monkeypatch, post=fake_post)
    task = _OllamaTask(
        "chat", model="qwen2.5:latest",
        messages=[{"role": "user", "content": "oi"}],
    )
    tokens, completed = [], []
    task.signals.token.connect(tokens.append)
    task.signals.chat_finished.connect(lambda: completed.append(True))
    task.run()
    assert tokens == ["resposta local"]
    assert completed == [True]


def test_servidor_indisponivel_emite_aviso_discreto(monkeypatch):
    def failing_get(*_args, **_kwargs):
        raise requests.ConnectionError("connection refused")

    _mock_session(
        monkeypatch,
        get=failing_get,
    )
    task = _OllamaTask("list")
    errors = []
    task.signals.error.connect(errors.append)
    task.run()
    assert errors == ["Ollama desconectado. Inicie o serviço local."]


def test_redirecionamento_do_loopback_e_recusado(monkeypatch):
    class FakeResponse:
        status_code = 307

        def close(self):
            pass

    _mock_session(monkeypatch, get=lambda *_args, **_kwargs: FakeResponse())
    task = _OllamaTask("list")
    errors = []
    task.signals.error.connect(errors.append)
    task.run()
    assert errors and "Redirecionamento recusado" in errors[0]


def test_stream_corrompido_preserva_fragmento_e_emite_erro(monkeypatch):
    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def raise_for_status(self):
            pass

        def iter_lines(self, decode_unicode):
            return iter(['{"message":{"content":"parte"}}', "{corrompido"])

    _mock_session(
        monkeypatch, post=lambda *_args, **_kwargs: FakeResponse()
    )
    task = _OllamaTask("chat", model="llama3.2", messages=[])
    tokens, errors, finished = [], [], []
    task.signals.token.connect(tokens.append)
    task.signals.error.connect(errors.append)
    task.signals.chat_finished.connect(lambda: finished.append(True))
    task.run()
    assert tokens == ["parte"]
    assert errors and errors[0].startswith("Falha no Ollama local:")
    assert finished == [True]


def test_fragmento_longo_e_limitado_para_proteger_memoria(monkeypatch):
    from pestinha.mind.ollama_local import MAX_RESPONSE_CHARS

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def raise_for_status(self):
            pass

        def iter_lines(self, decode_unicode):
            return iter([json.dumps({"message": {"content": "x" * (MAX_RESPONSE_CHARS + 50)}})])

    _mock_session(
        monkeypatch, post=lambda *_args, **_kwargs: FakeResponse()
    )
    task = _OllamaTask("chat", model="llama3.2", messages=[])
    tokens, limited = [], []
    task.signals.token.connect(tokens.append)
    task.signals.limited.connect(lambda: limited.append(True))
    task.run()
    assert sum(map(len, tokens)) == MAX_RESPONSE_CHARS
    assert limited == [True]


def test_listagem_assincrona_roda_em_thread_secundaria(monkeypatch):
    app = QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(False)
    main_thread = threading.get_ident()
    called_from = []

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def raise_for_status(self):
            pass

        def json(self):
            called_from.append(threading.get_ident())
            return {"models": [{"name": "llama3.2"}]}

        def close(self):
            pass

    _mock_session(
        monkeypatch, get=lambda *_args, **_kwargs: FakeResponse()
    )
    service = OllamaLocal()
    loop = QEventLoop()
    timer = QTimer()
    timer.setSingleShot(True)
    timer.timeout.connect(loop.quit)
    service.models_ready.connect(lambda _models: loop.quit())
    service.list_models_async()
    timer.start(3000)
    loop.exec()
    assert called_from and called_from[0] != main_thread
    assert _workers_ended(service)


def test_stream_assincrono_roda_em_thread_secundaria(monkeypatch):
    app = QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(False)
    main_thread = threading.get_ident()
    called_from = []

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def raise_for_status(self):
            pass

        def iter_lines(self, decode_unicode):
            called_from.append(threading.get_ident())
            return iter(['{"message":{"content":"ok"}}'])

    _mock_session(
        monkeypatch, post=lambda *_args, **_kwargs: FakeResponse()
    )
    service = OllamaLocal()
    loop = QEventLoop()
    timer = QTimer()
    timer.setSingleShot(True)
    timer.timeout.connect(loop.quit)
    service.chat_finished.connect(loop.quit)
    service.chat_stream_async("llama3.2", [{"role": "user", "content": "oi"}])
    timer.start(3000)
    loop.exec()
    assert called_from and called_from[0] != main_thread
    assert _workers_ended(service)


def test_speech_retorn_wav_do_endpoint_de_voz_do_llm(monkeypatch):
    seen = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def raise_for_status(self):
            pass

        def iter_content(self, chunk_size):
            assert chunk_size > 0
            return iter([b"RIFF", b"\x24\x00\x00\x00", b"WAVE", b"audio"])

    def fake_post(url, json, **kwargs):
        seen.update(url=url, json=json, kwargs=kwargs)
        return FakeResponse()

    _mock_session(monkeypatch, post=fake_post)
    task = _OllamaTask("speech", model="tts-local", speech_text="olá")
    audio = []
    task.signals.speech_audio.connect(audio.append)
    task.run()
    assert seen["url"] == f"{OLLAMA_HOST}/v1/audio/speech"
    assert seen["json"] == {
        "model": "tts-local", "input": "olá", "response_format": "wav",
    }
    assert seen["kwargs"]["allow_redirects"] is False
    assert b"".join(audio) == b"RIFF\x24\x00\x00\x00WAVEaudio"


def test_speech_rejeita_audio_que_nao_e_wav(monkeypatch):
    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def raise_for_status(self):
            pass

        def iter_content(self, chunk_size):
            return iter([b"isto nao e wav"])

    _mock_session(monkeypatch, post=lambda *_a, **_k: FakeResponse())
    task = _OllamaTask("speech", model="tts-local", speech_text="olá")
    audio, errors = [], []
    task.signals.speech_audio.connect(audio.append)
    task.signals.error.connect(errors.append)
    task.run()
    assert audio == []
    assert errors and "WAV" in errors[0]


def test_cancelamento_fecha_resposta_e_libera_worker(monkeypatch):
    app = QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(False)
    entered = threading.Event()
    closed = threading.Event()

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def raise_for_status(self):
            pass

        def close(self):
            closed.set()

        def iter_lines(self, decode_unicode):
            def lines():
                entered.set()
                closed.wait(2)
                if False:
                    yield ""
            return lines()

    _mock_session(
        monkeypatch, post=lambda *_args, **_kwargs: FakeResponse()
    )
    service = OllamaLocal()
    loop = QEventLoop()
    service.chat_finished.connect(loop.quit)
    service.chat_stream_async("llama3.2", [{"role": "user", "content": "oi"}])
    assert entered.wait(2)
    service.cancel_chat()
    QTimer.singleShot(2000, loop.quit)
    loop.exec()
    assert closed.is_set()
    assert _workers_ended(service)
