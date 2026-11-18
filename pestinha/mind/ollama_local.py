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
SPEECH_TIMEOUT_S = 180            # por frase: modelos omni pequenos podem demorar
MAX_FRASES = 12


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


# ---------------- voz do LLM (como o Coucou faz com o lfm3-omni) ----------------

_CAPACIDADES = {}


def capacidades(session, host, modelo):
    """O que o modelo sabe fazer (`/api/show` → capabilities); vazio se o servidor não informar."""
    if modelo in _CAPACIDADES:
        return _CAPACIDADES[modelo]
    caps = set()
    try:
        resposta = session.post(f"{host}/api/show", json={"model": modelo}, timeout=(2, 10),
                                headers=_auth_headers(), allow_redirects=False)
        try:
            _reject_redirect(resposta)
            resposta.raise_for_status()
            lista = resposta.json().get("capabilities")
            caps = {str(c) for c in lista} if isinstance(lista, list) else set()
        finally:
            resposta.close()
    except Exception:
        caps = set()
    if caps:
        _CAPACIDADES[modelo] = caps
    return caps


def speech_chunks(texto):
    """Texto quebrado em frases (. ! ? quebra de linha): uma voz omni pequena muda de timbre no meio
    de um texto longo; uma requisição por frase mantém a voz igual. No máximo MAX_FRASES pedaços."""
    pedacos, inicio = [], 0
    for fim, letra in enumerate(texto):
        if letra in ".!?\n":
            pedaco = texto[inicio:fim + 1].strip()
            if pedaco:
                pedacos.append(pedaco)
            inicio = fim + 1
    resto = texto[inicio:].strip()
    if resto:
        pedacos.append(resto)
    if len(pedacos) > MAX_FRASES:
        pedacos = pedacos[:MAX_FRASES - 1] + [" ".join(pedacos[MAX_FRASES - 1:])]
    return pedacos


def _inicio_dos_dados(wav):
    pos = 12
    while pos + 8 <= len(wav):
        if wav[pos:pos + 4] == b"data":
            return pos
        tamanho = int.from_bytes(wav[pos + 4:pos + 8], "little")
        if tamanho > len(wav):
            return None
        pos += 8 + tamanho + (tamanho & 1)
    return None


def fix_wav_header(wav):
    """O Ollama manda o WAV em streaming com tamanhos 0xFFFFFFFF; com o arquivo inteiro, corrige-os."""
    wav = bytearray(wav)
    if len(wav) < 12 or wav[0:4] != b"RIFF" or wav[8:12] != b"WAVE":
        return bytes(wav)
    wav[4:8] = (len(wav) - 8).to_bytes(4, "little")
    dados = _inicio_dos_dados(wav)
    if dados is not None:
        wav[dados + 4:dados + 8] = (len(wav) - dados - 8).to_bytes(4, "little")
    return bytes(wav)


def concat_wavs(partes):
    """Vários WAVs de uma frase cada → um só: os dados em sequência sob o cabeçalho do primeiro."""
    if not partes:
        return b""
    cabeca = _inicio_dos_dados(partes[0])
    if cabeca is None or len(partes) == 1:
        return bytes(partes[0])
    out = bytearray(partes[0][:cabeca + 8])
    for wav in partes:
        dados = _inicio_dos_dados(wav)
        if dados is not None:
            out += wav[dados + 8:]
    out[4:8] = (len(out) - 8).to_bytes(4, "little")
    out[cabeca + 4:cabeca + 8] = (len(out) - cabeca - 8).to_bytes(4, "little")
    return bytes(out)


class _TaskSignals(QObject):
    models = Signal(object)
    token = Signal(str)
    chat_finished = Signal()
    limited = Signal()
    error = Signal(str)
    speech_audio = Signal(bytes)
    progress = Signal(object)       # pull: {"status": str, "pct": int|None}
    pull_done = Signal()
    retired = Signal(object)


class _OllamaTask:
    """Uma chamada Ollama isolada numa thread daemon limitada pelo serviço."""

    def __init__(self, operation, *, model=None, messages=None, speech_text=None, voice_candidates=()):
        super().__init__()
        self.operation = operation
        self.model = model
        self.voice_candidates = tuple(m for m in voice_candidates if isinstance(m, str) and m.strip())[:256]
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

    def _modelo_com_voz(self, session, host):
        """O primeiro modelo que sabe falar (capacidade 'speech'): o pedido, depois os instalados."""
        candidatos = list(dict.fromkeys(m for m in (self.model, *self.voice_candidates) if m))
        algum_informado = False
        for modelo in candidatos:
            caps = capacidades(session, host, modelo)
            algum_informado = algum_informado or bool(caps)
            if "speech" in caps:
                return modelo
        if candidatos and not algum_informado:
            return candidatos[0]        # servidor sem /api/show: tenta o modelo pedido
        raise RuntimeError("Nenhum modelo com voz instalado. Instale um, por exemplo: ollama pull lfm3-omni")

    def _falar_frase(self, session, host, modelo, frase):
        """Uma frase falada pelo modelo: os bytes WAV como vieram (com limite de tamanho)."""
        chunks, total = [], 0
        with session.post(
            f"{host}/v1/audio/speech",
            json={"model": modelo, "input": frase, "response_format": "wav"},
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
                    raise RuntimeError("A resposta de áudio excedeu o limite local.")
                chunks.append(chunk)
        return b"".join(chunks)

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

            if self.operation == "pull":
                # POST /api/pull: JSONL com {"status", "completed", "total"} por camada —
                # o progresso chega sem parar, então o timeout de leitura pode ser folgado.
                if not self.model:
                    raise ValueError("Nome de modelo vazio.")
                if self._cancelled.is_set():
                    return
                with session.post(
                    f"{host}/api/pull",
                    json={"model": self.model, "stream": True},
                    stream=True,
                    timeout=(2, 120),
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
                        dado = json.loads(line)
                        if not isinstance(dado, dict):
                            continue
                        total = dado.get("total") or 0
                        feito = dado.get("completed") or 0
                        pct = round(feito * 100 / total) if total else None
                        self.signals.progress.emit({
                            "status": str(dado.get("status") or "")[:120],
                            "pct": pct,
                        })
                self._set_response(None)
                if not self._cancelled.is_set():
                    self.signals.pull_done.emit()
                return

            if self.operation == "speech":
                # Voz do próprio LLM (/v1/audio/speech), do jeito do Coucou: o modelo que sabe falar,
                # uma requisição por frase e o cabeçalho WAV corrigido.
                if not self.speech_text:
                    raise ValueError("Texto de voz vazio.")
                if self._cancelled.is_set():
                    return
                modelo = self._modelo_com_voz(session, host)
                partes = []
                for frase in speech_chunks(self.speech_text):
                    if self._cancelled.is_set():
                        return
                    partes.append(fix_wav_header(self._falar_frase(session, host, modelo, frase)))
                audio = concat_wavs(partes)
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
    pull_progress = Signal(object)
    pull_finished = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._tasks = set()
        self._tasks_lock = threading.Lock()
        self._max_tasks = 3   # um pull pode baixar em paralelo com o chat

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

    def speak_async(self, model, text, candidates=()):
        """Pede áudio WAV ao /v1/audio/speech do Ollama; `candidates` são outros modelos que podem ter voz."""
        if not isinstance(model, str) or not model.strip():
            self.speech_failed.emit("Nenhum modelo de voz local selecionado.")
            return
        clean = str(text or "").strip()[:MAX_SPEECH_TEXT]
        if not clean:
            return
        task = _OllamaTask(
            "speech", model=model.strip()[:200], speech_text=clean, voice_candidates=candidates
        )
        task.signals.speech_audio.connect(self.speech_ready)
        task.signals.error.connect(self.speech_failed)
        self._submit(task)

    def pull_async(self, model):
        """Baixa um modelo (`/api/pull`) com progresso por sinais; só o loopback, sem proxy."""
        if not isinstance(model, str) or not model.strip():
            self.error.emit("Nome de modelo inválido para baixar.")
            return
        task = _OllamaTask("pull", model=model.strip()[:200])
        task.signals.progress.connect(self.pull_progress)
        task.signals.pull_done.connect(self.pull_finished)
        task.signals.error.connect(self.error)
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
