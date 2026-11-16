# Cadência separada: boca no think, braços no frame (pet Qt)

## Problema
- Ao mover `boca.passo()` e `bracos.passo()` do `think()` (10 Hz) para o `frame()` (60 fps),
  a boca passou a responder ~6× mais rápido do que foi afinada — reações que abrem a boca
  (fala, susto, feliz) ficaram secas/rápidas demais.
- Os braços, sim, precisavam do frame: a 10 Hz pareciam "pulos" de animação.

## Correção (pestinha/app.py)
- `think()` voltou a chamar `st.boca.passo(self.voz._falando)` — ritmo original da boca.
- `frame()` mantém apenas `st.bracos.passo(falando, abertura, emocao)` — braços a 60 fps.
- Os braços leem `st.boca.abertura.valor` atualizado a 10 Hz; as molas suavizam, sem engasgo.

## Verificação
- pyflakes limpo; 28 testes de aparência/ilha passando.
- App reiniciado para carregar a mudança.
- SEM commit/push (aguardando pedido do usuário).
