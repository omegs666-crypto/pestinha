"""
SEGUNDO CÉREBRO - o diário e o aprendizado do pet em Markdown, dentro do seu vault do Obsidian.

Opt-in e desligado por padrão. Tudo fica no seu computador: o pet só ESCREVE dentro
de <vault>/Pestinha/<pet>/ (diario/<data>.md, aprendizado.md, perfil.md) — nunca lê
nada do vault e nunca grava nome de programa nem título de janela, só categorias e
números, como a timeline.
"""

import datetime
from pathlib import Path

from ..ajustes import SEGUNDO_CELEBRO_MAX_LINHAS
from ..log import log
from ..paths import pet_id_valido
from ..store import append_line, pasta_gravavel, read_lines, write_text


class SegundoCerebro:
    """Escreve o "segundo cérebro" do pet num vault do Obsidian: diário do dia, o que ele aprendeu e a ficha dele."""
    def __init__(self, perms, pet_id, nome):
        """Guarda as permissões (a mesma referência do app: mudança de configuração vale na hora), o pet e os buffers de escrita."""
        self.perms = perms
        self.pet_id = pet_id
        self.nome = nome
        self._eventos = []          # (datetime, texto) esperando o próximo salvar
        self._linhas_dia = None     # quantas linhas o diário de hoje já tem (None = ainda não conferi)
        self._dia = None            # data do diário em aberto
        self._ultimo_aprendizado = None
        self._ultimo_perfil = None
        self._avisou_erro = False   # erro de escrita já avisado nesta sessão (uma vez basta)

    # ---------------- pasta ----------------

    def _base(self):
        """Pasta do pet dentro do vault escolhido (ou None se não configurado)."""
        pasta = self.perms.get("segundo_celebro_pasta")
        if not isinstance(pasta, str) or not pasta.strip():
            return None
        return Path(pasta) / "Pestinha" / self.pet_id

    def ligado(self):
        """Diz se o segundo cérebro está ativo agora (permissão + pasta válida)."""
        return (bool(self.perms.get("segundo_celebro"))
                and self._base() is not None
                and pet_id_valido(self.pet_id))

    # ---------------- diário ----------------

    def registrar(self, texto):
        """Guarda um evento do diário (grava de verdade no próximo `salvar`). Ignorado se desligado."""
        if self.ligado() and len(self._eventos) < SEGUNDO_CELEBRO_MAX_LINHAS:
            self._eventos.append((datetime.datetime.now(), texto))

    def _diario(self, base, hoje):
        """Arquivo do diário de um dia."""
        return base / "diario" / f"{hoje:%Y-%m-%d}.md"

    def _linhas_ate_agora(self, arquivo, hoje):
        """Quantas linhas o diário de hoje já tem no disco (confere uma vez por dia)."""
        if self._dia != hoje or self._linhas_dia is None:
            self._dia = hoje
            self._linhas_dia = len(read_lines(arquivo)) if arquivo.exists() else 0
        return self._linhas_dia

    def _salvar_eventos(self, base, agora):
        """Despeja os eventos pendentes no diário de hoje, respeitando o limite de linhas."""
        hoje = agora.date()
        arquivo = self._diario(base, hoje)
        tem = self._linhas_ate_agora(arquivo, hoje)
        if not arquivo.exists():
            write_text(arquivo, f"# Diário de {self.nome} — {hoje:%d/%m/%Y}\n\n")
            tem = len(read_lines(arquivo))
        vagas = SEGUNDO_CELEBRO_MAX_LINHAS - tem
        for quando, texto in self._eventos[:max(0, vagas)]:
            append_line(arquivo, f"- **{quando:%H:%M}** {texto}")
            tem += 1
        if len(self._eventos) > vagas and vagas > 0:
            append_line(arquivo, "- **…** *(mais eventos do dia no limite do diário)*")
            tem += 1
        self._linhas_dia = tem
        self._eventos.clear()

    # ---------------- aprendizado e perfil ----------------

    def _texto_aprendizado(self, learned, condicionamento, castigo, drives, agora):
        """Monta aprendizado.md: o que a rede aprendeu, o que ele antecipa e os números do castigo e da homeostase."""
        linhas = [f"# O que {self.nome} aprendeu", f"_Atualizado em {agora:%d/%m/%Y %H:%M}_", ""]
        if learned:
            linhas += ["## Carinho e bronca",
                       "(o que estava acontecendo quando ele recebeu carinho ou foi dispensado)", ""]
            linhas += [f"- `{canal} → {post}` {peso:+.3f}" for canal, post, peso in learned]
        else:
            linhas += ["## Carinho e bronca", "", "Nada aprendido ainda."]
        linhas += ["", "## Antecipações",
                   "(o que ele aprendeu a esperar, pelo condicionamento)", ""]
        for pista, forca in sorted(condicionamento.items()):
            linhas.append(f"- `{pista}`: {forca:.2f}")
        linhas += ["", "## Cantinho do castigo", "",
                   f"- fugas que deram certo: **{castigo['fugas']:.0f}**",
                   f"- rancor: {castigo['rancor']:.2f} · receio: {castigo['receio']:.2f}",
                   "", "## Equilíbrio interno", "",
                   f"- energia: {drives['energia']:.2f} · estímulo: {drives['estimulo']:.2f} · carinho: {drives['contato']:.2f}"]
        return "\n".join(linhas) + "\n"

    def _texto_perfil(self, emocao, agora):
        """Monta perfil.md: a ficha do pet e como ele está agora."""
        return (f"# {self.nome}\n\n"
                f"_Atualizado em {agora:%d/%m/%Y %H:%M}_\n\n"
                f"- emoção agora: **{emocao}**\n")

    # ---------------- gravação ----------------

    def salvar(self, learned, condicionamento, castigo, drives, emocao, agora=None):
        """Grava o que mudou: anexa os eventos no diário e reescreve aprendizado/perfil só quando o texto muda.

        `learned` é a lista de brain.learned_summary(); `condicionamento` é o dict de forças;
        `castigo` tem fugas/rancor/receio; `drives` tem energia/estimulo/contato; `emocao` é a atual.
        """
        if not self.ligado():
            self._eventos.clear()
            return
        base = self._base()
        try:
            if not pasta_gravavel(base):
                if not self._avisou_erro:
                    log(f"[segundo cérebro] não consigo gravar em {base}")
                    self._avisou_erro = True
                return
        except OSError:
            if not self._avisou_erro:
                log(f"[segundo cérebro] erro ao verificar {base}")
                self._avisou_erro = True
            return
        agora = agora or datetime.datetime.now()
        try:
            if self._eventos:
                self._salvar_eventos(base, agora)
        except OSError as error:
            if not self._avisou_erro:
                log(f"[segundo cérebro] não gravou o diário: {error}")
                self._avisou_erro = True
        aprendizado = self._texto_aprendizado(learned, condicionamento, castigo, drives, agora)
        if aprendizado != self._ultimo_aprendizado:
            try:
                write_text(base / "aprendizado.md", aprendizado)
                self._ultimo_aprendizado = aprendizado
            except OSError as error:
                if not self._avisou_erro:
                    log(f"[segundo cérebro] não gravou o aprendizado: {error}")
                    self._avisou_erro = True
        perfil = self._texto_perfil(emocao, agora)
        if perfil != self._ultimo_perfil:
            try:
                write_text(base / "perfil.md", perfil)
                self._ultimo_perfil = perfil
            except OSError as error:
                if not self._avisou_erro:
                    log(f"[segundo cérebro] não gravou o perfil: {error}")
                    self._avisou_erro = True
