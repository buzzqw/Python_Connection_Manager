# PCM — Python Connection Manager (GTK3)

Versione riscritta in **GTK3** con terminale **VTE** nativo.  
Funziona nativamente su **Wayland** senza XWayland.

## Dipendenze

```bash
# Debian/Ubuntu
sudo apt install \
    python3-gi \
    gir1.2-gtk-3.0 \
    gir1.2-vte-2.91 \
    gir1.2-webkit2-4.1 \
    python3-paramiko \
    xdotool

# FreeBSD
pkg install py311-gobject3 vte3 webkit2-gtk3 py311-paramiko xdotool

# Python packages
pip install cryptography
```

## Avvio

```bash
python3 PCM.py
```

## Caratteristiche

- Supporto protocolli: SSH, Telnet, SFTP, FTP, RDP, VNC, Mosh, Seriale
- Terminale embedded via **VTE** (nativo Wayland, no XWayland richiesto)
- Cifratura credenziali (Fernet/PBKDF2)
- Import sessioni da Remmina e Remote Desktop Manager
- Tunnel SSH, Wake-on-LAN, variabili globali, macro
- Server FTP locale (pyftpdlib)
- Viewer VNC esterno (vncviewer, tigervnc, remmina, krdc) o noVNC integrato
- Statistiche sessione live nella statusbar
- Internazionalizzazione (IT/EN/DE/FR/ES)

## Differenze rispetto alla versione PyQt6

| Funzionalità | PyQt6 | GTK3 |
|---|---|---|
| Framework UI | PyQt6 | GTK3 (PyGObject) |
| Terminale | xterm embedded | VTE nativo |
| Wayland | XWayland richiesto | Nativo |
| Dipendenze | python-pyqt6, xterm | python3-gi, gir1.2-vte |

## Note Wayland

La modalità RDP "pannello interno" richiede XWayland (usa xdotool).  
Per uso puro Wayland impostare RDP su "finestra esterna".
