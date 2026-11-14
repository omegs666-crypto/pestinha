"""Cliente Ollama loopback com listagem e streaming executados fora da UI Qt."""

import json
import os
import threading
import time

import requests
from PySide6.QtCore import QObject, Signal


OLLAMA_HOST = "http://127.0.0.1:11434"
MAX_RESPONSE_CHARS = 16_000
MAX_MESSAGES = 22
MAX_MESSAGE_CHARS = 24_000
STREAM_CHUNK_CHARS = 32
STREAM_FLUSH_S = 0.04
STREAM_READ_TIMEOUT_S = 30
MAX_SPEECH_TEXT = 4_000
MAX_SPEECH_BYTES = 8_000_000
SPEECH_TIMEOUT_S = 60


def normalize_models(response):
    """Lê /v1/models e aceita /api/tags para servidores Ollama antigos."""
    if not isinstance(response, dict):
        return []
    models = response.get("data")
    if not isinstance(models, list):
        models = response.get("models", [])
    if not isinstance(models, list):
        return []
    names = []
    for model in models:
        name = (
            model.get("id") or model.get("name") or model.get("model")
            if isinstance(model, dict) else None
        )
        if not isinstance(name, str) or not name.strip():
            continue
        name = name.strip()[:200]
        folded = name.casefold()
        if any(fragment in folded for fragment in (
            "nomic-embed", "bge-", "clip", "rerank", "mxbai-embed",
            "snowflake-arctic-embed", "embeddinggemma",
        )):
            continue
        if name not in names:
            names.append(name)
        if len(names) >= 256:
            break
    return sorted(names, key=str.casefold)


def normalize_messages(messages):
    """Filtra roles e limita texto/histórico antes de construir o pedido HTTP."""
    if not isinstance(messages, (list, tuple)):
        return []
    clean = []
    for message in messages[-MAX_MESSAGES:]:
        if not isinstance(message, dict):
            continue
        role = message.get("role")
        content = message.get("content")
        if role not in {"system", "user", "assistant"} or not isinstance(content, str):
            continue
        clean.append({"role": role, "content": content[:MAX_MESSAGE_CHARS]})
    return clean


def _reject_redirect(response):
    """Recusa redirecionamentos que poderiam enviar o chat a outro servidor."""
    try:
        status = int(getattr(response, "status_code", 200))
    except (TypeError, ValueError, OverflowError):
        status = 200
    if 300 <= status < 400:
        raise requests.RequestException("Redirecionamento recusado no serviço local.")


def _auth_headers():
    """Lê chave opcional sem persistir nem exibir o valor; só envia ao loopback fixo."""
    key = os.environ.get("OLLAMA_API_KEY", "").strip()
    return {"Authorization": f"Bearer {key}"} if key else {}


def _error_message(error):
    """Converte falhas de conexão em uma mensagem segura e compreensível."""
    text = str(error).lower()
    if isinstance(error, requests.ReadTimeout):
        return "Ollama demorou a responder. Tente novamente."
    if isinstance(error, (
        requests.ConnectionError, requests.ConnectTimeout, ConnectionError, TimeoutError,
    )) or any(part in text for part in (
        "connection refused", "failed to connect", "connection error",
        "actively refused", "winerror 10061", "errno 111",
        "all connection attempts failed", "connecterror",
    )):
        return "Ollama desconectado. Inicie o serviço local."
    return f"Falha no Ollama local: {str(error)[:240]}"


class _TaskSignals(QObject):
    models = Signal(object)
    token = Signal(str)
    chat_finished = Signal()
    limited = Signal()
    error = Signal(str)
    speech_audio = Signal(bytes)
    retired = Signal(object)


class _OllamaTask:
    """Uma chamada Ollama isolada numa thread daemon limitada pelo serviço."""

    def __init__(self, operation, *, model=None, messages=None, speech_text=None):
        super().__init__()
        self.operation = operation
        self.model = model
        self.messages = normalize_messages(messages)
        self.speech_text = (
            str(speech_text).strip()[:MAX_SPEECH_TEXT]
            if speech_text is not None else ""
        )
        self.signals = _TaskSignals()
        self._cancelled = threading.Event()
        self._response_lock = threading.Lock()
        self._response = None
        self.thread = None
        self.thread_ident = None

    def cancel(self):
        """Pede cancelamento e fecha o stream ativo para liberar o worker."""
        self._cancelled.set()
        with self._response_lock:
            response = self._response
        if response is not None:
            try:
                response.close()
            except Exception:
                pass

    def _set_response(self, response):
        with self._response_lock:
            self._response = response

    def _host(self):
        return OLLAMA_HOST.rstrip("/")

    def run(self):
        self.thread_ident = threading.get_ident()
        buffered = []
        session = None
        try:
            if self._cancelled.is_set():
                return
            host = self._host()
            session = requests.Session()
            session.trust_env = False  # evita proxy do ambiente: só aceita o loopback configurado
            if self.operation == "list":
                if self._cancelled.is_set():
                    return
                response = session.get(
                    f"{host}/v1/models", headers=_auth_headers(), timeout=(2, 5),
                    allow_redirects=False,
                )
                try:
                    _reject_redirect(response)
                    response.raise_for_status()
                    models = normalize_models(response.json())
                finally:
                    response.close()
                if not self._cancelled.is_set():
                    self.signals.models.emit(models)
                return

            if self.operation == "speech":
                # TTS do próprio LLM: endpoint OpenAI-compatible /v1/audio/speech.
                if not self.speech_text:
                    raise ValueError("Texto de voz vazio.")
                if self._cancelled.is_set():
                    return
                payload = {
                    "model": self.model,
                    "input": self.speech_text,
                    "response_format": "wav",
                }
                chunks = []
                total = 0
                with session.post(
                    f"{host}/v1/audio/speech",
                    json=payload,
                    stream=True,
                    timeout=(2, SPEECH_TIMEOUT_S),
                    headers=_auth_headers(),
                    allow_redirects=False,
                ) as response:
                    self._set_response(response)
                    _reject_redirect(response)
                    response.raise_for_status()
                    for chunk in response.iter_content(65_536):
                        if self._cancelled.is_set():
                            break
                        if not chunk:
                            continue
                        total += len(chunk)
                        if total > MAX_SPEECH_BYTES:
                            raise RuntimeError(
                                "A resposta de áudio excedeu o limite local."
                            )
                        chunks.append(chunk)
                audio = b"".join(chunks)
                if self._cancelled.is_set():
                    return
                if not audio.startswith(b"RIFF") or audio[8:12] != b"WAVE":
                    raise RuntimeError(
                        "O serviço local não retornou áudio WAV válido."
                    )
                self.signals.speech_audio.emit(audio)
                return

            payload = {
                "model": self.model,
                "messages": self.messages,
                "stream": True,
            }
            if self._cancelled.is_set():
                return
            accumulated_chars = 0
            buffered_chars = 0
            last_emit = time.monotonic()
            with session.post(
                f"{host}/api/chat",
                json=payload,
                stream=True,
                timeout=(2, STREAM_READ_TIMEOUT_S),
                headers=_auth_headers(),
                allow_redirects=False,
            ) as response:
                self._set_response(response)
                _reject_redirect(response)
                response.raise_for_status()
                for line in response.iter_lines(decode_unicode=True):
                    if self._cancelled.is_set():
                        break
                    if not line:
                        continue
                    chunk = json.loads(line)
                    if not isinstance(chunk, dict):
                        continue
                    message = chunk.get("message")
                    token = message.get("content", "") if isinstance(message, dict) else ""
                    if not isinstance(token, str):
                        continue
                    remaining = MAX_RESPONSE_CHARS - accumulated_chars
                    if remaining <= 0:
                        self.signals.limited.emit()
                        break
                    token = token[:remaining]
                    if token:
                        buffered.append(token)
                        accumulated_chars += len(token)
                        buffered_chars += len(token)
                    if (buffered_chars >= STREAM_CHUNK_CHARS
                            or time.monotonic() - last_emit >= STREAM_FLUSH_S):
                        self.signals.token.emit("".join(buffered))
                        buffered.clear()
                        buffered_chars = 0
                        last_emit = time.monotonic()
                    if accumulated_chars >= MAX_RESPONSE_CHARS:
                        self.signals.limited.emit()
                        break
                if buffered and not self._cancelled.is_set():
                    self.signals.token.emit("".join(buffered))
            self._set_response(None)
            self.signals.chat_finished.emit()
        except Exception as error:  # conexão local, versão do servidor ou cliente ausente
            if not self._cancelled.is_set():
                if buffered:
                    self.signals.token.emit("".join(buffered))
                self.signals.error.emit(_error_message(error))
            if self.operation == "chat":
                self.signals.chat_finished.emit()
        finally:
            self._set_response(None)
            if session is not None:
                try:
                    session.close()
                except Exception:
                    pass
            self.signals.retired.emit(self)


class OllamaLocal(QObject):
    """Facade assíncrona local-only para listar modelos e transmitir respostas."""

    models_ready = Signal(object)
    token = Signal(str)
    chat_finished = Signal()
    error = Signal(str)
    response_limited = Signal()
    speech_ready = Signal(bytes)
    speech_failed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tasks = set()
        self._tasks_lock = threading.Lock()
        self._max_tasks = 2

    def list_models_async(self):
        """Consulta ollama.list() num worker; o loop de eventos da interface não espera."""
        task = _OllamaTask("list")
        task.signals.models.connect(self.models_ready)
        task.signals.error.connect(self.error)
        self._submit(task)

    def chat_stream_async(self, model, messages):
        """Envia histórico local e transmite cada fragmento de resposta por sinais Qt."""
        if not isinstance(model, str) or not model.strip():
            self.error.emit("Escolha um modelo Ollama instalado.")
            self.chat_finished.emit()
            return
        safe_messages = normalize_messages(messages)
        if not safe_messages:
            self.error.emit("A conversa está vazia ou contém mensagens inválidas.")
            self.chat_finished.emit()
            return
        task = _OllamaTask("chat", model=model.strip()[:200], messages=safe_messages)
        task.signals.token.connect(self.token)
        task.signals.chat_finished.connect(self.chat_finished)
        task.signals.limited.connect(self.response_limited)
        task.signals.error.connect(self.error)
        self._submit(task)

    def speak_async(self, model, text):
        """Pede áudio WAV ao /v1/audio/speech do Ollama; o resultado chega por sinal."""
        if not isinstance(model, str) or not model.strip():
            self.speech_failed.emit("Nenhum modelo de voz local selecionado.")
            return
        clean = str(text or "").strip()[:MAX_SPEECH_TEXT]
        if not clean:
            return
        task = _OllamaTask(
            "speech", model=model.strip()[:200], speech_text=clean
        )
        task.signals.speech_audio.connect(self.speech_ready)
        task.signals.error.connect(self.speech_failed)
        self._submit(task)

    def _submit(self, task):
        task.signals.retired.connect(self._retirar)
        with self._tasks_lock:
            if len(self._tasks) >= self._max_tasks:
                task.signals.error.emit(
                    "Ollama já está processando outra solicitação local."
                )
                if task.operation == "chat":
                    self.chat_finished.emit()
                return
            self._tasks.add(task)
            thread = threading.Thread(
                target=task.run,
                name=f"pestinha-ollama-{task.operation}",
                daemon=True,
            )
            task.thread = thread
        thread.start()

    def _retirar(self, task):
        with self._tasks_lock:
            self._tasks.discard(task)

    def cancel_chat(self):
        """Cancela streams de chat ativos sem bloquear a thread da interface."""
        with self._tasks_lock:
            tasks = tuple(self._tasks)
        for task in tasks:
            if task.operation == "chat":
                task.cancel()

    def shutdown(self, timeout_ms=750):
        """Cancela pedidos ativos e aguarda um prazo curto durante o encerramento."""
        with self._tasks_lock:
            tasks = tuple(self._tasks)
        for task in tasks:
            task.cancel()
        deadline = time.monotonic() + max(0, int(timeout_ms)) / 1000.0
        for task in tasks:
            thread = task.thread
            if thread is not None and thread.is_alive():
                thread.join(max(0.0, deadline - time.monotonic()))
        with self._tasks_lock:
            self._tasks = {task for task in self._tasks
                           if task.thread is not None and task.thread.is_alive()}
