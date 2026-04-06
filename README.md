# PCM — Python Connection Manager 🚀

**PCM** è un Connection Manager avanzato per Linux, sviluppato in Python e PyQt6.
Nasce come alternativa open-source a MobaXterm, con un'interfaccia a schede unificata
per gestire connessioni remote multi-protocollo, trasferimenti file e terminali locali.

---

## ✨ Funzionalità

- **Multi-protocollo:** SSH, Telnet, SFTP, FTP/FTPS, RDP, VNC, Mosh, SSH Tunnel, Seriale
- **Terminale integrato:** `xterm` embedded nelle schede, con temi colore, font configurabili e scrollback
- **VNC integrato:** sessioni VNC in scheda tramite noVNC (opzionale), oppure client esterno
- **Browser SFTP grafico:** si apre in automatico per le sessioni SSH, con drag & drop
- **Browser FTP:** client FTP/FTPS integrato con interfaccia grafica tipo WinSCP
- **Pannello sessioni:** raggruppate per gruppo, ordinate per nome, con icone per protocollo e ricerca live
- **Import da app esterne:** importa connessioni da **Remmina** e **Remote Desktop Manager** (XML e JSON)
- **Modalità Split:** divide l'area di lavoro verticalmente o orizzontalmente (2 pannelli)
- **Quick Connect:** barra superiore per connessioni rapide (`utente@host:porta`)
- **Gestione Tunnel SSH:** tunnel SOCKS, locali e remoti con interfaccia grafica
- **Multi-exec:** invia lo stesso comando a più sessioni SSH contemporaneamente
- **Variabili globali:** sostituzioni `{NOME}` nei comandi delle sessioni
- **Server FTP locale:** avvia un server FTP sulla macchina locale
- **Modalità protetta:** nasconde le password dall'interfaccia (`****`)
- **System tray:** minimizza in background, sessioni accessibili dal tray
- **Tema chiaro** con icone PNG dedicate per ogni protocollo

---

## 🛠 Installazione

### Metodo rapido (consigliato)

```bash
git clone <repo>
cd PCM
bash setup.sh
./run_pcm.sh
```

`setup.sh` installa automaticamente tutte le dipendenze di sistema e Python,
crea il virtualenv con `uv` e crea il launcher.

### Manuale

**1. Dipendenze di sistema**

Debian/Ubuntu:
```bash
sudo apt install python3 xterm xdotool openssh-client sshpass \
                 xfreerdp2-x11 lftp libxcb-cursor0
```

Arch/Manjaro:
```bash
sudo pacman -S python xterm xdotool openssh sshpass freerdp lftp
```

Fedora/RHEL:
```bash
sudo dnf install python3 xterm xdotool openssh-clients sshpass freerdp lftp
```

**2. Virtualenv Python**

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**3. Icone**

Le icone PNG sono già incluse nella cartella `icons/` del repository,
incluso `checkmark.png` per i checkbox dell'interfaccia.

**3. Avvio**

```bash
./run_pcm.sh
# oppure
.venv/bin/python PCM.py
```

---

## 📁 Struttura file

```
PCM/
├── PCM.py                  # Finestra principale
├── config_manager.py       # Gestione sessioni e impostazioni (connections.json)
├── session_panel.py        # Sidebar sessioni
├── session_dialog.py       # Dialog creazione/modifica sessione
├── session_command.py      # Costruzione comandi shell per protocollo
├── themes.py               # Tema UI e temi terminale
├── terminal_widget.py      # Widget xterm embedded
├── sftp_browser.py         # Browser SFTP (paramiko)
├── winscp_widget.py        # Browser SFTP/FTP grafico
├── tunnel_manager.py       # Gestore tunnel SSH
├── settings_dialog.py      # Dialog impostazioni globali
├── importer.py             # Import da Remmina e Remote Desktop Manager
├── ftp_server_dialog.py    # Server FTP locale
├── vnc_widget.py           # Widget VNC integrato (noVNC)
├── connections.json        # Sessioni salvate (creato al primo avvio)
├── pcm_settings.json       # Impostazioni globali (creato al primo avvio)
├── requirements.txt        # Dipendenze Python
├── setup.sh                # Installer automatico
├── run_pcm.sh              # Launcher con virtualenv
└── icons/                  # Icone PNG (incluso checkmark.png)
```

---

## ⌨ Scorciatoie da tastiera

| Scorciatoia | Azione |
|---|---|
| `Ctrl+Shift+N` | Nuova sessione remota |
| `Ctrl+Alt+T` | Terminale locale |
| `Ctrl+Shift+B` | Mostra/Nascondi sidebar |
| `Ctrl+Shift+P` | Modalità protetta (toggle) |
| `Ctrl+Shift+M` | Multi-exec |
| `Ctrl+Shift+V` | Variabili globali |
| `Ctrl+Shift+F` | Server FTP locale |
| `Ctrl+Alt+1` | Vista singola |
| `Ctrl+Alt+2` | Split verticale |
| `Ctrl+Alt+3` | Split orizzontale |
| `Ctrl+Alt+Q` | Chiudi tab corrente |
| `Ctrl+Alt+←/→` | Tab precedente / successivo |
| `F11` | Schermo intero |

---

## 📥 Import connessioni

Da **Strumenti → Importa da applicazione esterna**:

- **Remmina** — legge automaticamente `~/.local/share/remmina/` o un file/cartella scelto
- **Remote Desktop Manager (XML)** — file `.rdm` esportato da RDM
- **Remote Desktop Manager (JSON)** — file `.json` esportato da RDM

Le password non vengono importate (sono cifrate nelle app sorgente).
I gruppi RDM vengono mantenuti come gruppi PCM.

---

## 🔧 Dipendenze Python

| Pacchetto | Uso |
|---|---|
| `PyQt6` | Interfaccia grafica |
| `PyQt6-WebEngine` | VNC integrato via noVNC (opzionale) |
| `paramiko` | SSH/SFTP nativo, browser SFTP |
| `pyftpdlib` | Server FTP locale |

---

## 💰 Donazioni

Se apprezzi questo progetto e vuoi supportare il suo sviluppo, considera una donazione via PayPal:

[![Donate](https://img.shields.io/badge/Donate-PayPal-blue.svg)](https://www.paypal.com/cgi-bin/webscr?cmd=_donations&business=azanzani@gmail.com&item_name=Support+PCM+Project)

---

Sviluppato con ♥ per la community Linux.
