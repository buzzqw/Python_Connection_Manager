"""Regressione: modifiche ravvicinate al crontab non vanno perse."""

import threading

import cron_widget


class _FakeThread:
    def __init__(self, target, daemon=False):
        self.target = target
        self.started = False

    def start(self):
        self.started = True


class _FakeStdin:
    def write(self, _data):
        pass

    class _Channel:
        def shutdown_write(self):
            pass

    channel = _Channel()


class _FakeStdout:
    class _Channel:
        def recv_exit_status(self):
            return 0

    channel = _Channel()


class _FakeStderr:
    def read(self):
        return b""


class _FakeSSH:
    def __init__(self, during_write=None):
        self.during_write = during_write

    def exec_command(self, _cmd, timeout=10):
        if self.during_write:
            self.during_write()
        return _FakeStdin(), _FakeStdout(), _FakeStderr()


class _Widget:
    _scrivi_crontab = cron_widget.CronWidget._scrivi_crontab

    def __init__(self):
        self._ssh = _FakeSSH()
        self._rows = []
        self._write_lock = threading.Lock()
        self._write_pending = False
        self._write_dirty = False

    def _set_status(self, _msg):
        pass


def test_modifica_durante_scrittura_viene_riproposta(monkeypatch):
    monkeypatch.setattr(cron_widget.threading, "Thread", _FakeThread)
    w = _Widget()
    w._write_pending = True  # simula: prima scrittura in corso

    w._scrivi_crontab()

    assert w._write_dirty is True
    assert w._write_pending is True


def test_dirty_crea_un_nuovo_worker(monkeypatch):
    thread = _FakeThread(lambda: None)
    monkeypatch.setattr(cron_widget.threading, "Thread",
                        lambda *a, **k: thread)
    w = _Widget()
    w._ssh.during_write = lambda: setattr(w, "_write_dirty", True)

    w._scrivi_crontab()

    assert thread.started is True
    assert w._write_dirty is False
