"""
VOZ - o pet comenta o que sente em voz alta, com frases por emoção.

Frases: pets/<pet>/falas/<motivo>.txt (uma por linha, # é comentário; relidas
quando o arquivo muda, como os recadinhos). Fallback: falas/_padrao.txt ou a
emoção em si ("tô bravo").

Fala: se `voz_url` estiver configurada, POST no seu servidor TTS local
(OpenAI-compatible: POST <url> {"input": texto, "response_format": "wav"});
senão, a voz do Windows (System.Speech) via PowerShell. Tudo local, sem internet,
sempre em processo/thread à parte — nunca trava a tela.
"""

import subprocess
import sys
import threading
import time
import urllib.request

from ..ajustes import VOZ_COOLDOWN_S
from .. import config
from ..log import log


class Voz:
    """Escolhe a frase da emoção atual e fala em voz alta (TTS local), respeitando um intervalo mínimo."""
    def __init__(self, perms, conteudo, debug=lambda: False):
        """Guarda as permissões, o conteúdo do pet e o relógio do último comentário."""
        self.perms = perms
        self.conteudo = conteudo
        self.debug = debug
        self._ultimo = 0.0
        self._frases = {}             # motivo -> config.Notes
        self._falando = False         # já tem uma fala em andamento
        self._lock = threading.Lock()

    def ligado(self):
        """Diz se a voz está ativa (permissão ligada)."""
        return bool(self.perms.get("voz"))

    def _notas(self, motivo):
        """Post-its de fala de um motivo (emoção/evento), criado e relido sob demanda."""
        if motivo not in self._frases:
            self._frases[motivo] = config.Notes(self.conteudo.proprio / "falas" / f"{motivo}.txt")
        return self._frases[motivo]

    def _frase(self, motivo):
        """Uma frase do motivo; fallback para _padrao.txt e, sem arquivos, a frase da emoção."""
        for m in (motivo, "_padrao"):
            notas = self._notas(m)
            if notas.has_lines():
                return notas.pick()
        return {
            "feliz": "tô feliz!", "contente": "hmm, que bom", "curioso": "ah é?",
            "observando": "tô de olho", "bravo": "tô bravo!", "triste": "tô triste...",
            "assustado": "eita!", "dramatico": "inacreditável", "dormindo": "zzz",
            "preso": "me tira daqui!", "fuga": "fui!", "protesto": "chega!",
            "susto": "ui!", "arremesso": "aaaaaaaa!", "notebook": "vou trabalhar",
            "fogos": "foooogos!",
        }.get(motivo, motivo)

    def falar(self, motivo, now=None):
        """Comenta um motivo/emoção em voz alta, se a voz estiver ligada e passou o intervalo."""
        if not self.ligado():
            return None
        now = time.monotonic() if now is None else now
        if now - self._ultimo < VOZ_COOLDOWN_S:
            return None
        texto = self._frase(motivo)
        if not texto:
            return None
        self._ultimo = now
        self._falar_async(texto, motivo)
        return texto

    def _gerar_llm(self, motivo):
        """Gera a frase pela LLM local (Ollama /api/generate); devolve None se falhar."""
        import json
        url = (self.perms.get("voz_url") or "").strip() or "http://localhost:11434/api/generate"
        corpo = {"model": self.perms.get("llm_modelo") or "llama3",
                 "prompt": f"Você é o pet {self.conteudo.proprio.name}. Fale UMA frase curta em "
                           f"português sobre estar {motivo}. Só a frase, sem aspas.",
                 "stream": False}
        req = urllib.request.Request(url, data=json.dumps(corpo).encode(),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            texto = json.loads(resp.read()).get("response", "").strip()
        return texto.split("\n")[0][:120] or None

    def _falar_async(self, texto, motivo=None):
        """Fala sem travar a tela: processo do Windows ou thread para o endpoint HTTP."""
        with self._lock:
            if self._falando:
                return
            self._falando = True

        def rodar():
            try:
                falado = texto
                if self.perms.get("voz_modo") == "llm" and motivo:
                    try:
                        falado = self._gerar_llm(motivo) or texto   # LLM gerou? senão, frase do arquivo
                    except Exception as error:
                        if self.debug():
                            log(f"[voz] LLM falhou, usando frase do arquivo: {error}")
                self._falar_sync(falado)
            except Exception as error:
                if self.debug():
                    log(f"[voz] não falou: {error}")
            finally:
                with self._lock:
                    self._falando = False

        threading.Thread(target=rodar, daemon=True).start()

    def _falar_sync(self, texto):
        """Fala de fato: endpoint TTS local configurado, ou a voz do Windows."""
        url = (self.perms.get("voz_url") or "").strip()
        modo = self.perms.get("voz_modo", "sistema")
        if modo == "tts" and url:
            # servidor local (TTS ou LLM com voz própria): POST {"input": texto}
            corpo = ('{"input": ' + _json_str(texto) + ', "response_format": "wav"}').encode()
            req = urllib.request.Request(url, data=corpo,
                                         headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                resp.read()          # o servidor toca o áudio
            return
        if sys.platform == "win32":
            ps = ("Add-Type -AssemblyName System.Speech; "
                  "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                  "$s.Rate = 1; $s.Speak(" + _ps_str(texto) + ")")
            subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                           capture_output=True, timeout=20, check=False, **_sem_console())
        else:
            subprocess.run(["spd-say", texto], capture_output=True, timeout=20, check=False)


def _sem_console():
    """Argumentos para o subprocesso não abrir janela de console (Windows)."""
    if sys.platform != "win32":
        return {}
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = 0                       # SW_HIDE
    return {"creationflags": subprocess.CREATE_NO_WINDOW, "startupinfo": si}


def _json_str(texto):
    """String em formato JSON (aspa simples de aspas duplas)."""
    return '"' + texto.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ") + '"'


def _ps_str(texto):
    """String em formato PowerShell entre aspas simples (escapando aspa simples)."""
    return "'" + texto.replace("'", "''").replace("\n", " ") + "'"
