# PCM — Python Connection Manager

> Gestore grafico di connessioni remote per Linux, ispirato a MobaXterm.
> Scritto in Python, disponibile in due versioni: **PyQt6** e **GTK3**.

---

![PCM Main Window](immagini/pcm1.png)
*Schermata principale — sidebar sessioni, quick connect, terminale VTE integrato*

---

## Versioni disponibili

| Versione | Cartella | Framework | Terminale | Wayland |
|---|---|---|---|---|
| Originale | [`pyqt6/`](./pyqt6/) | PyQt6 | xterm | XWayland richiesto |
| GTK3 | [`gtk3/`](./gtk3/) | GTK3 (PyGObject) | VTE nativo | ✅ Nativo |

La versione **GTK3** è quella attivamente sviluppata e raccomandata per nuove installazioni.

---

## Protocolli supportati

**SSH · SFTP · FTP/FTPS · RDP · VNC · Telnet · Mosh · Seriale · SSH Tunnel**

---

## Funzionalità principali

- 🖥 **Sessioni organizzate per gruppo** con ricerca istantanea
- ⚡ **Quick Connect** dalla toolbar — `utente@host:porta`
- 🔐 **Cifratura credenziali** AES-256 (PBKDF2-SHA256, 480k iterazioni)
- 📂 **Browser FTP/SFTP** dual-pane stile WinSCP con coda trasferimenti
- 🔀 **Tunnel SSH** gestiti graficamente (SOCKS, locale, remoto)
- 💻 **Split terminale** verticale/orizzontale — più sessioni in parallelo
- ⚡ **Macro per sessione** e **Multi-exec** su più server contemporaneamente
- 🌐 **Wake-on-LAN** integrato prima della connessione
- 📥 **Import** da Remmina e Remote Desktop Manager
- 🔑 **Gestione chiavi SSH**: genera, copia, mostra pubblica
- 🖧 **Server FTP locale** integrato (pyftpdlib)
- 🌍 **5 lingue**: Italiano · English · Deutsch · Français · Español

---

## Screenshot

| | |
|---|---|
| ![SSH](immagini/pcm2.png) | ![Auth](immagini/pcm3.png) |
| *Configurazione sessione SSH con Wake-on-LAN* | *Autenticazione SSH e gestione chiavi* |
| ![Terminal](immagini/pcm4.png) | ![Advanced](immagini/pcm5.png) |
| *Opzioni terminale, pre-cmd VPN, log* | *Opzioni avanzate SSH, modalità apertura* |
| ![RDP](immagini/pcm6.png) | ![FTP Browser](immagini/pcm10.png) |
| *Configurazione RDP* | *Browser FTP dual-pane integrato* |

---

## Installazione rapida (GTK3)

```bash
git clone https://github.com/buzzqw/Python_Connection_Manager.git
cd Python_Connection_Manager/gtk3
bash setup.sh          # installa automaticamente per Debian/Ubuntu/Arch/Fedora/openSUSE
python3 PCM.py
```

Per la versione PyQt6 e le istruzioni complete vedi [`pyqt6/README.md`](./pyqt6/README.md).

---

## Supporta il progetto

Se PCM ti è utile e vuoi ringraziare lo sviluppatore per il suo lavoro, puoi offrire un caffè tramite PayPal. Ogni contributo, piccolo o grande, è molto apprezzato e aiuta a mantenere il progetto attivo e in continuo miglioramento!

> ☕ [**Dona via PayPal** → azanzani@gmail.com](https://www.paypal.com/paypalme/azanzani)

*Grazie mille!* 🙏

---

## Autore

**Andres Zanzani** — licenza [EUPL-1.2](EUPL-1.2%20EN.txt)

[![GitHub](https://img.shields.io/badge/GitHub-buzzqw%2FPython__Connection__Manager-blue?logo=github)](https://github.com/buzzqw/Python_Connection_Manager)

---
---

# PCM — Python Connection Manager 🇬🇧

> Graphical remote connection manager for Linux, inspired by MobaXterm.
> Written in Python, available in two versions: **PyQt6** and **GTK3**.

---

![PCM Main Window](immagini/pcm1.png)
*Main window — session sidebar, quick connect, integrated VTE terminal*

---

## Available versions

| Version | Folder | Framework | Terminal | Wayland |
|---|---|---|---|---|
| Original | [`pyqt6/`](./pyqt6/) | PyQt6 | xterm | XWayland required |
| GTK3 | [`gtk3/`](./gtk3/) | GTK3 (PyGObject) | Native VTE | ✅ Native |

The **GTK3** version is the actively developed one and is recommended for new installations.

---

## Supported protocols

**SSH · SFTP · FTP/FTPS · RDP · VNC · Telnet · Mosh · Serial · SSH Tunnel**

---

## Key features

- 🖥 **Sessions organized by group** with instant search
- ⚡ **Quick Connect** from toolbar — `user@host:port`
- 🔐 **Credential encryption** AES-256 (PBKDF2-SHA256, 480k iterations)
- 📂 **FTP/SFTP dual-pane browser** WinSCP-style with transfer queue
- 🔀 **SSH Tunnels** managed graphically (SOCKS, local, remote)
- 💻 **Split terminal** vertical/horizontal — multiple sessions in parallel
- ⚡ **Per-session macros** and **Multi-exec** on multiple servers simultaneously
- 🌐 **Wake-on-LAN** integrated before connection
- 📥 **Import** from Remmina and Remote Desktop Manager
- 🔑 **SSH key management**: generate, copy, show public key
- 🖧 **Integrated local FTP server** (pyftpdlib)
- 🌍 **5 languages**: Italiano · English · Deutsch · Français · Español

---

## Screenshots

| | |
|---|---|
| ![SSH](immagini/pcm2.png) | ![Auth](immagini/pcm3.png) |
| *SSH session configuration with Wake-on-LAN* | *SSH authentication and key management* |
| ![Terminal](immagini/pcm4.png) | ![Advanced](immagini/pcm5.png) |
| *Terminal options, VPN pre-cmd, logging* | *Advanced SSH options, open mode* |
| ![RDP](immagini/pcm6.png) | ![FTP Browser](immagini/pcm10.png) |
| *RDP configuration* | *Integrated dual-pane FTP browser* |

---

## Quick install (GTK3)

```bash
git clone https://github.com/buzzqw/Python_Connection_Manager.git
cd Python_Connection_Manager/gtk3
bash setup.sh          # automatically installs for Debian/Ubuntu/Arch/Fedora/openSUSE
python3 PCM.py
```

For the PyQt6 version and full instructions see [`pyqt6/README.md`](./pyqt6/README.md).

---

## Support the project

If you find PCM useful and want to thank the developer for his work, you can buy him a coffee via PayPal. Any contribution, big or small, is greatly appreciated and helps keep the project alive and actively developed!

> ☕ [**Donate via PayPal** → azanzani@gmail.com](https://www.paypal.com/paypalme/azanzani)

*Thank you so much!* 🙏

---

## Author

**Andres Zanzani** — license [EUPL-1.2](EUPL-1.2%20EN.txt)

[![GitHub](https://img.shields.io/badge/GitHub-buzzqw%2FPython__Connection__Manager-blue?logo=github)](https://github.com/buzzqw/Python_Connection_Manager)
