"""Regressione: intervallo di campionamento usato per la velocità di rete."""

from types import SimpleNamespace

import panel_monitor


class _Canale:
    def __init__(self, chunks):
        self._chunks = list(chunks)

    def settimeout(self, _timeout):
        pass

    def recv(self, _n):
        return self._chunks.pop(0) if self._chunks else b""


class _Pannello:
    _leggi_loop = panel_monitor.InfoPanelWidget._leggi_loop

    def __init__(self, chunks):
        self._attivo = True
        self._profilo = object()
        self._channel = _Canale(chunks)
        self._last_tick = 8.0

    def _dispatch(self, _sections, _dt):
        pass


def test_dt_è_intervallo_tra_sample_non_tempo_di_comando(monkeypatch):
    """Il loop remoto fa sleep dopo ===END: dt deve essere ~2s, non ~0s."""
    dts = []
    monkeypatch.setattr(
        panel_monitor.GLib, "idle_add",
        lambda fn, *args: dts.append(args[1]) or False,
    )
    clock = iter([10.0, 12.0, 14.0])
    monkeypatch.setattr(panel_monitor, "time",
                        SimpleNamespace(monotonic=lambda: next(clock),
                                        sleep=lambda _n: None))

    pannello = _Pannello([
        b"===TICK\n===NET\n1: 100 0 0 0 0 0 0 0 0 200\n===END\n",
        b"===TICK\n===NET\n1: 300 0 0 0 0 0 0 0 0 600\n===END\n",
        b"===TICK\n===NET\n1: 500 0 0 0 0 0 0 0 0 1000\n===END\n",
    ])
    profilo = pannello._profilo
    pannello._leggi_loop(profilo)

    assert len(dts) == 3
    assert all(dt == 2.0 for dt in dts)
