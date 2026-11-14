"""Garantias do logger compartilhado entre thread Qt, workers e voz."""

import builtins
import threading

from pestinha import log as log_module


def test_escritas_concorrentes_nao_intercalam_linhas(tmp_path, monkeypatch):
    path = tmp_path / "parallel.log"
    monkeypatch.setattr(builtins, "print", lambda *_args, **_kwargs: None)
    log_module.setup(path)
    workers = [
        threading.Thread(
            target=lambda prefix=i: [
                log_module.log(f"worker-{prefix}-{index}") for index in range(20)
            ]
        )
        for i in range(5)
    ]
    try:
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join(timeout=3)
        assert all(not worker.is_alive() for worker in workers)
        lines = path.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 100
        assert all("worker-" in line for line in lines)
        assert len(log_module.recent(10_000)) <= 120
        assert log_module.recent(0) == []
    finally:
        log_module.desligar_arquivo()
