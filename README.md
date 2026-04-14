# PCM — Python Connection Manager

Gestore grafico di connessioni remote per Linux, ispirato a MobaXterm.

Disponibile in due versioni:

| Versione | Cartella | Framework | Terminale | Wayland |
|---|---|---|---|---|
| Originale | [`pyqt6/`](./pyqt6/) | PyQt6 | xterm | XWayland |
| Riscritta | [`gtk3/`](./gtk3/) | GTK3 | VTE | Nativo ✓ |

## Protocolli supportati

SSH · Telnet · SFTP · FTP/FTPS · RDP · VNC · Mosh · Seriale

## Funzionalità comuni

- Sessioni organizzate per gruppo con ricerca
- Cifratura credenziali (Fernet + PBKDF2-SHA256, 480k iterazioni)
- Import da Remmina e Remote Desktop Manager
- Tunnel SSH gestiti graficamente
- Wake-on-LAN, variabili globali, macro per sessione
- Server FTP locale integrato
- Temi terminale (Dracula, Nord, Gruvbox, Solarized…)
- Internazionalizzazione: Italiano, English, Deutsch, Français, Español

## Autore

Andres Zanzani — licenza AGPL-3.0
