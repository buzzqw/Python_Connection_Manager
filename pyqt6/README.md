# PCM — Python Connection Manager (PyQt6)

> Versione originale basata su **PyQt6** con terminale **xterm** embedded.
> Per nuove installazioni è raccomandata la versione [GTK3](../gtk3/README.md).

---

## Dipendenze

### Arch Linux
```bash
sudo pacman -S python-pyqt6 xterm xdotool xclip
pip install --user cryptography paramiko pyftpdlib
```

### Debian / Ubuntu
```bash
sudo apt install python3-pyqt6 xterm xdotool xclip
pip install --user cryptography paramiko pyftpdlib
```

### Fedora
```bash
sudo dnf install python3-pyqt6 xterm xdotool xclip
pip install --user cryptography paramiko pyftpdlib
```

---

## Avvio

```bash
cd pyqt6/
python3 PCM.py
```

---

## Caratteristiche

- Protocolli: SSH, Telnet, SFTP, FTP/FTPS, RDP, VNC, SSH Tunnel, Mosh, Seriale
- Terminale embedded via **xterm** (richiede X11 / XWayland)
- Cifratura credenziali AES-256 (Fernet + PBKDF2-SHA256, 480k iterazioni)
- Import sessioni da Remmina e Remote Desktop Manager
- Tunnel SSH, Wake-on-LAN, variabili globali, macro
- Server FTP locale (pyftpdlib)
- Browser SFTP/FTP dual-pane integrato (stile WinSCP)
- Split terminale verticale/orizzontale
- Multi-exec e macro per sessione
- Tema UI chiaro/scuro, temi terminale (Dracula, Nord, Gruvbox, Solarized…)
- Internazionalizzazione: Italiano · English · Deutsch · Français · Español

---

## Differenze rispetto alla versione GTK3

| Funzionalità | PyQt6 (questa) | GTK3 |
|---|---|---|
| Framework UI | PyQt6 | GTK3 (PyGObject) |
| Terminale | xterm embedded | VTE nativo |
| Wayland | XWayland richiesto | ✅ Nativo |
| VNC integrato | noVNC/WebKit | ✅ gtk-vnc nativo |
| Dipendenze Python | python-pyqt6, python-xlib | python3-gi |

---

## Note

Questa versione richiede X11 o XWayland per il terminale xterm embedded.
Per uso nativo su Wayland usare la versione GTK3 nella cartella [`../gtk3/`](../gtk3/).

---

## Autore

**Andres Zanzani** — licenza [EUPL-1.2](../EUPL-1.2%20EN.txt) / AGPL-3.0

[GitHub](https://github.com/buzzqw/Python_Connection_Manager)
