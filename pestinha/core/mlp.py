"""
MLP - rede neural feedforward simples, feita do zero com NumPy.

Arquitetura fixa (a do exemplo e do painel "Laboratório MLP"):
    entrada 6 -> oculta 4 (ReLU) -> oculta 4 (ReLU) -> saída 2 (Sigmoid)

Uso:
    rede = NeuralNetwork()
    perdas = rede.train(X, Y, epocas=500, taxa=0.5)
    saida = rede.forward(X)

É uma rede didática, separada da rede pulsada do pet (nervous_system.py):
serve para visualizar forward/backward no painel e para estudos.
"""

import numpy as np

ENTRADA = 6
SAIDA = 2
MAX_EPOCAS = 100_000


class NeuralNetwork:
    """MLP 6-4-4-2: duas camadas ocultas ReLU e saída Sigmoid, com backpropagation por gradiente descendente."""

    def __init__(self, seed=7):
        """Inicializa pesos e bias de cada camada com valores aleatórios pequenos (semente fixa = rede reproduzível)."""
        rng = np.random.default_rng(seed)
        # Xavier simples: pesos pequenos evitam saturação inicial da sigmoid
        self.W1 = rng.normal(0.0, np.sqrt(2.0 / 6), (6, 4))
        self.W2 = rng.normal(0.0, np.sqrt(2.0 / 4), (4, 4))
        self.W3 = rng.normal(0.0, np.sqrt(2.0 / 4), (4, 2))
        self.b1 = np.zeros(4)
        self.b2 = np.zeros(4)
        self.b3 = np.zeros(2)
        self._cache = None

    def _validar_pesos(self):
        """Confere formas e finitude antes das operações matriciais."""
        expected = (
            ("W1", (6, 4)), ("W2", (4, 4)), ("W3", (4, 2)),
            ("b1", (4,)), ("b2", (4,)), ("b3", (2,)),
        )
        for name, shape in expected:
            value = getattr(self, name, None)
            if not isinstance(value, np.ndarray) or value.shape != shape:
                raise ValueError(f"Parâmetro {name} inválido; esperado shape {shape}.")
            if not np.isfinite(value).all():
                raise ValueError(f"Parâmetro {name} contém valor não finito.")

    @staticmethod
    def _entrada(x):
        """Valida uma entrada 6D ou um batch N×6 e retorna (batch, era_vetor)."""
        try:
            values = np.asarray(x, dtype=float)
        except (TypeError, ValueError, OverflowError) as error:
            raise ValueError("Entrada MLP deve conter números válidos.") from error
        single = values.ndim == 1
        if single and values.shape == (ENTRADA,):
            values = values.reshape(1, ENTRADA)
        if values.ndim != 2 or values.shape[1] != ENTRADA or values.shape[0] == 0:
            raise ValueError(f"Entrada MLP inválida; esperado (6,) ou (N, {ENTRADA}).")
        if not np.isfinite(values).all():
            raise ValueError("Entrada MLP contém valor não finito.")
        return values, single

    @staticmethod
    def _alvo(y, n):
        """Valida saídas alvo com forma (2,) para um exemplo ou N×2 para batch."""
        try:
            values = np.asarray(y, dtype=float)
        except (TypeError, ValueError, OverflowError) as error:
            raise ValueError("Alvo MLP deve conter números válidos.") from error
        if values.ndim == 1 and n == 1 and values.shape == (SAIDA,):
            values = values.reshape(1, SAIDA)
        if values.ndim != 2 or values.shape != (n, SAIDA):
            raise ValueError(f"Alvo MLP inválido; esperado ({n}, {SAIDA}).")
        if not np.isfinite(values).all():
            raise ValueError("Alvo MLP contém valor não finito.")
        return values

    # ---------------- funções de ativação ----------------

    @staticmethod
    def relu(z):
        """ReLU: z se positivo, 0 caso contrário."""
        return np.maximum(0.0, z)

    @staticmethod
    def relu_derivada(z):
        """Derivada da ReLU: 1 onde z > 0, senão 0."""
        return (z > 0).astype(float)

    @staticmethod
    def sigmoide(z):
        """Sigmoid: esmaga qualquer número para o intervalo (0, 1)."""
        z = np.clip(z, -60.0, 60.0)
        return 1.0 / (1.0 + np.exp(-z))

    # ---------------- forward ----------------

    def forward(self, x):
        """
        Propaga a entrada pelas 3 camadas e devolve a saída (0..1 em cada neurônio).

        x: array (6,) ou (N, 6). Guarda os intermediários em self._cache para o backward.
        """
        self._validar_pesos()
        x, single = self._entrada(x)
        z1 = x @ self.W1 + self.b1            # entrada -> oculta 1
        if not np.isfinite(z1).all():
            raise FloatingPointError("Ativação não finita na primeira camada.")
        a1 = self.relu(z1)
        z2 = a1 @ self.W2 + self.b2           # oculta 1 -> oculta 2
        if not np.isfinite(z2).all():
            raise FloatingPointError("Ativação não finita na segunda camada.")
        a2 = self.relu(z2)
        z3 = a2 @ self.W3 + self.b3           # oculta 2 -> saída
        if not np.isfinite(z3).all():
            raise FloatingPointError("Ativação não finita na camada de saída.")
        a3 = self.sigmoide(z3)
        self._cache = (x, z1, a1, z2, a2, z3)
        return a3[0] if single else a3

    # ---------------- perda ----------------

    @staticmethod
    def mse(alvo, saida):
        """Erro Quadrático Médio entre a saída e o alvo (a perda que o treino minimiza)."""
        try:
            target = np.asarray(alvo, dtype=float)
            output = np.asarray(saida, dtype=float)
        except (TypeError, ValueError, OverflowError) as error:
            raise ValueError("MSE exige arrays numéricos válidos.") from error
        if target.shape != output.shape or target.size == 0:
            raise ValueError("MSE exige arrays não vazios com dimensões iguais.")
        if not np.isfinite(target).all() or not np.isfinite(output).all():
            raise ValueError("MSE não aceita valores não finitos.")
        return float(np.mean((output - target) ** 2))

    # ---------------- backward ----------------

    def backward(self, x, y, taxa):
        """
        Retropropaga o erro e atualiza pesos e bias por gradiente descendente.

        Para a saída Sigmoid + MSE, o delta da última camada é
        (saida - alvo) * sigmoide'(z3); o resto segue a cadeia das ReLU.
        """
        self._validar_pesos()
        if self._cache is None:
            raise ValueError("Chame forward() antes de backward().")
        provided_x, _single = self._entrada(x)
        cached_x, z1, a1, z2, a2, z3 = self._cache
        if provided_x.shape != cached_x.shape or not np.array_equal(provided_x, cached_x):
            raise ValueError("Entrada de backward difere do batch mais recente de forward.")
        x = cached_x
        y = self._alvo(y, x.shape[0])
        try:
            taxa = float(taxa)
        except (TypeError, ValueError, OverflowError) as error:
            raise ValueError("Taxa de aprendizado inválida.") from error
        if not np.isfinite(taxa) or taxa < 0:
            raise ValueError("Taxa de aprendizado deve ser finita e não negativa.")
        saida = self.sigmoide(z3)
        n = x.shape[0]

        delta3 = (saida - y) * saida * (1.0 - saida)              # dL/dz3
        dW3 = a2.T @ delta3 / n
        db3 = delta3.mean(axis=0)

        delta2 = (delta3 @ self.W3.T) * self.relu_derivada(z2)    # dL/dz2
        dW2 = a1.T @ delta2 / n
        db2 = delta2.mean(axis=0)

        delta1 = (delta2 @ self.W2.T) * self.relu_derivada(z1)    # dL/dz1
        dW1 = x.T @ delta1 / n
        db1 = delta1.mean(axis=0)

        updates = {
            "W3": self.W3 - taxa * dW3,
            "b3": self.b3 - taxa * db3,
            "W2": self.W2 - taxa * dW2,
            "b2": self.b2 - taxa * db2,
            "W1": self.W1 - taxa * dW1,
            "b1": self.b1 - taxa * db1,
        }
        if any(not np.isfinite(value).all() for value in updates.values()):
            raise FloatingPointError("Atualização da MLP produziria pesos não finitos.")
        for name, value in updates.items():
            setattr(self, name, value)

    # ---------------- treino ----------------

    def train(self, X, Y, epocas=500, taxa=0.5, log=False, cancel_event=None):
        """Treina um batch validado; pode interromper entre épocas via cancel_event."""
        try:
            epocas = int(epocas)
            taxa = float(taxa)
        except (TypeError, ValueError, OverflowError) as error:
            raise ValueError("Épocas e taxa precisam ser valores numéricos válidos.") from error
        if not 1 <= epocas <= MAX_EPOCAS:
            raise ValueError(f"Épocas deve estar entre 1 e {MAX_EPOCAS}.")
        if not np.isfinite(taxa) or taxa < 0:
            raise ValueError("Taxa de aprendizado deve ser finita e não negativa.")
        inputs, _single = self._entrada(X)
        targets = self._alvo(Y, inputs.shape[0])
        self._validar_pesos()
        perdas = []
        for epoca in range(epocas):
            if cancel_event is not None and cancel_event.is_set():
                break
            saida = self.forward(inputs)
            perda = self.mse(targets, saida)
            perdas.append(perda)
            self.backward(inputs, targets, taxa)
            if log and (epoca % (epocas // 10 or 1) == 0 or epoca == epocas - 1):
                print(f"época {epoca:>4}: perda {perda:.6f}")
        return perdas


# ============================================================
# Exemplo prático: X com formato 1x6 aprendendo a saída alvo
# ============================================================
if __name__ == "__main__":
    # dados fictícios: uma entrada de 6 features e a saída desejada de 2 neurônios
    X = np.array([[0.2, 0.8, 0.5, 0.1, 0.9, 0.3]])   # 1 x 6
    Y = np.array([[0.9, 0.1]])                      # 1 x 2

    rede = NeuralNetwork()
    print("saída antes do treino:", rede.forward(X).round(3))
    rede.train(X, Y, epocas=2000, taxa=0.5, log=True)
    print("saída depois do treino:", rede.forward(X).round(3), " alvo:", Y)
