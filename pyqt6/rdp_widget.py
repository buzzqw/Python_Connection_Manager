"""
rdp_widget.py - Widget RDP embedded per PCM (approccio xdotool reparent).

Strategia:
  1. Lancia xfreerdp3 come finestra normale (senza /parent-window)
  2. Polling con xdotool search finche' la finestra non appare
  3. Reparenta la finestra dentro il container Qt con xdotool windowreparent
  4. Ridimensiona per riempire il container

La ricerca della finestra usa piu' metodi in cascata:
  - xdotool search --pid <pid_principale>
  - pgrep per trovare eventuali processi figli di xfreerdp3
  - xdotool search --name <host> / FreeRDP / SISERVER
"""

import os
import re
import signal
import subprocess
import shutil
import time

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLineEdit, QLabel, QApplication
from PyQt6.QtCore import Qt, QTimer, pyqtSignal

from translations import t


def _freerdp_major_version(client: str) -> int:
    try:
        out = subprocess.check_output(
            [client, "--version"], stderr=subprocess.STDOUT,
            timeout=3, text=True
        )
        m = re.search(r'(\d+)\.\d+', out)
        if m:
            return int(m.group(1))
    except Exception:
        pass
    return 3 if "3" in client else 2


class RdpEmbedWidget(QWidget):

    processo_terminato = pyqtSignal()

    def __init__(self, profilo: dict, parent=None):
        super().__init__(parent)
        self._profilo    = profilo
        self._process    = None
        self._avviato    = False
        self._extra_env  = {}
        self._wid_rdp    = None
        self._reparented = False
        self._poll_attempts = 0
        self._t_avvio = None   # datetime avvio processo

        self._init_ui()

        self._keepalive_timer = QTimer(self)
        self._keepalive_timer.timeout.connect(self._controlla_processo)
        self._keepalive_timer.start(3000)

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _init_ui(self):
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)

        self.barra_info = QLineEdit()
        self.barra_info.setReadOnly(True)
        self.barra_info.setFixedHeight(22)
        self.barra_info.setStyleSheet(
            "background-color:#252525; color:#888; "
            "font-family:monospace; font-size:11px; "
            "border:none; border-bottom:1px solid #444; padding:0 6px;"
        )
        self._layout.addWidget(self.barra_info)

        self._lbl_attesa = QLabel(t("rdp.embed.waiting"))
        self._lbl_attesa.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lbl_attesa.setStyleSheet(
            "background:#1e1e1e; color:#888; font-size:12px;"
        )
        self._layout.addWidget(self._lbl_attesa, 1)

        # Container: WA_NativeWindow garantisce un WID X11 reale
        self.container = QWidget()
        self.container.setAttribute(Qt.WidgetAttribute.WA_NativeWindow, True)
        self.container.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.container.setStyleSheet("background:#000000;")
        self.container.setVisible(False)
        self._layout.addWidget(self.container, 1)

    # ------------------------------------------------------------------
    # Avvio
    # ------------------------------------------------------------------

    def showEvent(self, event):
        super().showEvent(event)
        if not self._avviato:
            self._avviato = True
            QTimer.singleShot(300, self._avvia_rdp)

    def _avvia_rdp(self):
        p = self._profilo

        # Wayland check
        wayland = (os.environ.get("WAYLAND_DISPLAY") or
                   os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland")
        display = os.environ.get("DISPLAY", "")
        if wayland and not display:
            self._mostra_errore(t("rdp.embed.wayland_no_xwayland"))
            return
        self._extra_env = {"DISPLAY": display} if wayland and display else {}

        client = p.get("rdp_client", "xfreerdp3")
        if not shutil.which(client):
            for alt in ("rdesktop", "xfreerdp3", "xfreerdp"):
                if shutil.which(alt):
                    client = alt
                    break
            else:
                self._mostra_errore(t("rdp.embed.client_missing", client=client))
                return

        self._client_name = client
        host   = p.get("host", "")
        port   = p.get("port", "3389")
        user   = p.get("user", "")
        pwd    = p.get("password", "")
        domain = p.get("rdp_domain", "").strip()
        clips  = p.get("redirect_clipboard", True)
        drives = p.get("redirect_drives", False)
        self._rdp_host = host

        # ── rdesktop: embedding nativo con -X <winid> ────────────────────
        # rdesktop supporta -X che aggancia la finestra direttamente al WID
        # del container Qt — nessun polling, nessun xdotool necessario.
        if client == "rdesktop":
            self._avvia_rdesktop(host, port, user, pwd, domain, clips, drives)
            return

        # ── xfreerdp3/xfreerdp: avvia + polling + xdotool reparent ───────
        if not shutil.which("xdotool"):
            self._mostra_errore(t("rdp.embed.reparent_failed"))
            return

        freerdp_ver = _freerdp_major_version(client)
        w_init = max(self.width(), 1024)
        h_init = max(self.height() - 22, 768)

        args = [client, f"/v:{host}:{port}", "/cert:ignore",
                f"/w:{w_init}", f"/h:{h_init}"]
        if freerdp_ver >= 3:
            args.append("/dynamic-resolution")
        if user:
            args.append(f"/u:{user}")
        if domain:
            args.append(f"/d:{domain}")
        if pwd:
            args.append(f"/p:{pwd}")
        if clips:
            args.append("/clipboard")
        if drives:
            args.append("/drive:home,/home")

        cmd_display = " ".join(a if not a.startswith("/p:") else "/p:****" for a in args)
        self.barra_info.setText(f"  ▶  {cmd_display}")

        env = dict(os.environ)
        env.update(self._extra_env)

        import tempfile as _tmp
        self._stderr_file = open(_tmp.gettempdir() + "/pcm_rdp_stderr.log", "w")
        try:
            self._process = subprocess.Popen(
                args, preexec_fn=os.setsid,
                stdout=subprocess.DEVNULL, stderr=self._stderr_file,
                env=env,
            )
            from datetime import datetime as _dt
            self._t_avvio = _dt.now()
            print(f"[RDP] Avviato {client} PID={self._process.pid}")
        except Exception as e:
            self._mostra_errore(str(e))
            return

        self._wid_esistenti = set()
        try:
            out = subprocess.check_output(
                ["xdotool", "search", "--name", "FreeRDP"],
                stderr=subprocess.DEVNULL, timeout=2, text=True
            ).strip()
            if out:
                self._wid_esistenti = set(out.split())
        except Exception:
            pass

        self._poll_attempts = 0
        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self._cerca_e_reparenta)
        self._poll_timer.start(500)

    # ------------------------------------------------------------------
    # rdesktop: embedding nativo con -X
    # ------------------------------------------------------------------

    def _avvia_rdesktop(self, host, port, user, pwd, domain, clips, drives=False):
        """
        Avvia rdesktop con -X <winid> per embedding diretto nel container Qt.
        Non richiede polling o xdotool: rdesktop si aggancia subito al WID.
        """
        # Assicura che il container abbia un WID X11 nativo
        self._lbl_attesa.setVisible(False)
        self.container.setVisible(True)
        self.container.winId()   # forza creazione WID
        QApplication.processEvents()

        wid_container = str(int(self.container.winId()))
        w = max(self.container.width(), 1024)
        h = max(self.container.height() - 22, 768)

        args = ["rdesktop",
                f"-X{wid_container}",   # embedding nel container Qt
                f"-g{w}x{h}",           # dimensioni
                "-a16",                  # 16-bit colore
                "-DNK",                  # no decorazioni, no grab kbd
                ]
        if user:
            args += [f"-u{user}"]
        if domain:
            args += [f"-d{domain}"]
        if pwd:
            args += [f"-p{pwd}"]
        if clips:
            args += ["-rclipboard:PRIMARYCLIPBOARD"]

        args.append(f"{host}:{port}")

        cmd_display = " ".join(
            a if not a.startswith("-p") else "-p****"
            for a in args
        )
        self.barra_info.setText(f"  ▶  {cmd_display}")

        env = dict(os.environ)
        env.update(self._extra_env)

        try:
            self._process = subprocess.Popen(
                args, preexec_fn=os.setsid,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                env=env,
            )
            from datetime import datetime as _dt
            self._t_avvio = _dt.now()
            print(f"[RDP] rdesktop avviato PID={self._process.pid} into WID={wid_container}")
            self._reparented = True
            self._wid_container = wid_container
            # Avvia un timer per trovare la finestra figlia di rdesktop nel container
            self._resize_timer = QTimer(self)
            self._resize_timer.setSingleShot(True)
            self._resize_timer.timeout.connect(self._trova_wid_rdesktop)
            self._resize_timer.start(2000)   # aspetta 2s che rdesktop si agganci
        except Exception as e:
            self._mostra_errore(str(e))

    def _trova_wid_rdesktop(self):
        """
        Trova il WID X11 della finestra rdesktop dentro il container Qt.
        rdesktop con -X crea una finestra figlia del container — la cerchiamo
        con xwininfo -children e la salviamo in _wid_rdp per il resize.
        """
        wid_container = getattr(self, "_wid_container", None)
        if not wid_container:
            return
        try:
            out = subprocess.check_output(
                ["xwininfo", "-id", wid_container, "-children"],
                stderr=subprocess.DEVNULL, timeout=3, text=True
            )
            # Cerca righe con WID figli: "   0x... ..."
            import re as _re
            figli = _re.findall(r"^\s+(0x[0-9a-fA-F]+)", out, _re.MULTILINE)
            if figli:
                # Converti hex in decimale
                self._wid_rdp = str(int(figli[0], 16))
                print(f"[RDP] WID rdesktop trovato: {self._wid_rdp}")
        except Exception as e:
            print(f"[RDP] _trova_wid_rdesktop: {e}")

    # ------------------------------------------------------------------
    # Polling + Reparenting
    # ------------------------------------------------------------------

    def _cerca_e_reparenta(self):
        self._poll_attempts += 1

        # Timeout 180s (360 × 500ms) — Kerberos timeout puo' durare 60-90s
        if self._poll_attempts > 360:
            self._poll_timer.stop()
            self._mostra_errore(t("rdp.embed.reparent_failed"))
            return

        if self._process and self._process.poll() is not None:
            if not getattr(self, "_processo_morto_al", None):
                self._processo_morto_al = self._poll_attempts
                print(f"[RDP] Processo morto al tentativo {self._poll_attempts}, continuo a cercare...")
            elif self._poll_attempts - self._processo_morto_al > 20:
                self._poll_timer.stop()
                return

        wid = self._trova_finestra()
        if not wid:
            # Aggiorna label con punto animato
            dots = "." * (self._poll_attempts % 4)
            sec = int(self._poll_attempts * 0.5)
            self._lbl_attesa.setText(f"{t('rdp.embed.waiting')}{dots}  ({sec}s)")
            return

        self._poll_timer.stop()
        self._wid_rdp = wid
        self._esegui_reparent(wid)

    def _xdotool_search(self, *args) -> str | None:
        """Wrapper xdotool search, restituisce primo WID o None."""
        try:
            out = subprocess.check_output(
                ["xdotool", "search"] + list(args),
                stderr=subprocess.DEVNULL, timeout=2, text=True
            ).strip()
            if out:
                return out.split("\n")[0].strip()
        except Exception:
            pass
        return None

    def _trova_finestra(self) -> str | None:
        """
        Cerca la finestra xfreerdp per nome.
        xdotool search --pid NON funziona con xfreerdp3 perche' la finestra
        X11 viene creata da un thread interno con PID diverso dal processo.
        La ricerca per nome e' l'unico metodo affidabile.

        xfreerdp3 mette il titolo nel formato: "FreeRDP: <host>"
        """
        host = getattr(self, "_rdp_host", "")

        # Ricerca per titolo esatto: "FreeRDP: <host>" (formato xfreerdp3)
        if host:
            wid = self._xdotool_search("--name", f"FreeRDP: {host}")
            if wid:
                return wid
            # Prova anche solo l'IP/hostname
            wid = self._xdotool_search("--name", host)
            if wid:
                return wid

        # Cerca tutte le finestre FreeRDP ed esclude quelle preesistenti
        try:
            out = subprocess.check_output(
                ["xdotool", "search", "--name", "FreeRDP"],
                stderr=subprocess.DEVNULL, timeout=2, text=True
            ).strip()
            if out:
                esistenti = getattr(self, "_wid_esistenti", set())
                for wid in out.split():
                    if wid not in esistenti:
                        return wid
        except Exception:
            pass

        return None

    def _esegui_reparent(self, wid_rdp: str):
        """Reparenta la finestra xfreerdp dentro il container Qt."""
        self._lbl_attesa.setVisible(False)
        self.container.setVisible(True)
        QApplication.processEvents()

        # Forza la creazione del WID X11 nativo del container
        self.container.winId()
        QApplication.processEvents()

        wid_container = str(int(self.container.winId()))
        w = max(self.container.width(), 800)
        h = max(self.container.height(), 600)

        try:
            # Nascondi prima del reparenting (evita flash)
            subprocess.run(["xdotool", "windowunmap", wid_rdp],
                           timeout=3, capture_output=True)
            time.sleep(0.15)

            # Reparenting
            result = subprocess.run(
                ["xdotool", "windowreparent", wid_rdp, wid_container],
                timeout=3, capture_output=True
            )
            if result.returncode != 0:
                raise RuntimeError(f"xdotool windowreparent fallito: {result.stderr.decode()}")

            # Posiziona in (0,0) e ridimensiona
            subprocess.run(["xdotool", "windowmove", "--sync", wid_rdp, "0", "0"],
                           timeout=3, capture_output=True)
            subprocess.run(["xdotool", "windowsize", "--sync", wid_rdp, str(w), str(h)],
                           timeout=3, capture_output=True)

            # Rimappa
            subprocess.run(["xdotool", "windowmap", "--sync", wid_rdp],
                           timeout=3, capture_output=True)

            self._reparented = True
            self.barra_info.setStyleSheet(
                "background-color:#252525; color:#88cc88; "
                "font-family:monospace; font-size:11px; "
                "border:none; border-bottom:1px solid #444; padding:0 6px;"
            )

        except Exception as e:
            print(f"[rdp_widget] reparent error: {e}")
            # Fallback: mostra messaggio ma lascia xfreerdp aperto esternamente
            self._mostra_errore(
                f"{t('rdp.embed.reparent_failed')} — la finestra RDP e' aperta esternamente"
            )

    # ------------------------------------------------------------------
    # Resize
    # ------------------------------------------------------------------

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if not self._reparented:
            return
        w = max(self.container.width(), 320)
        h = max(self.container.height(), 240)
        if self._wid_rdp:
            # Ridimensiona la finestra X11 (xfreerdp o rdesktop)
            subprocess.Popen(
                ["xdotool", "windowsize", self._wid_rdp, str(w), str(h)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )
        elif getattr(self, "_wid_container", None):
            # Fallback: ridimensiona tramite il container
            subprocess.Popen(
                ["xdotool", "windowsize", self._wid_container, str(w), str(h)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )

    # ------------------------------------------------------------------
    # Monitor processo
    # ------------------------------------------------------------------

    def _controlla_processo(self):
        if not self._process:
            return
        if self._process.poll() is not None:
            self._keepalive_timer.stop()
            if hasattr(self, "_poll_timer"):
                self._poll_timer.stop()

            # Determina se e' un fallimento rapido (< 15s) o disconnessione normale
            from datetime import datetime as _dt
            durata = (_dt.now() - self._t_avvio).total_seconds() if self._t_avvio else 99
            client = getattr(self, "_client_name", "")

            self.barra_info.setStyleSheet(
                "background-color:#4a1a1a; color:#ff6b6b; "
                "font-family:monospace; font-size:11px; "
                "border:none; border-bottom:1px solid #aa3333; padding:0 6px;"
            )

            if durata < 15 and not self._reparented:
                # Fallimento rapido prima ancora di connettersi — suggerisci alternativa
                if client == "rdesktop":
                    alt = "xfreerdp3" if shutil.which("xfreerdp3") else "xfreerdp"
                    msg = t("rdp.embed.failed_suggest", client=client, alt=alt)
                else:
                    alt = "rdesktop" if shutil.which("rdesktop") else ""
                    msg = t("rdp.embed.failed_suggest", client=client, alt=alt) if alt else t("rdp.embed.failed_noalt", client=client)
                self.barra_info.setText(msg)
                self._lbl_attesa.setText(f"⚠  {msg}")
                self._lbl_attesa.setStyleSheet("background:#1e1e1e; color:#ff6b6b; font-size:11px;")
                self._lbl_attesa.setWordWrap(True)
                self._lbl_attesa.setVisible(True)
                self.container.setVisible(False)
            else:
                self.barra_info.setText(t("terminal.session_ended"))

            self._process = None
            self.processo_terminato.emit()

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def chiudi_processo(self):
        if hasattr(self, "_keepalive_timer"):
            self._keepalive_timer.stop()
        if hasattr(self, "_poll_timer"):
            self._poll_timer.stop()
        if hasattr(self, "_resize_timer"):
            self._resize_timer.stop()
        if self._process:
            try:
                pgid = os.getpgid(self._process.pid)
                try:
                    os.killpg(pgid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                try:
                    self._process.wait(timeout=1.0)
                except subprocess.TimeoutExpired:
                    try:
                        os.killpg(pgid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
            except Exception as e:
                print(f"[rdp_widget] Errore chiusura: {e}")
            finally:
                self._process = None

    def closeEvent(self, event):
        self.chiudi_processo()
        super().closeEvent(event)

    # ------------------------------------------------------------------
    # Utility
    # ------------------------------------------------------------------

    def _mostra_errore(self, msg: str):
        self._lbl_attesa.setVisible(True)
        self.container.setVisible(False)
        self._lbl_attesa.setText(f"⚠  {msg}")
        self._lbl_attesa.setStyleSheet("background:#1e1e1e; color:#ff6b6b; font-size:12px;")
        self.barra_info.setStyleSheet(
            "background-color:#4a1a1a; color:#ff6b6b; "
            "font-family:monospace; font-size:11px; "
            "border:none; border-bottom:1px solid #aa3333; padding:0 6px;"
        )
        self.barra_info.setText(f"  ✖  {msg}")
