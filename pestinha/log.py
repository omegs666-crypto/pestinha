"""
LOG - um lugar só para mensagens do app: terminal e arquivo em memory/logs/.

O arquivo é aparado quando passa de 1 MB (fica com a metade mais recente).
Se o arquivo não puder ser escrito, a mensagem vai só para o terminal.
"""

import datetime
import sys
import threading
import traceback
from collections import deque
from pathlib import Path

MAX_BYTES = 1_000_000
_file = None
_recent = deque(maxlen=120)
_lock = threading.Lock()
_file_lock = threading.Lock()


def setup(path):
    """Escolhe o arquivo do log (criado sob demanda)."""
    global _file
    with _file_lock:
        _file = Path(path)


def desligar_arquivo():
    """Para de gravar em arquivo (usado ao apagar os dados: nada pode recriar a pasta)."""
    global _file
    with _file_lock:
        _file = None


def _trim():
    """Corta o início do log quando ele passa do limite, para não crescer sem fim."""
    try:
        if _file.exists() and _file.stat().st_size > MAX_BYTES:
            lines = _file.read_text(encoding="utf-8", errors="replace").splitlines()
            _file.write_text("\n".join(lines[len(lines) // 2:]) + "\n", encoding="utf-8")
    except OSError:
        pass


def log(*parts):
    """Escreve uma mensagem no terminal e no arquivo do log (uma linha por chamada)."""
    text = " ".join(str(p) for p in parts)
    with _lock:
        _recent.append(text)
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode("ascii", "replace").decode("ascii"))
    _gravar(text)


def recent(limit=80):
    """Cópia das mensagens recentes para a interface; não lê disco nem bloqueia o logger."""
    limit = max(0, int(limit))
    if not limit:
        return []
    with _lock:
        return list(_recent)[-limit:]


def _gravar(text):
    """Acrescenta a mensagem ao arquivo do log, se houver um."""
    with _file_lock:
        if _file is None:
            return
        try:
            _file.parent.mkdir(parents=True, exist_ok=True)
            stamp = datetime.datetime.now().isoformat(timespec="seconds")
            with open(_file, "a", encoding="utf-8") as f:
                f.write(f"{stamp} {text}\n")
            _trim()
        except OSError:
            pass


def capturar_erros():
    """Grava no log os erros não tratados: o executável não tem terminal onde eles apareceriam."""
    anterior = sys.excepthook
    if getattr(anterior, "_do_pestinha", False):
        return

    def gancho(tipo, valor, rastro):
        """Registra o erro e deixa o tratamento anterior seguir normalmente."""
        _gravar("[erro] " + "".join(traceback.format_exception(tipo, valor, rastro)).rstrip())
        anterior(tipo, valor, rastro)

    gancho._do_pestinha = True
    sys.excepthook = gancho
