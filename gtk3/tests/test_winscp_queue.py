"""Regressioni sulla coda di trasferimento di winscp_widget.py."""

from types import SimpleNamespace

import winscp_widget
from translations import t


def _job():
    return winscp_widget.TransferJob("download", "/remote/f", "/local/f")


class _FakeThread:
    def __init__(self, target, daemon=False):
        self.target = target
        self.daemon = daemon

    def start(self):
        pass


def _widget(monkeypatch):
    monkeypatch.setattr(winscp_widget, "PARAMIKO_OK", False)
    return winscp_widget.WinScpWidget({"host": "x"})


class TestCoda:
    def test_pulisci_annulla_i_job_in_attesa(self):
        coda = winscp_widget.CodaWidget()
        j = _job()
        coda.aggiungi_in_attesa(j)
        coda.pulisci()
        assert j.annulla is True
        assert j.stato == t("winscp.status_cancelled")

    def test_progresso_risolto_per_identita_dopo_rimozione_righe(self):
        """Un job non deve scrivere il progresso su un'altra riga dopo uno spostamento."""
        coda = winscp_widget.CodaWidget()
        running, done, successivo = _job(), _job(), _job()
        running.stato = t("winscp.status_running")
        done.stato = t("winscp.status_done")
        successivo.stato = t("winscp.status_running")
        for j in (running, done, successivo):
            coda.aggiungi_in_attesa(j)

        coda.pulisci()  # rimuove 'done': 'successivo' passa da indice 2 a 1
        coda.aggiorna_progress(successivo, 100, 200)
        assert coda._store[1][6] == 50
        assert coda._store[0][6] == 0

        coda.segna_completato(successivo, True, "")
        assert coda._store[0][5] != "✓ OK"
        assert coda._store[1][5] == "✓ OK"


class TestWorkerUnificato:
    def test_avvia_coda_sposta_i_job_in_pending(self, monkeypatch):
        w = _widget(monkeypatch)
        monkeypatch.setattr(winscp_widget.threading, "Thread", _FakeThread)
        j = _job()
        w._coda.aggiungi_in_attesa(j)

        w._avvia_coda_se_idle()

        assert len(w._pending_jobs) == 1
        assert w._pending_jobs[0][0] is j
        assert w._worker_thread.target == w._run_jobs

    def test_esegui_jobs_con_worker_attivo_resta_in_pending(self, monkeypatch):
        w = _widget(monkeypatch)
        w._worker_thread = SimpleNamespace(is_alive=lambda: True)
        j = _job()

        w._esegui_jobs([j])

        assert len(w._pending_jobs) == 1
        assert w._pending_jobs[0][0] is j
        assert any(entry is j for entry in w._coda._jobs)

    def test_avvia_coda_non_duplica_job_gia_pending(self, monkeypatch):
        w = _widget(monkeypatch)
        monkeypatch.setattr(winscp_widget.threading, "Thread", _FakeThread)
        j = _job()
        w._coda.aggiungi_job(j)
        w._pending_jobs.append((j, 0))

        w._avvia_coda_se_idle()

        assert len(w._pending_jobs) == 1
