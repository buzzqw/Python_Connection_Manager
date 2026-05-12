"""
tunnel_manage-pyqt6.py - Gestore grafico di SSH Tunnel (port forwarding) per PCM.
Stile MobaSSHTunnel di MobaXterm: tabella dei tunnel, avvio/stop, persistenza.
"""

import os
import signal
import subprocess
import shutil

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QHeaderView, QMessageBox, QAbstractItemView,
    QWidget, QFormLayout, QLineEdit, QComboBox, QGroupBox, QDialogButtonBox
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QFont, QIcon

import config_manager
from translations import t


# ---------------------------------------------------------------------------
# Dialog per aggiungere/modificare un tunnel
# ---------------------------------------------------------------------------

class TunnelEditDialog(QDialog):

    TIPI = ["Proxy SOCKS (-D)", "Locale (-L)", "Remoto (-R)"]

    def __init__(self, parent=None, dati=None):
        super().__init__(parent)
        self.setWindowTitle(t("tunnel.edit_title"))
        self.setMinimumWidth(400)
        self.setModal(True)
        dati = dati or {}
        self._init_ui(dati)

    def _init_ui(self, d):
        layout = QVBoxLayout(self)

        form = QFormLayout()
        form.setSpacing(8)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.edit_nome = QLineEdit(d.get("nome", ""))
        self.edit_nome.setPlaceholderText("es. SOCKS proxy casa")
        form.addRow(t("tunnel.field_name"), self.edit_nome)

        self.combo_tipo = QComboBox()
        self.combo_tipo.addItems(self.TIPI)
        self.combo_tipo.setCurrentText(d.get("tipo", "Proxy SOCKS (-D)"))
        self.combo_tipo.currentTextChanged.connect(self._aggiorna_campi)
        form.addRow(t("tunnel.field_type"), self.combo_tipo)

        self.edit_ssh_host = QLineEdit(d.get("ssh_host", ""))
        self.edit_ssh_host.setPlaceholderText("host SSH")
        form.addRow(t("tunnel.field_host"), self.edit_ssh_host)

        self.edit_ssh_port = QLineEdit(str(d.get("ssh_port", "22")))
        self.edit_ssh_port.setMaximumWidth(70)
        form.addRow(t("tunnel.field_ssh_port"), self.edit_ssh_port)

        self.edit_ssh_user = QLineEdit(d.get("ssh_user", ""))
        form.addRow(t("tunnel.field_ssh_user"), self.edit_ssh_user)

        self.edit_ssh_pwd = QLineEdit(d.get("ssh_pwd", ""))
        self.edit_ssh_pwd.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow(t("tunnel.field_ssh_pwd"), self.edit_ssh_pwd)

        self.edit_lport = QLineEdit(str(d.get("local_port", "1080")))
        self.edit_lport.setMaximumWidth(70)
        form.addRow(t("tunnel.field_lport"), self.edit_lport)

        self.edit_rhost = QLineEdit(d.get("remote_host", ""))
        self.edit_rhost.setPlaceholderText("host destinazione (-L/-R)")
        form.addRow(t("tunnel.field_rhost"), self.edit_rhost)

        self.edit_rport = QLineEdit(str(d.get("remote_port", "")))
        self.edit_rport.setMaximumWidth(70)
        self.edit_rport.setPlaceholderText("porta dest.")
        form.addRow(t("tunnel.field_rport"), self.edit_rport)

        layout.addLayout(form)

        bbox = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        bbox.accepted.connect(self._valida)
        bbox.rejected.connect(self.reject)
        layout.addWidget(bbox)

        self._aggiorna_campi()

    def _aggiorna_campi(self):
        t = self.combo_tipo.currentText()
        remote_needed = t in ("Locale (-L)", "Remoto (-R)")
        self.edit_rhost.setEnabled(remote_needed)
        self.edit_rport.setEnabled(remote_needed)

    def _valida(self):
        if not self.edit_ssh_host.text().strip():
            self.edit_ssh_host.setFocus()
            return
        if not self.edit_nome.text().strip():
            nome = f"Tunnel {self.edit_ssh_host.text()}:{self.edit_lport.text()}"
            self.edit_nome.setText(nome)
        self.accept()

    def get_data(self) -> dict:
        return {
            "nome":        self.edit_nome.text().strip(),
            "tipo":        self.combo_tipo.currentText(),
            "ssh_host":    self.edit_ssh_host.text().strip(),
            "ssh_port":    self.edit_ssh_port.text().strip(),
            "ssh_user":    self.edit_ssh_user.text().strip(),
            "ssh_pwd":     self.edit_ssh_pwd.text(),
            "local_port":  self.edit_lport.text().strip(),
            "remote_host": self.edit_rhost.text().strip(),
            "remote_port": self.edit_rport.text().strip(),
            "pid":         None,
            "attivo":      False,
        }


# ---------------------------------------------------------------------------
# Finestra principale Tunnel Manager
# ---------------------------------------------------------------------------

class TunnelManagerDialog(QDialog):
    """
    Finestra di gestione tunnel SSH stile MobaSSHTunnel.
    Mostra una tabella con tutti i tunnel configurati e permette
    di avviarli/fermarli individualmente.
    I tunnel rimangono attivi anche dopo la chiusura della finestra;
    alla riapertura vengono riagganciati tramite il PID salvato in config.
    """

    COLONNE = [t("tunnel.col_name"), t("tunnel.col_type"), t("tunnel.col_host"), t("tunnel.col_lport"), t("tunnel.col_rhost"), t("tunnel.col_status")]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(t("tunnel.main_title_full"))
        self.setMinimumSize(720, 400)
        self._tunnels = config_manager.load_tunnels()
        self._processi = {}   # nome -> Popen (o proxy con solo .pid)

        self._init_ui()
        self._riaggancia_processi()
        self._aggiorna_tabella()

        # Timer di controllo stato
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._controlla_stati)
        self._timer.start(2000)

    # ------------------------------------------------------------------
    # Utilità PID
    # ------------------------------------------------------------------

    @staticmethod
    def _processo_vivo(pid: int) -> bool:
        """Controlla se un PID è ancora in esecuzione senza ucciderlo."""
        try:
            os.kill(pid, 0)
            return True
        except (ProcessLookupError, PermissionError):
            return False

    def _riaggancia_processi(self):
        """
        Alla riapertura della finestra, controlla quali tunnel hanno un PID
        salvato in config e, se il processo è ancora vivo, lo riaggancia nel
        dizionario _processi in modo da poterlo monitorare e fermare.
        """
        for t in self._tunnels:
            pid  = t.get("pid")
            nome = t.get("nome")
            if pid and nome and self._processo_vivo(pid):
                # Proxy leggero: non è un vero Popen ma ha .pid
                proxy = _PidProxy(pid)
                self._processi[nome] = proxy
                t["attivo"] = True
            else:
                t["attivo"] = False
                t["pid"]    = None

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # Intestazione
        hdr = QLabel(f"  {t('tunnel.toolbar_title')}")
        hdr.setStyleSheet("color:#6a9fd8; font-size:14px; font-weight:bold; padding:6px;")
        layout.addWidget(hdr)

        # Istruzioni integrate (collassabili con un pulsante)
        self._info_visible = False
        info_bar = QHBoxLayout()
        self._btn_info = QPushButton("ℹ  Come funziona?")
        self._btn_info.setCheckable(True)
        self._btn_info.setStyleSheet(
            "QPushButton { background:transparent; color:#4e7abc; border:1px solid #4e7abc; "
            "border-radius:3px; padding:2px 10px; font-size:11px; }"
            "QPushButton:checked { background:#4e7abc; color:#fff; }"
        )
        self._btn_info.toggled.connect(self._toggle_info)
        info_bar.addWidget(self._btn_info)
        info_bar.addStretch()
        layout.addLayout(info_bar)

        self._info_box = QLabel(
            "<b>• SOCKS (-D):</b> Crea un proxy locale. Configura il browser su "
            "<tt>localhost:&lt;porta locale&gt;</tt> (SOCKS5) per navigare attraverso il server SSH.<br>"
            "<b>• Locale (-L):</b> Rende accessibile in locale un servizio remoto. "
            "Es: <tt>-L 5433:db-interno:5432</tt> → puoi usare <tt>localhost:5433</tt> "
            "per raggiungere il database dietro il firewall.<br>"
            "<b>• Remoto (-R):</b> Espone un servizio locale sul server remoto. "
            "Es: <tt>-R 8080:localhost:8080</tt> → il server remoto vede il tuo <tt>localhost:8080</tt>.<br><br>"
            "<b>Doppio clic</b> su una riga per avviare/fermare il tunnel. "
            "I tunnel restano attivi anche dopo aver chiuso questa finestra."
        )
        self._info_box.setWordWrap(True)
        self._info_box.setStyleSheet(
            "background:#eef3fa; border:1px solid #b8cfe8; border-radius:4px; "
            "padding:10px; font-size:11px; color:#333; margin-bottom:4px;"
        )
        self._info_box.setVisible(False)
        layout.addWidget(self._info_box)

        # Tabella
        self.tabella = QTableWidget(0, len(self.COLONNE))
        self.tabella.setHorizontalHeaderLabels(self.COLONNE)
        self.tabella.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tabella.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.tabella.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.tabella.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.tabella.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.tabella.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.tabella.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tabella.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tabella.setAlternatingRowColors(True)
        self.tabella.verticalHeader().setVisible(False)
        self.tabella.doubleClicked.connect(self._toggle_selezionato)
        layout.addWidget(self.tabella, 1)

        # Pulsanti azione
        btn_layout = QHBoxLayout()

        self.btn_aggiungi = QPushButton(t("tunnel.btn_add"))
        self.btn_aggiungi.clicked.connect(self._aggiungi_tunnel)

        self.btn_modifica = QPushButton(t("tunnel.btn_edit"))
        self.btn_modifica.clicked.connect(self._modifica_tunnel)

        self.btn_elimina = QPushButton(t("tunnel.btn_delete"))
        self.btn_elimina.clicked.connect(self._elimina_tunnel)

        self.btn_avvia = QPushButton(t("tunnel.btn_start"))
        self.btn_avvia.clicked.connect(self._avvia_selezionato)
        self.btn_avvia.setStyleSheet("background:#2d7a2d;")

        self.btn_ferma = QPushButton(t("tunnel.btn_stop"))
        self.btn_ferma.clicked.connect(self._ferma_selezionato)
        self.btn_ferma.setStyleSheet("background:#7a2d2d;")

        self.btn_avvia_tutti = QPushButton(t("tunnel.btn_start_all"))
        self.btn_avvia_tutti.clicked.connect(self._avvia_tutti)

        self.btn_ferma_tutti = QPushButton(t("tunnel.btn_stop_all"))
        self.btn_ferma_tutti.clicked.connect(self._ferma_tutti)

        for b in [self.btn_aggiungi, self.btn_modifica, self.btn_elimina,
                  self.btn_avvia, self.btn_ferma,
                  self.btn_avvia_tutti, self.btn_ferma_tutti]:
            btn_layout.addWidget(b)

        layout.addLayout(btn_layout)

        # Chiudi
        close_btn = QPushButton(t("tunnel.btn_close"))
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn, alignment=Qt.AlignmentFlag.AlignRight)

    def _toggle_info(self, visible: bool):
        self._info_box.setVisible(visible)

    # ------------------------------------------------------------------
    # Tabella
    # ------------------------------------------------------------------

    def _aggiorna_tabella(self):
        self.tabella.setRowCount(0)
        for tun in self._tunnels:
            r = self.tabella.rowCount()
            self.tabella.insertRow(r)

            attivo = tun.get("attivo", False)
            stato_txt = "● " + t("tunnel.status_active") if attivo else "○ " + t("tunnel.status_idle")

            bg_row = QColor("#2a2a2a") if r % 2 == 0 else QColor("#242424")
            fg_row = QColor("#dddddd")

            celle = [
                tun.get("nome", ""),
                tun.get("tipo", ""),
                f"{tun.get('ssh_user', '')}@{tun.get('ssh_host', '')}:{tun.get('ssh_port', 22)}",
                str(tun.get("local_port", "")),
                f"{tun.get('remote_host', '')}:{tun.get('remote_port', '')}" if tun.get("remote_host") else "—",
                stato_txt,
            ]
            for c, testo in enumerate(celle):
                item = QTableWidgetItem(testo)
                item.setBackground(bg_row)
                item.setForeground(fg_row)
                if c == len(celle) - 1:
                    item.setForeground(QColor("#44dd66") if attivo else QColor("#888888"))
                    font = item.font()
                    font.setBold(attivo)
                    item.setFont(font)
                self.tabella.setItem(r, c, item)

    # ------------------------------------------------------------------
    # CRUD tunnel
    # ------------------------------------------------------------------

    def _aggiungi_tunnel(self):
        dlg = TunnelEditDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._tunnels.append(dlg.get_data())
            self._salva()
            self._aggiorna_tabella()

    def _modifica_tunnel(self):
        row = self.tabella.currentRow()
        if row < 0 or row >= len(self._tunnels):
            return
        tun = self._tunnels[row]
        if tun.get("attivo"):
            QMessageBox.warning(self, t("tunnel.warn_active"), t("tunnel.warn_stop_first"))
            return
        dlg = TunnelEditDialog(self, dati=tun)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._tunnels[row] = dlg.get_data()
            self._salva()
            self._aggiorna_tabella()

    def _elimina_tunnel(self):
        row = self.tabella.currentRow()
        if row < 0 or row >= len(self._tunnels):
            return
        t = self._tunnels[row]
        if t.get("attivo"):
            self._ferma_tunnel(row)
        if QMessageBox.question(self, "Elimina", f"Eliminare il tunnel '{t['nome']}'?") \
                == QMessageBox.StandardButton.Yes:
            self._tunnels.pop(row)
            self._salva()
            self._aggiorna_tabella()

    # ------------------------------------------------------------------
    # Avvio / Stop
    # ------------------------------------------------------------------

    def _build_ssh_cmd(self, t: dict) -> list:
        host  = t.get("ssh_host", "")
        port  = str(t.get("ssh_port", "22"))
        user  = t.get("ssh_user", "")
        tipo  = t.get("tipo", "Proxy SOCKS (-D)")
        lport = str(t.get("local_port", "1080"))
        rhost = t.get("remote_host", "")
        rport = str(t.get("remote_port", ""))

        target = f"{user}@{host}" if user else host

        cmd = ["ssh", "-N",
               "-p", port,
               "-o", "StrictHostKeyChecking=accept-new",
               "-o", "ExitOnForwardFailure=yes"]

        if tipo == "Proxy SOCKS (-D)":
            cmd += ["-D", lport]
        elif tipo == "Locale (-L)":
            cmd += ["-L", f"{lport}:{rhost}:{rport}"]
        elif tipo == "Remoto (-R)":
            cmd += ["-R", f"{lport}:{rhost}:{rport}"]

        cmd.append(target)
        return cmd

    def _avvia_tunnel(self, idx: int):
        t = self._tunnels[idx]
        if t.get("attivo"):
            return
        cmd = self._build_ssh_cmd(t)
        pwd = t.get("ssh_pwd", "")
        env = None
        if pwd and shutil.which("sshpass"):
            env = {**os.environ, "SSHPASS": pwd}
            cmd = ["sshpass", "-e"] + cmd
        try:
            proc = subprocess.Popen(
                cmd, preexec_fn=os.setsid,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                env=env,
            )
            nome = t["nome"]
            self._processi[nome] = proc
            self._tunnels[idx]["attivo"] = True
            self._tunnels[idx]["pid"]    = proc.pid
            self._salva()
            self._aggiorna_tabella()
        except Exception as e:
            QMessageBox.critical(self, "Errore avvio tunnel", str(e))

    def _ferma_tunnel(self, idx: int):
        t    = self._tunnels[idx]
        nome = t.get("nome")
        proc = self._processi.get(nome)
        if proc:
            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
            except Exception:
                pass
            del self._processi[nome]
        self._tunnels[idx]["attivo"] = False
        self._tunnels[idx]["pid"]    = None
        self._salva()
        self._aggiorna_tabella()

    def _avvia_selezionato(self):
        row = self.tabella.currentRow()
        if 0 <= row < len(self._tunnels):
            self._avvia_tunnel(row)

    def _ferma_selezionato(self):
        row = self.tabella.currentRow()
        if 0 <= row < len(self._tunnels):
            self._ferma_tunnel(row)

    def _toggle_selezionato(self):
        row = self.tabella.currentRow()
        if 0 <= row < len(self._tunnels):
            if self._tunnels[row].get("attivo"):
                self._ferma_tunnel(row)
            else:
                self._avvia_tunnel(row)

    def _avvia_tutti(self):
        for i in range(len(self._tunnels)):
            if not self._tunnels[i].get("attivo"):
                self._avvia_tunnel(i)

    def _ferma_tutti(self):
        for i in range(len(self._tunnels)):
            if self._tunnels[i].get("attivo"):
                self._ferma_tunnel(i)

    def _controlla_stati(self):
        """
        Controlla se i processi dei tunnel sono ancora in esecuzione
        usando os.kill(pid, 0) — funziona anche sui proxy riagganciati.
        """
        aggiornato = False
        for i, t in enumerate(self._tunnels):
            nome = t.get("nome")
            proc = self._processi.get(nome)
            if proc:
                pid  = t.get("pid") or proc.pid
                vivo = self._processo_vivo(pid) if pid else False
                if not vivo:
                    self._tunnels[i]["attivo"] = False
                    self._tunnels[i]["pid"]    = None
                    del self._processi[nome]
                    aggiornato = True
        if aggiornato:
            self._salva()
            self._aggiorna_tabella()

    # ------------------------------------------------------------------
    # Persistenza
    # ------------------------------------------------------------------

    def _salva(self):
        config_manager.save_tunnels(self._tunnels)

    def closeEvent(self, event):
        """
        Chiusura della finestra: ferma il timer ma lascia i processi SSH attivi.
        I PID sono già salvati in config; alla prossima apertura verranno
        riagganciati da _riaggancia_processi().
        """
        self._timer.stop()
        self._salva()
        super().closeEvent(event)

    def ferma_tutti_alla_chiusura(self):
        """Chiama questo alla chiusura dell'app principale se vuoi
        terminare tutti i tunnel attivi."""
        self._ferma_tutti()


# ---------------------------------------------------------------------------
# Proxy leggero per i processi riagganciati (non creati da questo Popen)
# ---------------------------------------------------------------------------

class _PidProxy:
    """
    Sostituisce un oggetto Popen per i processi SSH già in esecuzione
    rilevati al riavvio della dialog. Espone solo .pid, usato da
    os.killpg e _processo_vivo.
    """
    __slots__ = ("pid",)

    def __init__(self, pid: int):
        self.pid = pid
