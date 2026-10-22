# PCM — Python Connection Manager (GTK3)

Questa è l'unica variante attiva di PCM. La documentazione generale,
gli screenshot e le istruzioni di installazione sono nel
**[README principale](../README.md)**.

## Avvio rapido

```bash
python3 PCM.py
```

Oppure, dalla root del repository:

```bash
bash setup.sh
cd gtk3 && python3 PCM.py
```

## Funzionalità specifiche

- Sessioni SSH, SFTP, FTP/FTPS, RDP, VNC, Telnet, Mosh, seriale ed Exec.
- Plugin built-in per AWS SSM, kubectl exec, Docker exec e SPICE.
- Gruppi annidati usando `/`, ad esempio `Produzione/Linux`.
- Template concatenabili con ereditarietà e rilevamento dei cicli.
- External tools configurabili con placeholder, eseguiti senza shell.
- Port scan TCP limitato con importazione selettiva dei profili.
- Backup rotazionali configurabili di `connections.json` e `pcm_settings.json`.
- Terminale VTE nativo con split, ricerca regex, cronologia comandi, menu contestuale completo, modalità sola lettura e bracketed paste.
- Monitor latenza SSH nella statusbar (RTT reale via canale SFTP o probe TCP).
- Drag & drop: file locali sul terminale per upload nella cwd remota, file remoti dal pannello SFTP al terminale per inserire il percorso.
- Indicatori di attività sui tab, notifiche desktop al campanello, titolo remoto (OSC 0/2) nel tooltip.
- Directory corrente remota via OSC 7: copia percorso, apertura nel pannello SFTP, Ctrl+clic su percorsi per editor/file manager.
- Browser SFTP dual-pane, monitoraggio risorse e tunnel SSH.

## Documentazione

- [README completo](../README.md)
- [Manuale `pcm(1)`](pcm.1.md)
- [Guida HTML](pcm_help_en.html), disponibile anche dal menu **Aiuto > Guida di PCM**

## Configurazione

In un checkout sorgente scrivibile, `connections.json` e `pcm_settings.json`
sono nella directory `gtk3/`. Con AppImage o installazioni in sola lettura
sono in `${XDG_CONFIG_HOME:-~/.config}/pcm/`. I log terminale sono normalmente
in `~/.local/share/pcm/logs/`.
