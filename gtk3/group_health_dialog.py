"""
group_health_dialog.py - Verifica connettività (Health Check) concorrente per gruppi di sessioni
"""

from __future__ import annotations

import socket
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import gi

gi.require_version("Gtk", "3.0")
import config_manager
from gi.repository import GLib, Gtk
from translations import t


class GroupHealthDialog(Gtk.Dialog):
    """Verifica concorrente raggiungibilità TCP per tutte le macchine di un gruppo."""

    def __init__(self, parent: Gtk.Window | None, gruppo: str):
        super().__init__(
            title=t("ping_group.title", group=gruppo or t("sidebar.no_group").strip()),
            transient_for=parent,
            modal=True,
            destroy_with_parent=True,
        )
        self._gruppo = gruppo
        self.set_default_size(580, 400)
        self._profili = config_manager.load_profiles()
        self._targets = self._trova_target()
        self._build_ui()
        self.show_all()
        GLib.idle_add(self._avvia_controllo)

    def _trova_target(self) -> list[dict]:
        targets = []
        gruppo_slash = f"{self._gruppo}/"
        for nome, dati in sorted(self._profili.items()):
            if not isinstance(dati, dict):
                continue
            g = dati.get("group", "")
            if self._gruppo and not (g == self._gruppo or g.startswith(gruppo_slash)):
                continue
            if not self._gruppo and g:
                continue

            host = (dati.get("host") or "").strip()
            if not host:
                continue
            proto = dati.get("protocol", "ssh")
            try:
                port = int(dati.get("port") or 22)
            except (ValueError, TypeError):
                port = 22

            targets.append({
                "nome": nome,
                "host": host,
                "port": port,
                "proto": proto,
            })
        return targets

    def _build_ui(self):
        area = self.get_content_area()
        area.set_spacing(8)
        area.set_margin_start(14)
        area.set_margin_end(14)
        area.set_margin_top(12)
        area.set_margin_bottom(8)

        # ScrolledWindow con TreeView
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_shadow_type(Gtk.ShadowType.ETCHED_IN)
        scrolled.set_vexpand(True)
        area.pack_start(scrolled, True, True, 0)

        # Model: 0: Nome, 1: Host:Porta, 2: Protocollo, 3: Stato (markup str)
        self._store = Gtk.ListStore(str, str, str, str)
        self._tree = Gtk.TreeView(model=self._store)
        scrolled.add(self._tree)

        col_name = Gtk.TreeViewColumn(t("ping_group.col_session"), Gtk.CellRendererText(), text=0)
        col_name.set_min_width(150)
        self._tree.append_column(col_name)

        col_target = Gtk.TreeViewColumn(t("ping_group.col_target"), Gtk.CellRendererText(), text=1)
        col_target.set_min_width(140)
        self._tree.append_column(col_target)

        col_proto = Gtk.TreeViewColumn(t("dlg_ft.protocol"), Gtk.CellRendererText(), text=2)
        col_proto.set_min_width(70)
        self._tree.append_column(col_proto)

        col_status = Gtk.TreeViewColumn(t("ping_group.col_status"), Gtk.CellRendererText(), markup=3)
        col_status.set_min_width(160)
        self._tree.append_column(col_status)

        # Status label
        self._lbl_status = Gtk.Label(label=t("ping_group.testing"))
        self._lbl_status.set_xalign(0.0)
        area.pack_start(self._lbl_status, False, False, 0)

        # Bottoni
        btn_refresh = self.add_button(t("ping_group.refresh"), Gtk.ResponseType.APPLY)
        btn_refresh.connect("clicked", lambda _: self._avvia_controllo())
        self.add_button(t("dialog.close"), Gtk.ResponseType.CLOSE)

    def _avvia_controllo(self):
        self._store.clear()
        if not self._targets:
            self._lbl_status.set_text(t("ping_group.no_sessions"))
            return

        row_iters = []
        for tg in self._targets:
            it = self._store.append([
                tg["nome"],
                f"{tg['host']}:{tg['port']}",
                tg["proto"].upper(),
                f"<span foreground='gray'>{t('ping_group.testing')}</span>",
            ])
            row_iters.append((it, tg))

        self._lbl_status.set_text(t("ping_group.testing"))

        def _worker(item):
            it, tg = item
            host, port = tg["host"], tg["port"]
            t0 = time.monotonic()
            try:
                with socket.create_connection((host, port), timeout=3.0):
                    ms = int((time.monotonic() - t0) * 1000)
                txt = f"<span foreground='green'>🟢 {t('ping_group.reachable', ms=ms)}</span>"
            except Exception:  # noqa: BLE001
                txt = f"<span foreground='red'>🔴 {t('ping_group.unreachable', port=port)}</span>"

            def _update():
                if self.get_visible():
                    self._store.set_value(it, 3, txt)
            GLib.idle_add(_update)

        def _run_all():
            with ThreadPoolExecutor(max_workers=min(12, len(row_iters) or 1)) as ex:
                list(ex.map(_worker, row_iters))
            GLib.idle_add(lambda: self._lbl_status.set_text(f"✓ {t('ping_group.completed')}") if self.get_visible() else None)

        threading.Thread(target=_run_all, daemon=True).start()
