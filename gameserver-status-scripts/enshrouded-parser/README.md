# Player Log Parser für Enshrouded

Dieses Projekt enthält eine Sammlung von Python-Skripten, um die Logdateien von Gameservern live auszulesen. Die Skripte extrahieren die aktuellen Spielerdaten (Name, Rolle, etc.) und speichern sie in einer JSON-Datei. Diese JSON-Datei kann dann von einer separaten Web-API bereitgestellt werden, um sie auf einer Webseite anzuzeigen.

Hier ist das **Parser-Skript für Enshrouded**, das als verallgemeinerte Vorlage dient.

## Features

- **Live-Parsing:** Überwacht die Log-Dateien in Echtzeit, ohne die Dateien ständig neu einlesen zu müssen.
- **Konfigurierbar:** Alle wichtigen Einstellungen werden über eine separate `config.ini`-Datei gesteuert.
- **Flexibler Betriebsmodus:** Unterstützt sowohl nativ laufende Server (direkter Logfile-Zugriff) als auch Server, die in einem Docker-Container laufen.
- **Robust:** Läuft als `systemd`-Dienst, startet automatisch mit dem Server und wird bei Fehlern neu gestartet.
- **Effizient:** Geringer Ressourcenverbrauch, optimiert für den Dauerbetrieb auf einem Gameserver.
- **Professionelles Logging:** Schreibt eigene, saubere Log-Dateien zur einfachen Fehlersuche.

---

## Installation und Einrichtung

Diese Anleitung beschreibt die Einrichtung des Enshrouded-Parsers. Der Prozess ist für den Valheim-Parser analog.

### Schritt 1: Vorbereitung (Benutzer und Verzeichnisse)

Es wird dringend empfohlen, für jeden Dienst einen eigenen, unprivilegierten Benutzer zu erstellen.

1.  **Benutzer erstellen** (falls noch nicht geschehen):
    ```bash
    sudo adduser enshrouded --disabled-password
    ```

2.  **Verzeichnis für die Skripte erstellen:**
    ```bash
    sudo mkdir -p /home/enshrouded/scripts
    sudo chown -R enshrouded:enshrouded /home/enshrouded/scripts
    ```

### Schritt 2: Skript-Dateien kopieren

Kopieren Sie die folgenden Dateien aus diesem Repository in das erstellte Verzeichnis:

- `enshrouded_log_parser.py`
- `config.ini.example`

Nach dem Kopieren sollten die Dateien hier liegen:
- `/home/enshrouded/scripts/enshrouded_log_parser.py`
- `/home/enshrouded/scripts/config.ini.example`

### Schritt 3: Python Virtual Environment (venv) einrichten

Wir isolieren die Python-Abhängigkeiten in einer virtuellen Umgebung, um Konflikte zu vermeiden.

1.  **Abhängigkeiten installieren** (benötigt, falls nicht auf dem System vorhanden):
    ```bash
    # Für Debian/Ubuntu
    sudo apt-get update
    sudo apt-get install python3-venv python3-pip -y
    ```

2.  **Zum Benutzer wechseln:** (falls nicht bereits geschehen)
    ```bash
    sudo -i -u enshrouded
    ```
    
3.  **Virtuelle Umgebung erstellen** (im Skript-Verzeichnis):
    ```bash
    cd /home/enshrouded/scripts
    python3 -m venv venv
    ```

4.  **Verlassen Sie die Benutzersitzung wieder:** (wenn enshrouded nicht Teil der sudo-Gruppe ist)
    ```bash
    exit
    ```

### Schritt 4: Konfiguration anpassen (`config.ini`)

Die Beispiel-Konfiguration muss nun in die aktive Konfiguration kopiert und angepasst werden.

1.  **Beispieldatei kopieren:**
    ```bash
    sudo cp /home/enshrouded/scripts/config.ini.example /home/enshrouded/scripts/config.ini
    ```

2.  **`config.ini` bearbeiten:**
    Öffnen Sie die Datei mit einem Editor (z.B. `sudo nano /home/enshrouded/scripts/config.ini`) und passen Sie die Werte an Ihre Umgebung an. Entfernen Sie die Platzhalter `<...>` vollständig.

    - **`[main]` Sektion:**
        - `mode`: Wählen Sie `native` oder `docker`.
        - `output_json_path`: Normalerweise ist `/tmp/enshrouded_players.json` eine gute Wahl.
        - `log_file_path`: `/var/log/enshrouded-player.log` ist der Standard.

    - **`[native]` Sektion (wenn `mode = native`):**
        - `log_path`: Setzen Sie den korrekten Pfad zu Ihrer `enshrouded_server.log`-Datei.

    - **`[docker]` Sektion (wenn `mode = docker`):**
        - `container_name`: Geben Sie den exakten Namen oder die ID Ihres Enshrouded-Docker-Containers an.

### Schritt 5: Systemd Service einrichten

Damit das Skript als Dienst im Hintergrund läuft, erstellen wir eine `systemd`-Service-Unit.

1.  **Service-Datei erstellen:**
    Kopieren Sie zuerst die Vorlage an den richtigen Ort:
    ```bash
    sudo cp enshrouded-log-parser.service.example /etc/systemd/system/enshrouded-log-parser.service
    ```

2.  **Service-Datei anpassen:**
    Öffnen Sie die neue Datei (`sudo nano /etc/systemd/system/enshrouded-log-parser.service`) und ersetzen Sie die Platzhalter `<PFAD ZUR SCRIPT UND PYTHON UMGEBUNG>` durch den korrekten Pfad. In unserem Beispiel ist dies `/home/enshrouded/scripts`.

    Die fertigen Zeilen sollten so aussehen:
    ```ini
    ExecStart=/home/enshrouded/scripts/venv/bin/python3 /home/enshrouded/scripts/enshrouded_log_parser.py
    WorkingDirectory=/home/enshrouded/scripts
    ```

---

## Betrieb

Nach der Einrichtung können Sie den Dienst starten und verwalten.

### 1. Berechtigungen für die Log-Datei des Parsers setzen

Das Skript benötigt Schreibrechte für seine eigene Log-Datei.

```bash
sudo touch /var/log/enshrouded-player.log
sudo chown enshrouded:enshrouded /var/log/enshrouded-player.log

2. Dienst starten und aktivieren
Systemd neu laden, um die neue Service-Datei zu erkennen:

sudo systemctl daemon-reload

Dienst starten:

sudo systemctl start enshrouded-log-parser.service

Dienst für den automatischen Start aktivieren:

sudo systemctl enable enshrouded-log-parser.service

3. Status und Logs prüfen
Status des Dienstes prüfen:

sudo systemctl status enshrouded-log-parser.service

Der Status sollte active (running) sein.

Live-Logs des Dienstes ansehen:
Um zu sehen, was das Skript tut (oder welche Fehler es gibt), verwenden Sie journalctl:

sudo journalctl -u enshrouded-log-parser.service -f

API-Endpunkt
Wenn das Skript läuft, erstellt und aktualisiert es kontinuierlich die JSON-Datei (z.B. /tmp/enshrouded_players.json). Sie können nun eine Web-API (z.B. mit Flask/Gunicorn, wie im separaten Projekt beschrieben) erstellen, die den Inhalt dieser Datei ausliest und über einen HTTP-Endpunkt zur Verfügung stellt.

HTTP GET -> /api/enshrouded  =>  Liest /tmp/enshrouded_players.json aus und gibt den Inhalt zurück.
