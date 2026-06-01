"""
cron_widget.py — Gestione crontab remoto via SSH/paramiko per PCM (GTK3)

Stessa architettura di SysMonitorWidget: connessione paramiko in thread,
aggiornamenti UI via GLib.idle_add.
"""

import os
import re
import threading

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib

try:
    import paramiko
    PARAMIKO_OK = True
except ImportError:
    PARAMIKO_OK = False


# ---------------------------------------------------------------------------
# Parser crontab
# ---------------------------------------------------------------------------

_CRON_RE = re.compile(
    r'^(?P<min>\S+)\s+'
    r'(?P<hour>\S+)\s+'
    r'(?P<dom>\S+)\s+'
    r'(?P<mon>\S+)\s+'
    r'(?P<dow>\S+)\s+'
    r'(?P<cmd>.+)$'
)

# Campo cron valido: solo cifre, *, /, -, , e nomi abbreviati mese/giorno (3 lettere)
_VALID_FIELD = re.compile(r'^[\d*/,\-]+([\d*/,\-]|[A-Za-z]{3})*$')

# Shortcut cron: @reboot, @daily, @weekly, @monthly, @yearly, @hourly, @annually
_SHORTCUT_RE = re.compile(r'^(?P<shortcut>@\w+)\s+(?P<cmd>.+)$')

# Assegnazione variabile ambiente: NOME=valore  (nessuno spazio prima di =)
_ENV_RE = re.compile(r'^\w+=')


def _is_cron_field(s: str) -> bool:
    """True se s è un campo cron valido (non una parola di testo libero)."""
    return bool(_VALID_FIELD.match(s))


def _parse_crontab(text: str) -> list:
    """
    Lista di dict {min,hour,dom,mon,dow,cmd,abilitata} + righe non-cron
    (commenti, variabili ambiente) come {"commento": riga}.

    Gestisce:
    - Voci standard a 5 campi con validazione — esclude righe di commento
      che per caso hanno 6+ token (es. "# Edit this file to introduce…")
    - Shortcut @reboot / @daily / @weekly / @monthly / @yearly / @hourly
    - Variabili ambiente (SHELL=, PATH=…) → preservate ma nascoste
    """
    rows = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue

        enabled = not stripped.startswith("#")
        check   = stripped.lstrip("#").strip()

        if not check:
            continue

        # Variabili ambiente (solo su righe non commentate)
        if enabled and _ENV_RE.match(check):
            rows.append({"commento": stripped})
            continue

        # Shortcut @reboot, @daily, ecc.
        m = _SHORTCUT_RE.match(check)
        if m:
            rows.append({
                "min":      m.group("shortcut"),
                "hour":     "",
                "dom":      "",
                "mon":      "",
                "dow":      "",
                "cmd":      m.group("cmd"),
                "abilitata": enabled,
                "shortcut": True,
            })
            continue

        # Formato standard a 5 campi
        m = _CRON_RE.match(check)
        if m:
            fields = [m.group(f) for f in ("min", "hour", "dom", "mon", "dow")]
            # Tutti e 5 i campi devono sembrare campi cron validi
            if all(_is_cron_field(f) for f in fields):
                rows.append({
                    "min":      m.group("min"),
                    "hour":     m.group("hour"),
                    "dom":      m.group("dom"),
                    "mon":      m.group("mon"),
                    "dow":      m.group("dow"),
                    "cmd":      m.group("cmd"),
                    "abilitata": enabled,
                })
                continue

        # Tutto il resto: riga di commento/testo libero
        rows.append({"commento": stripped})

    return rows


def _rows_to_crontab(rows: list) -> str:
    lines = []
    for r in rows:
        if "commento" in r:
            lines.append(r["commento"])
            continue
        line = f"{r['min']} {r['hour']} {r['dom']} {r['mon']} {r['dow']} {r['cmd']}"
        if not r.get("abilitata", True):
            line = "# " + line
        lines.append(line)
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Dialog add/edit singola voce
# ---------------------------------------------------------------------------

class _CronEntryDialog(Gtk.Dialog):

    def __init__(self, parent, entry=None):
        title = "Nuova voce cron" if entry is None else "Modifica voce cron"
        super().__init__(title=title, transient_for=parent, modal=True)
        self.add_buttons("_Annulla", Gtk.ResponseType.CANCEL,
                         "_OK",      Gtk.ResponseType.OK)
        self.set_default_size(520, 300)
        self._build(entry or {})

    def _build(self, e: dict):
        grid = Gtk.Grid(column_spacing=8, row_spacing=6,
                        margin_start=12, margin_end=12,
                        margin_top=8,   margin_bottom=8)

        def _lbl(txt):
            l = Gtk.Label(label=txt, xalign=1.0)
            l.set_width_chars(13)
            return l

        def _entry(val, ph=""):
            en = Gtk.Entry()
            en.set_text(val)
            en.set_placeholder_text(ph)
            en.set_hexpand(True)
            return en

        self._e_min  = _entry(e.get("min",  "*"), "0-59, *, */5…")
        self._e_hour = _entry(e.get("hour", "*"), "0-23, *, */2…")
        self._e_dom  = _entry(e.get("dom",  "*"), "1-31, *…")
        self._e_mon  = _entry(e.get("mon",  "*"), "1-12, *…")
        self._e_dow  = _entry(e.get("dow",  "*"), "0-7 (0=dom), *…")
        self._e_cmd  = _entry(e.get("cmd",  ""),  "/usr/bin/backup.sh >> /var/log/backup.log 2>&1")
        self._e_cmd.set_hexpand(True)

        for row, (label, widget) in enumerate([
            ("Minuti:",       self._e_min),
            ("Ore:",          self._e_hour),
            ("Giorno mese:",  self._e_dom),
            ("Mese:",         self._e_mon),
            ("Giorno sett.:", self._e_dow),
            ("Comando:",      self._e_cmd),
        ]):
            grid.attach(_lbl(label), 0, row, 1, 1)
            grid.attach(widget,      1, row, 1, 1)

        hint = Gtk.Label()
        hint.set_markup(
            "<small>Esempio: <tt>0 2 * * 0  /usr/bin/backup.sh</tt>"
            "  →  ogni domenica alle 02:00\n"
            "       <tt>*/15 * * * *  /check.sh</tt>"
            "  →  ogni 15 minuti</small>"
        )
        hint.set_xalign(0.0)
        grid.attach(hint, 0, 6, 2, 1)

        self._chk = Gtk.CheckButton(label="Abilitata")
        self._chk.set_active(e.get("abilitata", True))
        grid.attach(self._chk, 0, 7, 2, 1)

        self.get_content_area().add(grid)
        grid.show_all()
        self.set_default_response(Gtk.ResponseType.OK)

    def get_entry(self) -> dict:
        return {
            "min":      self._e_min.get_text().strip()  or "*",
            "hour":     self._e_hour.get_text().strip() or "*",
            "dom":      self._e_dom.get_text().strip()  or "*",
            "mon":      self._e_mon.get_text().strip()  or "*",
            "dow":      self._e_dow.get_text().strip()  or "*",
            "cmd":      self._e_cmd.get_text().strip(),
            "abilitata": self._chk.get_active(),
        }


# ---------------------------------------------------------------------------
# Widget principale
# ---------------------------------------------------------------------------

class CronWidget(Gtk.Box):
    """
    Tab gestione crontab remoto.
    Accetta un profilo sessione SSH e si connette via paramiko
    per leggere/scrivere il crontab utente.
    """

    def __init__(self, profilo: dict):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        self._profilo = profilo
        self._ssh: "paramiko.SSHClient | None" = None
        self._rows: list = []

        self._build_ui()
        self.connect("destroy", lambda _: self._chiudi())

        if PARAMIKO_OK:
            threading.Thread(target=self._connetti, daemon=True).start()
        else:
            self._set_status("❌ paramiko non installato")

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        host = self._profilo.get("host", "?")

        hdr = Gtk.Label()
        hdr.set_markup(f"<b>Cron: {host}</b>")
        hdr.set_xalign(0.0)
        hdr.set_margin_start(8); hdr.set_margin_top(6); hdr.set_margin_bottom(4)
        self.pack_start(hdr, False, False, 0)
        self.pack_start(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL), False, False, 0)

        # Toolbar
        tb = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        tb.set_margin_start(6); tb.set_margin_top(4); tb.set_margin_bottom(4)

        btn_add  = Gtk.Button(label="+ Aggiungi")
        btn_edit = Gtk.Button(label="✎ Modifica")
        btn_del  = Gtk.Button(label="✕ Elimina")
        btn_ref  = Gtk.Button()
        btn_ref.add(Gtk.Image.new_from_icon_name("view-refresh-symbolic",
                                                  Gtk.IconSize.SMALL_TOOLBAR))
        btn_ref.set_tooltip_text("Ricarica crontab dal server")

        btn_add.connect("clicked",  self._on_add)
        btn_edit.connect("clicked", self._on_edit)
        btn_del.connect("clicked",  self._on_delete)
        btn_ref.connect("clicked",  lambda _: threading.Thread(
            target=self._leggi_crontab, daemon=True).start())

        tb.pack_start(btn_add,  False, False, 0)
        tb.pack_start(btn_edit, False, False, 0)
        tb.pack_start(btn_del,  False, False, 0)
        tb.pack_end(btn_ref,    False, False, 0)
        self.pack_start(tb, False, False, 0)
        self.pack_start(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL), False, False, 0)

        # TreeView: abilitata(0), min(1), hour(2), dom(3), mon(4), dow(5), cmd(6)
        self._store = Gtk.ListStore(bool, str, str, str, str, str, str)
        self._view  = Gtk.TreeView(model=self._store)
        self._view.set_headers_visible(True)

        cell_toggle = Gtk.CellRendererToggle()
        cell_toggle.connect("toggled", self._on_toggled)
        col_en = Gtk.TreeViewColumn("On", cell_toggle, active=0)
        col_en.set_min_width(36); col_en.set_max_width(40)
        self._view.append_column(col_en)

        col_specs = [
            ("Min",     50, False),
            ("Ore",     50, False),
            ("G/M",     50, False),
            ("Mese",    50, False),
            ("G/S",     50, False),
            ("Comando", -1, True),
        ]
        for i, (h, w, expand) in enumerate(col_specs, start=1):
            cell = Gtk.CellRendererText()
            col  = Gtk.TreeViewColumn(h, cell, text=i)
            col.set_resizable(True)
            if expand:
                col.set_expand(True)
            else:
                col.set_min_width(w); col.set_max_width(w + 20)
            self._view.append_column(col)

        self._view.connect("row-activated", lambda _v, _p, _c: self._on_edit())

        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scroll.add(self._view)
        self.pack_start(scroll, True, True, 0)

        self._status_lbl = Gtk.Label(label="Connessione in corso…")
        self._status_lbl.set_xalign(0.0)
        self._status_lbl.set_margin_start(8)
        self._status_lbl.set_margin_top(3); self._status_lbl.set_margin_bottom(3)
        self.pack_start(self._status_lbl, False, False, 0)

    def _set_status(self, msg: str):
        self._status_lbl.set_text(msg)

    def grab_focus(self):
        self._view.grab_focus()

    # ------------------------------------------------------------------
    # Connessione SSH
    # ------------------------------------------------------------------

    def _connetti(self):
        try:
            host = self._profilo.get("host", "")
            port = int(self._profilo.get("port", 22))
            user = self._profilo.get("user", "")
            pwd  = self._profilo.get("password", "")
            pkey = self._profilo.get("private_key", "")

            self._ssh = paramiko.SSHClient()
            self._ssh.load_system_host_keys()
            self._ssh.set_missing_host_key_policy(paramiko.RejectPolicy())

            kw = {"hostname": host, "port": port, "username": user, "timeout": 10}
            if pkey and os.path.isfile(pkey):
                kw["key_filename"] = pkey
            elif pwd:
                kw["password"] = pwd

            self._ssh.connect(**kw)
            GLib.idle_add(self._set_status, f"✔ Connesso a {host}")
            self._leggi_crontab()
        except paramiko.ssh_exception.SSHException as e:
            msg = str(e)
            if "not found in known_hosts" in msg or "Unknown server" in msg.lower():
                GLib.idle_add(self._set_status,
                              f"Chiave host non in known_hosts.\n"
                              f"ssh-keyscan -H {self._profilo.get('host','')} >> ~/.ssh/known_hosts")
            else:
                GLib.idle_add(self._set_status, f"✖ {e}")
        except Exception as e:
            GLib.idle_add(self._set_status, f"✖ {e}")

    def _leggi_crontab(self):
        if not self._ssh:
            return
        try:
            _, stdout, _ = self._ssh.exec_command("crontab -l 2>/dev/null", timeout=10)
            text = stdout.read().decode("utf-8", errors="replace")
            rows = _parse_crontab(text)
            GLib.idle_add(self._popola, rows)
        except Exception as e:
            GLib.idle_add(self._set_status, f"✖ Lettura crontab: {e}")

    def _scrivi_crontab(self):
        if not self._ssh:
            return
        try:
            text = _rows_to_crontab(self._rows)
            stdin, stdout, stderr = self._ssh.exec_command("crontab -", timeout=10)
            stdin.write(text.encode("utf-8"))
            stdin.channel.shutdown_write()
            stdout.channel.recv_exit_status()
            err = stderr.read().decode("utf-8", errors="replace").strip()
            if err:
                GLib.idle_add(self._set_status, f"✖ {err}")
            else:
                GLib.idle_add(self._set_status, "✔ Crontab salvato")
        except Exception as e:
            GLib.idle_add(self._set_status, f"✖ Salvataggio: {e}")

    def _chiudi(self):
        if self._ssh:
            try:
                self._ssh.close()
            except Exception:
                pass
            self._ssh = None

    # ------------------------------------------------------------------
    # UI update
    # ------------------------------------------------------------------

    def _popola(self, rows: list):
        self._rows = rows
        self._store.clear()
        cron_rows = [r for r in rows if "commento" not in r]
        for r in cron_rows:
            self._store.append([
                r.get("abilitata", True),
                r.get("min",  "*"), r.get("hour", "*"),
                r.get("dom",  "*"), r.get("mon",  "*"),
                r.get("dow",  "*"), r.get("cmd",  ""),
            ])
        self._set_status(f"✔ {len(cron_rows)} voci cron")

    def _cron_rows(self) -> list:
        """Sottolista di _rows senza commenti puri."""
        return [r for r in self._rows if "commento" not in r]

    def _sel_idx_and_row(self) -> tuple:
        model, it = self._view.get_selection().get_selected()
        if it is None:
            return -1, None
        idx = model.get_path(it).get_indices()[0]
        cron = self._cron_rows()
        return (idx, cron[idx]) if idx < len(cron) else (-1, None)

    def _find_rows_index(self, cron_idx: int) -> int:
        """Converte indice in cron_rows → indice in self._rows."""
        ci = 0
        for i, r in enumerate(self._rows):
            if "commento" in r:
                continue
            if ci == cron_idx:
                return i
            ci += 1
        return -1

    # ------------------------------------------------------------------
    # Azioni
    # ------------------------------------------------------------------

    def _on_toggled(self, _cell, path_str):
        store_idx = int(path_str)
        it = self._store.get_iter_from_string(path_str)
        old = self._store.get_value(it, 0)
        self._store.set_value(it, 0, not old)
        cron = self._cron_rows()
        if store_idx < len(cron):
            cron[store_idx]["abilitata"] = not old
        threading.Thread(target=self._scrivi_crontab, daemon=True).start()

    def _on_add(self, _btn=None):
        dlg = _CronEntryDialog(parent=self.get_toplevel())
        if dlg.run() == Gtk.ResponseType.OK:
            entry = dlg.get_entry()
            if entry["cmd"]:
                self._rows.append(entry)
                self._popola(self._rows)
                threading.Thread(target=self._scrivi_crontab, daemon=True).start()
        dlg.destroy()

    def _on_edit(self, _btn=None):
        idx, row = self._sel_idx_and_row()
        if row is None:
            return
        dlg = _CronEntryDialog(parent=self.get_toplevel(), entry=row)
        if dlg.run() == Gtk.ResponseType.OK:
            nuovo = dlg.get_entry()
            ri = self._find_rows_index(idx)
            if ri >= 0:
                self._rows[ri] = nuovo
            self._popola(self._rows)
            threading.Thread(target=self._scrivi_crontab, daemon=True).start()
        dlg.destroy()

    def _on_delete(self, _btn=None):
        idx, row = self._sel_idx_and_row()
        if row is None:
            return
        schedule = f"{row['min']} {row['hour']} {row['dom']} {row['mon']} {row['dow']}"
        dlg = Gtk.MessageDialog(
            transient_for=self.get_toplevel(),
            modal=True,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.YES_NO,
            text="Eliminare questa voce cron?",
            secondary_text=f"{schedule}  {row['cmd']}"
        )
        if dlg.run() == Gtk.ResponseType.YES:
            ri = self._find_rows_index(idx)
            if ri >= 0:
                del self._rows[ri]
            self._popola(self._rows)
            threading.Thread(target=self._scrivi_crontab, daemon=True).start()
        dlg.destroy()
