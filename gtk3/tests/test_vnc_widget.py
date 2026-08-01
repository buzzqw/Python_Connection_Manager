import os

import vnc_widget


class TestVncSocketPasswordFile:
    """_write_passwd_file usava un semplice XOR byte a byte, non il DES a
    chiave fissa richiesto dal formato -passwd/--PasswordFile: il client
    VNC (vncviewer/xtigervncviewer/...) non riusciva mai a leggerlo e
    ignorava silenziosamente la password salvata, chiedendola sempre a
    schermo. La funzione ora delega a session_command._vnc_obfuscate_password."""

    def test_returns_none_without_vncpasswd(self, monkeypatch):
        monkeypatch.setattr(vnc_widget.shutil, "which", lambda tool: None)
        assert vnc_widget._VncSocket._write_passwd_file("secret") is None

    def test_writes_obfuscated_bytes_not_xor(self, monkeypatch):
        import session_command
        monkeypatch.setattr(session_command, "_vnc_obfuscate_password",
                             lambda pwd: b"\xaa\xbb\xcc\xdd\xee\xff\x11\x22")
        path = vnc_widget._VncSocket._write_passwd_file("secret")
        assert path is not None
        try:
            with open(path, "rb") as f:
                content = f.read()
            assert content == b"\xaa\xbb\xcc\xdd\xee\xff\x11\x22"
            # La vecchia implementazione XOR-ava la password con la chiave
            # fissa: verifichiamo che non produciamo più quel formato.
            key = [23, 82, 107, 6, 35, 78, 88, 7]
            old_xor = bytes(b ^ key[i] for i, b in
                             enumerate(b"secret\x00\x00"))
            assert content != old_xor
        finally:
            os.unlink(path)
