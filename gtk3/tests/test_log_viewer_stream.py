"""Regressioni sullo streaming del visualizzatore log."""

import log_viewer


class _CanaleErrore:
    def __init__(self, exc):
        self._exc = exc
        self.chiuso = False
        self.recv_calls = 0

    def exec_command(self, _cmd):
        pass

    def settimeout(self, _t):
        pass

    def recv(self, _n):
        self.recv_calls += 1
        raise self._exc

    def close(self):
        self.chiuso = True


class _CanaleChiusura(_CanaleErrore):
    def __init__(self):
        super().__init__(OSError("broken"))


class _Transport:
    def __init__(self, canale):
        self._canale = canale

    def is_active(self):
        return True

    def open_session(self):
        return self._canale


class _SSH:
    def __init__(self, canale):
        self._transport = _Transport(canale)

    def get_transport(self):
        return self._transport


class _Viewer:
    _leggi = log_viewer.LogViewerWidget._leggi
    _riavvia = log_viewer.LogViewerWidget._riavvia

    def __init__(self, canale):
        self._gen = 0
        self._ssh = _SSH(canale)
        self._canale = None
        self._messaggi = []

    def _append(self, msg):
        self._messaggi.append(msg)

    def _get_cmd(self):
        return "tail -f /var/log/syslog"

    def _set_status(self, _msg):
        pass


class _FakeThread:
    def __init__(self, target, args=(), daemon=False):
        self.target = target

    def start(self):
        pass


def test_errore_socket_non_fa_girare_la_loop(monkeypatch):
    monkeypatch.setattr(log_viewer.GLib, "idle_add",
                        lambda fn, *args: fn(*args) or False)
    viewer = _Viewer(_CanaleErrore(OSError("connection reset")))

    viewer._leggi("tail -f /var/log/syslog", 0)

    assert viewer._canale is None
    assert len(viewer._messaggi) == 1
    assert "connection reset" in viewer._messaggi[0]
    # Un solo tentativo: niente tight-loop su errori persistenti.
    assert viewer._ssh.get_transport()._canale.recv_calls == 1


def test_riavvio_chiude_subito_il_canale_vecchio(monkeypatch):
    vecchio = _CanaleChiusura()
    viewer = _Viewer(vecchio)
    viewer._canale = vecchio
    monkeypatch.setattr(log_viewer.threading, "Thread", _FakeThread)

    viewer._riavvia()

    assert vecchio.chiuso is True
    assert viewer._canale is None
    assert viewer._gen == 1
