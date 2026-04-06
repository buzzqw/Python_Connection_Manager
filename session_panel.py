"""
session_panel.py - Pannello sidebar sessioni PCM
Layout lineare: sessioni raggruppate per gruppo, ordinate per nome.
Ogni sessione: icona protocollo (SVG) | nome — utente@host:porta
"""

import os

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QTreeWidget, QTreeWidgetItem, QMenu, QToolButton,
    QFrame, QMessageBox, QApplication
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QFont, QColor, QIcon, QPixmap, QPainter

import config_manager

# ---------------------------------------------------------------------------
# Percorso assoluto della cartella icons (accanto a questo file)
# ---------------------------------------------------------------------------

_HERE = os.path.dirname(os.path.abspath(__file__))
_ICONS = os.path.join(_HERE, "icons")


def _icon_path(filename: str) -> str:
    return os.path.join(_ICONS, filename)


# ---------------------------------------------------------------------------
# Mappe protocollo
# ---------------------------------------------------------------------------

PROTO_COLOR = {
    "ssh":        "#4ec9b0",
    "telnet":     "#c9b458",
    "sftp":       "#6ab187",
    "ftp":        "#b87a00",
    "rdp":        "#0078d4",
    "vnc":        "#e8a020",
    "ssh_tunnel": "#9b72aa",
    "mosh":       "#5aadad",
    "serial":     "#888888",
}

# filename PNG (nella cartella icons/)
PROTO_ICON_FILE = {
    "ssh":        "ssh.png",
    "telnet":     "network.png",
    "sftp":       "folder.png",
    "ftp":        "folder.png",
    "rdp":        "monitor.png",
    "vnc":        "vnc.png",
    "ssh_tunnel": "tunnel.png",
    "mosh":       "flash.png",
    "serial":     "cable.png",
}

PROTO_LABEL = {
    "ssh":        "SSH",
    "telnet":     "Telnet",
    "sftp":       "SFTP",
    "ftp":        "FTP",
    "rdp":        "RDP",
    "vnc":        "VNC",
    "ssh_tunnel": "Tunnel",
    "mosh":       "Mosh",
    "serial":     "Serial",
}

_PORTE_STD = {
    "ssh": "22", "telnet": "23", "rdp": "3389",
    "vnc": "5900", "ftp": "21", "sftp": "22",
    "mosh": "22", "ssh_tunnel": "22",
}

_SEPARATOR_ROLE = Qt.ItemDataRole.UserRole + 1

# Cache icone già caricate
_ICON_CACHE: dict[str, QIcon] = {}


# ---------------------------------------------------------------------------
# Icona con fallback su pallino colorato
# ---------------------------------------------------------------------------

def _get_icon(proto: str) -> QIcon:
    if proto in _ICON_CACHE:
        return _ICON_CACHE[proto]

    fname = PROTO_ICON_FILE.get(proto, "terminal.png")
    path  = _icon_path(fname)

    ico = QIcon()
    if os.path.isfile(path):
        ico = QIcon(path)

    if ico.isNull():
        # Fallback: cerchietto colorato 14×14
        colore = QColor(PROTO_COLOR.get(proto, "#aaaaaa"))
        pm = QPixmap(14, 14)
        pm.fill(Qt.GlobalColor.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(colore)
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(1, 1, 12, 12)
        p.end()
        ico = QIcon(pm)

    _ICON_CACHE[proto] = ico
    return ico


# ---------------------------------------------------------------------------
# Etichetta host
# ---------------------------------------------------------------------------

def _label_host(dati: dict) -> str:
    proto  = dati.get("protocol", "ssh")
    host   = dati.get("host", "")
    porta  = str(dati.get("port", ""))
    utente = dati.get("user", "")

    if proto == "serial":
        device = dati.get("device", "")
        baud   = dati.get("baud", "")
        return f"{device}  {baud}bps" if baud else device

    info = f"{utente}@{host}" if utente else host
    std  = _PORTE_STD.get(proto, "")
    if porta and porta != std:
        info += f":{porta}"
    return info


# ---------------------------------------------------------------------------
# SessionPanel
# ---------------------------------------------------------------------------

class SessionPanel(QWidget):

    sessione_aperta    = pyqtSignal(str, dict)
    sessione_modifica  = pyqtSignal(str, dict)
    sessione_eliminata = pyqtSignal(str)
    nuova_sessione     = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._profili: dict = {}
        self._init_ui()
        self.aggiorna()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        hdr = QLabel("  Sessioni")
        hdr.setStyleSheet(
            "background:#f0f0f0; color:#4e7abc; font-size:13px; font-weight:bold; "
            "padding:8px; border-bottom:1px solid #ccc;"
        )
        layout.addWidget(hdr)

        # Toolbar
        tb = QHBoxLayout()
        tb.setContentsMargins(4, 3, 4, 3)
        tb.setSpacing(2)
        for testo, tooltip, slot in [
            ("➕", "Nuova sessione",  self.nuova_sessione.emit),
            ("↺",  "Aggiorna lista",  self.aggiorna),
            ("▼",  "Espandi tutto",   lambda: self.tree.expandAll()),
            ("▲",  "Comprimi tutto",  lambda: self.tree.collapseAll()),
        ]:
            b = QToolButton()
            b.setText(testo)
            b.setToolTip(tooltip)
            b.clicked.connect(slot)
            b.setStyleSheet(
                "QToolButton { background:transparent; color:#555; border:none; "
                "font-size:14px; padding:1px 4px; }"
                "QToolButton:hover { color:#111; background:#d0d0d0; border-radius:3px; }"
            )
            tb.addWidget(b)
        tb.addStretch()
        layout.addLayout(tb)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color:#ccc;")
        layout.addWidget(sep)

        # Ricerca
        self.edit_cerca = QLineEdit()
        self.edit_cerca.setPlaceholderText("Cerca sessione…")
        self.edit_cerca.setClearButtonEnabled(True)
        self.edit_cerca.setStyleSheet(
            "background:#ffffff; color:#111111; border:none; "
            "border-bottom:1px solid #ccc; padding:6px 8px; font-size:12px;"
        )
        self.edit_cerca.textChanged.connect(self._filtra)
        layout.addWidget(self.edit_cerca)

        # Albero
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setIndentation(14)
        self.tree.setAnimated(True)
        self.tree.setIconSize(QSize(16, 16))
        self.tree.itemDoubleClicked.connect(self._doppio_clic)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._menu_contestuale)
        layout.addWidget(self.tree, 1)

        # Contatore
        self.lbl_count = QLabel()
        self.lbl_count.setStyleSheet(
            "background:#f0f0f0; color:#555555; font-size:10px; "
            "padding:3px 8px; border-top:1px solid #ccc;"
        )
        layout.addWidget(self.lbl_count)

    # ------------------------------------------------------------------
    # Dati
    # ------------------------------------------------------------------

    def aggiorna(self):
        self._profili = config_manager.load_profiles()
        self._costruisci_albero(self._profili)

    def _costruisci_albero(self, profili: dict, filtro: str = ""):
        self.tree.clear()
        filtro = filtro.strip().lower()

        struttura: dict[str, list] = {}
        for nome, dati in profili.items():
            if filtro:
                haystack = (
                    nome.lower()
                    + dati.get("host", "").lower()
                    + dati.get("user", "").lower()
                )
                if filtro not in haystack:
                    continue
            gruppo = dati.get("group", "").strip() or ""
            struttura.setdefault(gruppo, []).append((nome, dati))

        if not struttura:
            self.lbl_count.setText("   0 sessioni")
            return

        # Gruppi nominati A→Z, poi "" (senza gruppo)
        gruppi_ordinati = sorted(g for g in struttura if g)
        if "" in struttura:
            gruppi_ordinati.append("")

        totale = 0
        primo  = True

        for gruppo in gruppi_ordinati:
            sessioni = struttura[gruppo]
            totale  += len(sessioni)

            # Separatore orizzontale tra gruppi
            if not primo:
                sep_item = QTreeWidgetItem([""])
                sep_item.setFlags(Qt.ItemFlag.NoItemFlags)
                sep_item.setData(0, _SEPARATOR_ROLE, True)
                sep_item.setBackground(0, QColor("#cccccc"))
                sep_item.setSizeHint(0, sep_item.sizeHint(0).__class__(0, 5))
                self.tree.addTopLevelItem(sep_item)
            primo = False

            # Nodo gruppo
            label_g = f"  📂  {gruppo}" if gruppo else "  (senza gruppo)"
            ng = QTreeWidgetItem([label_g])
            ng.setFont(0, QFont("sans-serif", 10, QFont.Weight.Bold))
            ng.setForeground(0, QColor("#4e7abc" if gruppo else "#888888"))
            ng.setData(0, Qt.ItemDataRole.UserRole, None)
            ng.setData(0, _SEPARATOR_ROLE, False)
            ng.setToolTip(0, f"{len(sessioni)} connessioni nel gruppo")
            self.tree.addTopLevelItem(ng)

            # Sessioni figlie ordinate per nome
            for nome, dati in sorted(sessioni, key=lambda x: x[0].lower()):
                proto    = dati.get("protocol", "ssh")
                colore   = PROTO_COLOR.get(proto, "#aaaaaa")
                tag      = PROTO_LABEL.get(proto, proto.upper())
                host_str = _label_host(dati)

                label = f"  {nome}"
                if host_str:
                    label += f"  —  {host_str}"

                child = QTreeWidgetItem([label])
                child.setIcon(0, _get_icon(proto))
                child.setForeground(0, QColor(colore))
                child.setData(0, Qt.ItemDataRole.UserRole, nome)
                child.setData(0, _SEPARATOR_ROLE, False)

                utente = dati.get("user", "")
                host   = dati.get("host", "")
                porta  = dati.get("port", "")
                note   = dati.get("notes", "")
                macros = dati.get("macros", [])

                tt = f"[{tag}]  {utente}@{host}:{porta}" if utente else f"[{tag}]  {host}:{porta}"
                if note:
                    tt += f"\n\n📝 {note}"
                if macros:
                    tt += "\n\n⚡ Macro: " + ", ".join(
                        m.get("nome") or m.get("cmd", "") for m in macros
                    )
                child.setToolTip(0, tt)
                ng.addChild(child)

            ng.setExpanded(True)

        n_gruppi = len(gruppi_ordinati)
        self.lbl_count.setText(f"   {totale} sessioni  ·  {n_gruppi} gruppi")

    # ------------------------------------------------------------------
    # Filtro e interazioni
    # ------------------------------------------------------------------

    def _filtra(self, testo: str):
        self._costruisci_albero(self._profili, filtro=testo)

    def _doppio_clic(self, item: QTreeWidgetItem, _col: int):
        if item.data(0, _SEPARATOR_ROLE):
            return
        nome = item.data(0, Qt.ItemDataRole.UserRole)
        if nome and nome in self._profili:
            self.sessione_aperta.emit(nome, self._profili[nome])

    def _menu_contestuale(self, pos):
        item = self.tree.itemAt(pos)
        if not item or item.data(0, _SEPARATOR_ROLE):
            return
        nome = item.data(0, Qt.ItemDataRole.UserRole)
        if not nome or nome not in self._profili:
            return

        profilo = self._profili[nome]
        menu = QMenu(self)
        menu.addAction("▶  Connetti",  lambda: self.sessione_aperta.emit(nome, profilo))
        menu.addSeparator()
        menu.addAction("✏  Modifica",  lambda: self.sessione_modifica.emit(nome, profilo))
        menu.addAction("📋  Duplica",  lambda: self._duplica(nome, profilo))
        menu.addSeparator()

        macros = profilo.get("macros", [])
        if macros:
            mm = menu.addMenu("⚡  Macro")
            for m in macros:
                nome_m = m.get("nome") or m.get("cmd", "")
                cmd_m  = m.get("cmd", "")
                mm.addAction(nome_m,
                    lambda c=cmd_m: self.sessione_aperta.emit(f"__macro__:{c}", profilo))
            menu.addSeparator()

        menu.addAction("📋  Copia comando", lambda: self._copia_comando(nome, profilo))
        menu.addAction("📄  Esporta apri-connessione.sh…", lambda: self._esporta_sh(nome, profilo))
        menu.addSeparator()
        menu.addAction("🌐  Verifica raggiungibilità…", lambda: self._verifica_raggiungibilita(nome, profilo))
        menu.addSeparator()
        menu.addAction("🗑  Elimina",       lambda: self._chiedi_elimina(nome))
        menu.exec(self.tree.mapToGlobal(pos))

    # ------------------------------------------------------------------
    # Operazioni
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Feature 4: Verifica raggiungibilità
    # ------------------------------------------------------------------

    def _verifica_raggiungibilita(self, nome: str, profilo: dict):
        """
        Dialog di verifica raggiungibilità: ping + TCP + DNS.
        Il thread di rete scrive in una queue; un QTimer nel thread
        principale svuota la coda e aggiorna la UI — sicuro per PyQt6.
        """
        import socket
        import subprocess
        import threading
        import queue as _queue
        from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QLabel,
                                     QDialogButtonBox, QTextEdit, QPushButton)
        from PyQt6.QtCore import QTimer
        from PyQt6.QtGui import QColor, QTextCursor

        host  = profilo.get("host", "")
        proto = profilo.get("protocol", "ssh")
        _PORTE = {"ssh": 22, "telnet": 23, "sftp": 22, "ftp": 21,
                  "rdp": 3389, "vnc": 5900, "mosh": 22, "ssh_tunnel": 22}
        porta = int(profilo.get("port", _PORTE.get(proto, 22)) or _PORTE.get(proto, 22))

        # Coda thread-safe: ogni item è (testo, colore_hex)
        q = _queue.Queue()
        done = threading.Event()

        # ── Dialog ────────────────────────────────────────────────────
        dlg = QDialog()
        dlg.setWindowTitle(f"Verifica raggiungibilita — {nome}")
        dlg.setMinimumWidth(560)
        dlg.setMinimumHeight(340)
        lay = QVBoxLayout(dlg)

        lbl = QLabel(
            f"<b>Host:</b> {host} &nbsp;&nbsp; "
            f"<b>Porta:</b> {porta} &nbsp;&nbsp; "
            f"<b>Protocollo:</b> {proto.upper()}"
        )
        lbl.setStyleSheet("padding:6px;")
        lay.addWidget(lbl)

        log = QTextEdit()
        log.setReadOnly(True)
        log.setStyleSheet(
            "background:#1a1a1a; color:#cccccc; "
            "font-family:monospace; font-size:11px; border:none;"
        )
        lay.addWidget(log, 1)

        btn_chiudi = QPushButton("Chiudi")
        btn_chiudi.setEnabled(False)   # abilitato solo a fine test
        btn_chiudi.clicked.connect(dlg.accept)
        lay.addWidget(btn_chiudi)

        # ── Funzione UI-safe per appendere testo ──────────────────────
        def _ui_append(msg: str, colore: str = "#cccccc"):
            """Chiamata SOLO dal thread principale tramite QTimer."""
            log.setTextColor(QColor(colore))
            log.append(msg)
            log.moveCursor(QTextCursor.MoveOperation.End)

        # ── Thread di rete (NON tocca la UI direttamente) ─────────────
        def _run():
            def w(msg, col="#cccccc"):
                q.put((msg, col))

            # 1. DNS
            w(f"-> Risoluzione DNS: {host}", "#88ccff")
            ip_risolto = host
            try:
                ip_risolto = socket.gethostbyname(host)
                w(f"   OK  {host} -> {ip_risolto}", "#55dd55")
            except Exception as e:
                w(f"   FAIL DNS: {e}", "#dd5555")

            # 2. Ping (3 pacchetti, -W 2 = timeout 2s per pacchetto)
            w(f"", "#cccccc")
            w(f"-> Ping {host} (3 pacchetti)...", "#88ccff")
            try:
                r = subprocess.run(
                    ["ping", "-c", "3", "-W", "2", host],
                    capture_output=True, text=True, timeout=12
                )
                for line in r.stdout.strip().splitlines():
                    if line.strip():
                        w(f"   {line}")
                if r.returncode == 0:
                    w("   OK  Ping riuscito", "#55dd55")
                else:
                    w("   WARN Host non risponde al ping (ICMP bloccato o host spento)", "#ddaa44")
            except subprocess.TimeoutExpired:
                w("   FAIL Timeout ping (12s)", "#dd5555")
            except FileNotFoundError:
                w("   WARN comando ping non trovato", "#ddaa44")
            except Exception as e:
                w(f"   FAIL {e}", "#dd5555")

            # 3. Check porta TCP
            w(f"", "#cccccc")
            w(f"-> Connessione TCP {host}:{porta}...", "#88ccff")
            try:
                s = socket.create_connection((host, porta), timeout=5)
                s.close()
                w(f"   OK  Porta {porta} aperta", "#55dd55")
            except socket.timeout:
                w(f"   FAIL Porta {porta} timeout (firewall?)", "#dd5555")
            except ConnectionRefusedError:
                w(f"   FAIL Porta {porta} rifiutata (servizio non avviato?)", "#dd5555")
            except Exception as e:
                w(f"   FAIL {e}", "#dd5555")

            w("", "#cccccc")
            w("-- Fine --", "#888888")
            done.set()

        # ── QTimer che svuota la coda nel thread principale ───────────
        timer = QTimer(dlg)

        def _flush():
            while not q.empty():
                try:
                    msg, col = q.get_nowait()
                    _ui_append(msg, col)
                except _queue.Empty:
                    break
            if done.is_set() and q.empty():
                timer.stop()
                btn_chiudi.setEnabled(True)

        timer.timeout.connect(_flush)
        timer.start(80)   # svuota la coda ogni 80ms

        # ── Avvio ─────────────────────────────────────────────────────
        t = threading.Thread(target=_run, daemon=True)
        t.start()
        dlg.exec()
        timer.stop()

    # ------------------------------------------------------------------
    # Feature 11: Esporta come script .sh
    # ------------------------------------------------------------------

    def _esporta_sh(self, nome: str, profilo: dict):
        """Genera uno script shell standalone per la sessione e lo salva."""
        import shlex
        from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QLabel,
                                     QTextEdit, QDialogButtonBox,
                                     QFileDialog, QPushButton, QHBoxLayout)

        from session_command import build_command
        cmd, modalita = build_command(profilo)
        if not cmd:
            QMessageBox.warning(self, "Esporta", "Impossibile costruire il comando per questa sessione.")
            return

        proto = profilo.get("protocol", "ssh").upper()
        host  = profilo.get("host", "")
        note  = profilo.get("notes", "").strip()
        pre   = profilo.get("pre_cmd", "").strip()

        righe = [
            "#!/usr/bin/env bash",
            f"# PCM — Sessione esportata: {nome}",
            f"# Protocollo: {proto}   Host: {host}",
        ]
        if note:
            for r in note.splitlines():
                righe.append(f"# {r}")
        righe.append("")
        righe.append("set -e")
        righe.append("")

        if pre:
            righe.append("# Comando locale pre-connessione")
            righe.append(pre)
            righe.append("")

        wol_mac = profilo.get("wol_mac", "").strip()
        if profilo.get("wol_enabled") and wol_mac:
            righe.append("# Wake-on-LAN")
            righe.append(f'wakeonlan "{wol_mac}" 2>/dev/null || '
                         f'python3 -c "'
                         f'import socket,struct; mac=bytes(int(x,16) for x in \"{wol_mac}\".split(\":\")); '
                         f's=socket.socket(socket.AF_INET,socket.SOCK_DGRAM); '
                         f's.setsockopt(socket.SOL_SOCKET,socket.SO_BROADCAST,1); '
                         f's.sendto(b\"\\xff\"*6+mac*16,(\"255.255.255.255\",9))"')
            wait = int(profilo.get("wol_wait", 20))
            righe.append(f'echo "WoL inviato, attendo {wait}s..."')
            righe.append(f'sleep {wait}')
            righe.append("")

        righe.append("# Connessione")
        righe.append(cmd)
        righe.append("")

        script = "\n".join(righe)

        # Dialog preview
        dlg = QDialog()
        dlg.setWindowTitle(f"📄  Esporta apri-connessione.sh — {nome}")
        dlg.setMinimumSize(620, 420)
        lay = QVBoxLayout(dlg)
        lay.addWidget(QLabel(
            f"Script <b>apri-connessione.sh</b> per {nome} ({proto} {host}).<br>"
            f"<small style='color:#888'>Per esportare i comandi digitati: tasto destro sul <b>tab</b> della sessione → 'Esporta comandi.sh'</small>"
        ))

        txt = QTextEdit()
        txt.setPlainText(script)
        txt.setStyleSheet("font-family:monospace; font-size:11px; background:#1a1a1a; color:#cccccc;")
        lay.addWidget(txt, 1)

        btn_row = QHBoxLayout()
        btn_salva  = QPushButton("💾  Salva .sh…")
        btn_copia  = QPushButton("📋  Copia negli appunti")
        btn_chiudi = QPushButton("Chiudi")

        def _salva():
            nome_file = "apri-connessione_" + nome.replace(" ", "_").replace("/", "_") + ".sh"
            path, _ = QFileDialog.getSaveFileName(
                dlg, "Salva script", os.path.join(os.path.expanduser("~"), nome_file),
                "Script shell (*.sh);;Tutti i file (*)"
            )
            if path:
                with open(path, "w") as f:
                    f.write(txt.toPlainText())
                os.chmod(path, 0o755)
                QMessageBox.information(dlg, "Salvato", f"Script salvato e reso eseguibile:\n{path}")

        def _copia():
            QApplication.clipboard().setText(txt.toPlainText())
            btn_copia.setText("✅  Copiato!")

        btn_salva.clicked.connect(_salva)
        btn_copia.clicked.connect(_copia)
        btn_chiudi.clicked.connect(dlg.accept)
        btn_row.addWidget(btn_salva)
        btn_row.addWidget(btn_copia)
        btn_row.addStretch()
        btn_row.addWidget(btn_chiudi)
        lay.addLayout(btn_row)
        dlg.exec()

    def _duplica(self, nome: str, profilo: dict):
        import copy
        nuovo = f"{nome} (copia)"
        i = 2
        while nuovo in self._profili:
            nuovo = f"{nome} (copia {i})"
            i += 1
        self._profili[nuovo] = copy.deepcopy(profilo)
        config_manager.save_profiles(self._profili)
        self.aggiorna()

    def _copia_comando(self, nome: str, profilo: dict):
        from session_command import build_command
        cmd, _ = build_command(profilo)
        if cmd:
            QApplication.clipboard().setText(cmd)

    def _chiedi_elimina(self, nome: str):
        if QMessageBox.question(
            self, "Elimina sessione",
            f"Eliminare la sessione «{nome}»?"
        ) == QMessageBox.StandardButton.Yes:
            del self._profili[nome]
            config_manager.save_profiles(self._profili)
            self.sessione_eliminata.emit(nome)
            self.aggiorna()
