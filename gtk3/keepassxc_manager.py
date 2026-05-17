"""
keepassxc_manager.py - Integrazione KeePassXC Browser Protocol v2 per PCM

Trasporto: keepassxc-proxy (stdin/stdout, native messaging format)
Protocollo: KeePassXC-Browser v2 (NaCl box — Curve25519 + XSalsa20-Poly1305)
Dipendenza: pynacl (pip install pynacl)

Flusso:
  1. change-public-keys  — scambio chiavi (plaintext)
  2. associate           — prima volta: approvare in KeePassXC
  3. test-associate      — verificare associazione salvata
  4. get-logins          — recupera credenziali
"""

import json
import os
import select
import shutil
import struct
import subprocess
import base64
import secrets
import threading
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib

from translations import t

try:
    import nacl.public
    import nacl.utils
    _HAS_NACL = True
except ImportError:
    _HAS_NACL = False

_ASSOC_KEY = "keepassxc_assoc"


def _find_proxy() -> str | None:
    return shutil.which("keepassxc-proxy")


def _find_socket() -> str | None:
    uid = os.getuid()
    for p in [
        f"/run/user/{uid}/org.keepassxc.KeePassXC.BrowserServer",
        "/tmp/org.keepassxc.KeePassXC.BrowserServer",
    ]:
        if os.path.exists(p):
            return p
    return None


def _load_assoc() -> dict:
    try:
        import config_manager
        return config_manager.load_settings().get(_ASSOC_KEY, {})
    except Exception:
        return {}


def _save_assoc(assoc: dict):
    try:
        import config_manager
        s = config_manager.load_settings()
        s[_ASSOC_KEY] = assoc
        config_manager.save_settings(s)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Client KeePassXC Browser Protocol v2
# ---------------------------------------------------------------------------

class KeePassXCClient:
    """
    Client KeePassXC Browser Protocol v2.
    Usa keepassxc-proxy (stdin/stdout) come trasporto — più affidabile del socket diretto.
    """

    def __init__(self):
        self._proc: subprocess.Popen | None = None
        self._box  = None
        self._client_id = base64.b64encode(secrets.token_bytes(24)).decode()
        if _HAS_NACL:
            self._priv = nacl.public.PrivateKey.generate()
            self._pub  = self._priv.public_key
        else:
            self._priv = self._pub = None

    # ── Trasporto ────────────────────────────────────────────────────────

    def _ensure_proc(self):
        if self._proc and self._proc.poll() is None:
            return
        proxy = _find_proxy()
        if not proxy:
            raise ConnectionError(t("keepass.not_running") + " (keepassxc-proxy non trovato)")
        self._proc = subprocess.Popen(
            [proxy],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )

    def _send_raw(self, msg: dict, timeout: float = 5.0) -> dict:
        self._ensure_proc()
        data  = json.dumps(msg).encode()
        frame = struct.pack("<I", len(data)) + data
        self._proc.stdin.write(frame)
        self._proc.stdin.flush()

        ready = select.select([self._proc.stdout], [], [], timeout)
        if not ready[0]:
            raise ConnectionError(f"Timeout ({timeout:.0f}s) da keepassxc-proxy — database aperto?")
        raw_len = self._proc.stdout.read(4)
        if len(raw_len) < 4:
            raise ConnectionError("Risposta troncata da keepassxc-proxy")
        length  = struct.unpack("<I", raw_len)[0]
        payload = self._proc.stdout.read(length)
        return json.loads(payload)

    # ── NaCl box ─────────────────────────────────────────────────────────

    def _send_encrypted(self, body: dict, timeout: float = 5.0) -> dict:
        nonce = nacl.utils.random(24)
        enc   = self._box.encrypt(json.dumps(body).encode(), nonce)
        resp  = self._send_raw({
            "action":   body["action"],
            "message":  base64.b64encode(enc.ciphertext).decode(),
            "nonce":    base64.b64encode(nonce).decode(),
            "clientID": self._client_id,
        }, timeout=timeout)
        msg_b64   = resp.get("message")
        nonce_b64 = resp.get("nonce")
        if not msg_b64 or not nonce_b64:
            return resp
        decrypted = self._box.decrypt(
            base64.b64decode(msg_b64),
            base64.b64decode(nonce_b64),
        )
        return json.loads(decrypted)

    # ── Handshake ─────────────────────────────────────────────────────────

    def exchange_keys(self) -> bool:
        if not _HAS_NACL:
            return False
        nonce = base64.b64encode(nacl.utils.random(24)).decode()
        resp  = self._send_raw({
            "action":    "change-public-keys",
            "publicKey": base64.b64encode(bytes(self._pub)).decode(),
            "nonce":     nonce,
            "clientID":  self._client_id,
        })
        if resp.get("success") != "true":
            return False
        srv_key_b64 = resp.get("publicKey")
        if not srv_key_b64:
            return False
        srv_pub   = nacl.public.PublicKey(base64.b64decode(srv_key_b64))
        self._box = nacl.public.Box(self._priv, srv_pub)
        return True

    def associate(self) -> dict | None:
        """Prima associazione — l'utente deve approvare in KeePassXC (timeout 30s)."""
        id_key = nacl.utils.random(32)
        try:
            resp = self._send_encrypted({
                "action": "associate",
                "key":    base64.b64encode(bytes(self._pub)).decode(),
                "idKey":  base64.b64encode(id_key).decode(),
            }, timeout=30.0)
        except Exception:
            return None
        if resp.get("success") != "true":
            return None
        assoc = {
            "id":    resp.get("id", ""),
            "idKey": base64.b64encode(id_key).decode(),
        }
        _save_assoc(assoc)
        return assoc

    def test_associate(self, assoc: dict) -> bool:
        try:
            resp = self._send_encrypted({
                "action": "test-associate",
                "id":     assoc.get("id", ""),
                "key":    assoc.get("idKey", ""),
            })
            return resp.get("success") == "true"
        except Exception:
            return False

    # ── API pubblica ──────────────────────────────────────────────────────

    def get_logins(self, url: str, on_associate=None) -> list[dict]:
        """
        Cerca credenziali per l'URL dato.
        on_associate(): callback opzionale prima di avviare l'associazione.
        """
        if not _HAS_NACL:
            raise ConnectionError("PyNaCl non installato — pip install pynacl")
        if "://" not in url:
            url = f"ssh://{url}"

        if not self._box and not self.exchange_keys():
            raise ConnectionError(t("keepass.not_running"))

        assoc = _load_assoc()
        keys: list[dict] = []
        if assoc and self.test_associate(assoc):
            keys = [{"id": assoc["id"], "key": assoc["idKey"]}]
        else:
            if on_associate:
                on_associate()
            assoc = self.associate()
            if assoc:
                keys = [{"id": assoc["id"], "key": assoc["idKey"]}]

        try:
            resp = self._send_encrypted({
                "action":    "get-logins",
                "url":       url,
                "submitUrl": url,
                "httpAuth":  False,
                "keys":      keys,
            })
        except Exception as e:
            raise ConnectionError(str(e))

        if resp.get("error"):
            return []
        return [
            {
                "title":    e.get("name", ""),
                "username": e.get("login", ""),
                "password": e.get("password", ""),
                "url":      e.get("url", ""),
                "uuid":     e.get("uuid", ""),
            }
            for e in resp.get("entries", [])
        ]

    def close(self):
        if self._proc:
            try:
                self._proc.stdin.close()
                self._proc.terminate()
                self._proc.wait(timeout=2)
            except Exception:
                pass
            self._proc = None


# ---------------------------------------------------------------------------
# Dialog ricerca credenziali
# ---------------------------------------------------------------------------

class KeePassXCDialog(Gtk.Dialog):
    """
    Dialog che cerca credenziali in KeePassXC e permette di sceglierle.
    Restituisce (username, password) via get_credentials().
    """

    def __init__(self, parent=None, query: str = ""):
        super().__init__(
            title=t("keepass.title"),
            transient_for=parent,
            modal=True,
            destroy_with_parent=True,
        )
        self.set_default_size(540, 360)
        self._results: list[dict] = []
        self._last_query: str = query
        self._client  = KeePassXCClient()
        self._init_ui(query)

    def _init_ui(self, query: str):
        area = self.get_content_area()
        area.set_spacing(8)
        area.set_margin_start(16); area.set_margin_end(16)
        area.set_margin_top(12);  area.set_margin_bottom(8)

        search_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self._entry_search = Gtk.SearchEntry()
        self._entry_search.set_placeholder_text(t("keepass.search_ph"))
        self._entry_search.set_text(query)
        self._entry_search.set_hexpand(True)
        btn_search = Gtk.Button(label=t("keepass.search_btn"))
        btn_search.get_style_context().add_class("suggested-action")
        btn_search.connect("clicked", lambda _: self._do_search())
        self._entry_search.connect("activate", lambda _: self._do_search())
        search_row.pack_start(self._entry_search, True, True, 0)
        search_row.pack_start(btn_search, False, False, 0)
        area.pack_start(search_row, False, False, 0)

        lbl_hint = Gtk.Label()
        lbl_hint.set_markup(f"<small><i>{t('keepass.url_hint')}</i></small>")
        lbl_hint.set_xalign(0.0)
        lbl_hint.set_line_wrap(True)
        area.pack_start(lbl_hint, False, False, 0)

        self._lbl_status = Gtk.Label(label="")
        self._lbl_status.set_xalign(0.0)
        self._lbl_status.set_line_wrap(True)
        area.pack_start(self._lbl_status, False, False, 0)

        self._store = Gtk.ListStore(str, str, str, str)  # title, username, url, uuid
        self._tv = Gtk.TreeView(model=self._store)
        for i, col in enumerate([t("keepass.col_title"), t("keepass.col_user"), t("keepass.col_url")]):
            cell = Gtk.CellRendererText()
            cell.set_property("ellipsize", 3)
            c = Gtk.TreeViewColumn(col, cell, text=i)
            c.set_resizable(True)
            self._tv.append_column(c)
        self._tv.connect("row-activated", lambda *_: self.response(Gtk.ResponseType.OK))

        sw = Gtk.ScrolledWindow()
        sw.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        sw.add(self._tv)
        area.pack_start(sw, True, True, 0)

        btn_use = self.add_button(t("keepass.use"), Gtk.ResponseType.OK)
        btn_use.get_style_context().add_class("suggested-action")
        self.add_button(t("dialog.cancel"), Gtk.ResponseType.CANCEL)

        self.show_all()
        if query:
            GLib.idle_add(self._do_search)

    def _do_search(self, *_):
        query = self._entry_search.get_text().strip()
        if not query:
            return False
        self._store.clear()
        self._last_query = query
        self._lbl_status.set_text(t("ping.testing"))

        def _run():
            def _on_associate():
                GLib.idle_add(lambda: self._lbl_status.set_markup(
                    f"<span foreground='orange'>{t('keepass.approve_assoc')}</span>"
                ))
            try:
                results = self._client.get_logins(query, on_associate=_on_associate)
                GLib.idle_add(self._apply_results, results)
            except Exception as e:
                msg = str(e)
                GLib.idle_add(lambda: self._lbl_status.set_markup(
                    f"<span foreground='red'>{msg}</span>"
                ))

        threading.Thread(target=_run, daemon=True).start()
        return False

    def _apply_results(self, results: list[dict]):
        self._results = results
        if not results:
            # Mostra l'URL cercato così l'utente sa cosa inserire in KeePassXC
            query = getattr(self, "_last_query", "")
            bare = query.split("://")[-1].split("/")[0]  # estrae solo l'host
            msg = t("keepass.no_results", url=bare)
            self._lbl_status.set_markup(f"<span foreground='orange'>{msg}</span>")
            return
        for r in results:
            self._store.append([r["title"], r["username"], r["url"], r["uuid"]])
        self._lbl_status.set_markup(
            f"<span foreground='green'>{t('keepass.found', n=len(results))}</span>"
        )

    def get_credentials(self) -> tuple[str, str]:
        sel = self._tv.get_selection()
        model, it = sel.get_selected()
        if it is None:
            if self._store.get_iter_first() is not None:
                it = self._store.get_iter_first()
            else:
                return "", ""
        uuid = model.get_value(it, 3)
        user = model.get_value(it, 1)
        pwd  = next((r["password"] for r in self._results if r["uuid"] == uuid), "")
        return user, pwd

    def do_destroy(self):
        self._client.close()
        Gtk.Dialog.do_destroy(self)


# ---------------------------------------------------------------------------
# Dialog impostazioni KeePassXC
# ---------------------------------------------------------------------------

class KeePassXCSettingsDialog(Gtk.Dialog):
    """
    Dialog impostazioni integrazione KeePassXC.
    """

    def __init__(self, parent=None):
        super().__init__(
            title=t("keepass.title"),
            transient_for=parent,
            modal=True,
            destroy_with_parent=True,
        )
        self.set_default_size(480, 0)
        area = self.get_content_area()
        area.set_spacing(10)
        area.set_margin_start(16); area.set_margin_end(16)
        area.set_margin_top(12);  area.set_margin_bottom(8)

        lbl_title = Gtk.Label()
        lbl_title.set_markup(f"<b>{t('keepass.title')}</b>")
        lbl_title.set_xalign(0.0)
        area.pack_start(lbl_title, False, False, 0)

        proxy = _find_proxy() or t("keepass.socket_not_found")
        lbl_proxy = Gtk.Label(label=f"Proxy: {proxy}")
        lbl_proxy.set_xalign(0.0)
        lbl_proxy.set_selectable(True)
        area.pack_start(lbl_proxy, False, False, 0)

        sock = _find_socket() or "—"
        lbl_sock = Gtk.Label(label=f"Socket: {sock}")
        lbl_sock.set_xalign(0.0)
        area.pack_start(lbl_sock, False, False, 0)

        lbl_status = Gtk.Label(label=t("ping.testing"))
        lbl_status.set_xalign(0.0)
        area.pack_start(lbl_status, False, False, 0)

        assoc = _load_assoc()
        assoc_txt = assoc.get("id") or t("keepass.no_assoc")
        lbl_assoc = Gtk.Label(label=f"Associazione: {assoc_txt}")
        lbl_assoc.set_xalign(0.0)
        area.pack_start(lbl_assoc, False, False, 0)

        if not _HAS_NACL:
            lbl_status.set_markup(
                "<span foreground='orange'>⚠ PyNaCl non installato — pip install pynacl</span>"
            )
        else:
            lbl_info = Gtk.Label()
            lbl_info.set_markup(
                "<small>Per utilizzare KeePassXC con PCM:\n"
                "1. Apri KeePassXC → Strumenti → Impostazioni → Browser Integration\n"
                "2. Abilita l'integrazione e sblocca il database\n"
                "3. PCM usa keepassxc-proxy per comunicare con KeePassXC</small>"
            )
            lbl_info.set_xalign(0.0)
            lbl_info.set_line_wrap(True)
            area.pack_start(lbl_info, False, False, 0)

        self.add_button(t("dialog.close"), Gtk.ResponseType.CLOSE)
        self.show_all()

        if _HAS_NACL:
            def _test_conn():
                try:
                    client = KeePassXCClient()
                    if client.exchange_keys():
                        client.close()
                        GLib.idle_add(lambda: lbl_status.set_markup(
                            f"<span foreground='green'>✔ {t('keepass.connected')}</span>"
                        ))
                    else:
                        GLib.idle_add(lambda: lbl_status.set_markup(
                            f"<span foreground='orange'>⚠ {t('keepass.not_running')}</span>"
                        ))
                except Exception as e:
                    msg = str(e)
                    GLib.idle_add(lambda: lbl_status.set_markup(
                        f"<span foreground='orange'>⚠ {t('keepass.error', e=msg)}</span>"
                    ))

            threading.Thread(target=_test_conn, daemon=True).start()
