# PCM — Python Connection Manager (PyQt6)

Versione originale basata su **PyQt6** + **xterm** embedded.

## Dipendenze

```bash
# Arch Linux
sudo pacman -S python-pyqt6 xterm xdotool xclip

# Debian/Ubuntu
sudo apt install python3-pyqt6 xterm xdotool xclip

# Python packages
pip install cryptography paramiko
```

## Avvio

```bash
python PCM.py
```

## Caratteristiche

- Supporto protocolli: SSH, Telnet, SFTP, FTP, RDP, VNC, Mosh, Seriale
- Terminale embedded via xterm (richiede X11 / XWayland)
- Cifratura credenziali (Fernet/PBKDF2)
- Import sessioni da Remmina e Remote Desktop Manager
- Tunnel SSH, Wake-on-LAN, variabili globali, macro
- Server FTP locale (pyftpdlib)
- Tema UI chiaro/scuro, internazionalizzazione (IT/EN/DE/FR/ES)

## Note

Questa versione richiede X11 o XWayland per il terminale embedded.
Per uso nativo su Wayland, vedi la versione GTK3 nella cartella `../gtk3/`.
