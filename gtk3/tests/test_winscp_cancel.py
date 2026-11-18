"""Regressione: annullamento trasferimenti e chiusura sicura (winscp_widget)."""
import winscp_widget
from translations import t


def _job():
    return winscp_widget.TransferJob("download", "/remote/f", "/local/f")


def test_annulla_tutti_senza_ui():
    coda = winscp_widget.CodaWidget()
    j1, j2 = _job(), _job()
    j2.stato = t("winscp.status_running")
    coda.aggiungi_in_attesa(j1)
    coda.aggiungi_in_attesa(j2)
    coda._in_pausa = True

    coda.annulla_tutti(aggiorna_ui=False)

    assert j1.annulla and j2.annulla
    assert j1.stato == t("winscp.status_cancelled")
    assert j2.stato == t("winscp.status_cancelled")
    assert coda.is_in_pausa() is False


def test_annulla_tutti_ignora_job_completati():
    coda = winscp_widget.CodaWidget()
    j = _job()
    j.stato = t("winscp.status_done")
    coda.aggiungi_in_attesa(j)
    coda.annulla_tutti(aggiorna_ui=False)
    assert j.annulla is False
    assert j.stato == t("winscp.status_done")


def test_chiudi_processo_idempotente(monkeypatch):
    monkeypatch.setattr(winscp_widget, "PARAMIKO_OK", False)
    w = winscp_widget.WinScpWidget({"host": "x"})
    j = _job()
    j.stato = t("winscp.status_running")
    w._coda.aggiungi_in_attesa(j)

    w.chiudi_processo()
    w.chiudi_processo()   # non deve sollevare

    assert w._stopped is True
    assert j.annulla is True


def test_ui_idle_noop_dopo_chiusura(monkeypatch):
    monkeypatch.setattr(winscp_widget, "PARAMIKO_OK", False)
    w = winscp_widget.WinScpWidget({"host": "x"})
    w.chiudi_processo()
    chiamate = []
    w._ui_idle(chiamate.append, 1)
    assert chiamate == []
