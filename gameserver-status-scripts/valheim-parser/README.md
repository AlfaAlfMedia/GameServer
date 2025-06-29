# Player Log Parser für Valheim

Dieses Projekt enthält ein Python-Skript, um die Logdateien eines Valheim-Servers live auszulesen. Das Skript extrahiert die aktuellen Spielerdaten (Name, Rolle, SteamID) und speichert sie in einer JSON-Datei. Diese JSON-Datei kann dann von einer separaten Web-API bereitgestellt werden, um sie auf einer Webseite anzuzeigen.

## Features

-   **Live-Parsing:** Überwacht die Log-Dateien in Echtzeit.
-   **Konfigurierbar:** Alle wichtigen Einstellungen werden über eine separate `config.ini`-Datei gesteuert.
-   **Flexibler Betriebsmodus:** Unterstützt sowohl nativ laufende Server (direkter Logfile-Zugriff) als auch Server, die in einem Docker-Container laufen.
-   **Dynamische Admin-Liste:** Lädt Änderungen an der `adminlist.txt` automatisch im laufenden Betrieb neu.
-   **Robust:** Läuft als `systemd`-Dienst, startet automatisch mit dem Server und wird bei Fehlern neu gestartet.
-   **Professionelles Logging:** Schreibt eigene, saubere Log-Dateien zur einfachen Fehlersuche.

---

## Einrichtung

Die folgenden Schritte beschreiben die vollständige Einrichtung des Valheim-Parsers auf einem neuen Server.

### Schritt 1: Vorbereitung (Benutzer und Verzeichnisse)

Es wird dringend empfohlen, für den Dienst einen eigenen, unprivilegierten Benutzer zu erstellen.

1.  **Benutzer erstellen** (falls noch nicht geschehen):
    ```bash
    sudo adduser valheim --disabled-password
    ```

2.  **Benutzer zur Docker-Gruppe hinzufügen** (erforderlich für den Docker-Modus):
    ```bash
    sudo usermod -aG docker valheim
    ```

3.  **Verzeichnis für die Skripte erstellen:**
    ```bash
    sudo mkdir -p /home/valheim/scripts
    sudo chown -R valheim:valheim /home/valheim/scripts
    ```

### Schritt 2: Dateien und Konfiguration

1.  Kopieren Sie `valheim_log_parser.py` und `config.ini.example` aus dem `valheim_parser`-Verzeichnis dieses Repositories nach `/home/valheim/scripts/`.

2.  Kopieren Sie die Beispiel-Konfiguration, um sie zu bearbeiten:
    ```bash
    sudo cp /home/valheim/scripts/config.ini.example /home/valheim/scripts/config.ini
    ```

3.  **`config.ini` bearbeiten:**
    Öffnen Sie die Datei mit einem Editor (z.B. `sudo nano /home/valheim/scripts/config.ini`) und passen Sie alle Werte an Ihre Umgebung an. Entfernen Sie die Platzhalter `<...>` vollständig.
    -   `mode`: Wählen Sie `native` oder `docker`.
    -   `admin_list_path`: Geben Sie den korrekten Pfad zu Ihrer `adminlist.txt` an.
    -   `log_path` (für native): Setzen Sie den Pfad zur Valheim-Logdatei. Oft muss diese erst durch eine Anpassung am Start-Skript erzeugt werden (z.B. `>> /pfad/zum/log.txt`).
    -   `container_name` (für docker): Geben Sie den exakten Namen oder die ID Ihres Valheim-Docker-Containers an.

### Schritt 3: Python Virtual Environment (venv)

Wir isolieren die Python-Abhängigkeiten, um Konflikte zu vermeiden.

1.  **System-Pakete installieren:**
    ```bash
    sudo apt-get update && sudo apt-get install python3-venv python3-pip -y
    ```
2.  **Zum Benutzer wechseln:**
    ```bash
    sudo -i -u valheim
    ```
3.  **Venv erstellen:**
    ```bash
    cd /home/valheim/scripts && python3 -m venv venv
    ```
4.  **Sitzung verlassen:**
    ```bash
    exit
    ```

### Schritt 4: Systemd Service einrichten

1.  **Service-Datei kopieren:**
    ```bash
    sudo cp systemd_services/valheim-log-parser.service.example /etc/systemd/system/valheim-log-parser.service
    ```
2.  **Service-Datei anpassen:**
    Öffnen Sie die neue Datei (`sudo nano /etc/systemd/system/valheim-log-parser.service`) und ersetzen Sie die Platzhalter `<...>` mit dem korrekten Pfad `/home/valheim/scripts` und dem Benutzernamen `valheim`.

    Die fertigen Zeilen sollten so aussehen:
    ```ini
    ExecStart=/home/valheim/scripts/venv/bin/python3 /home/valheim/scripts/valheim_log_parser.py
    WorkingDirectory=/home/valheim/scripts
    User=valheim
    Group=docker
    ```

---

## Betrieb des Dienstes

### 1. Log-Datei des Parsers erstellen

Erstellen und berechtigen Sie die Log-Datei, die Sie in Ihrer `config.ini` unter `log_file_path` definiert haben.

```bash
sudo touch /var/log/valheim-player.log
sudo chown valheim:valheim /var/log/valheim-player.log
```

### 2. Dienst verwalten

-   **Systemd neu laden:** `sudo systemctl daemon-reload`
-   **Dienst starten:** `sudo systemctl start valheim-log-parser.service`
-   **Dienst für den automatischen Start aktivieren:** `sudo systemctl enable valheim-log-parser.service`
-   **Status prüfen:** `sudo systemctl status valheim-log-parser.service`
-   **Live-Logs ansehen:** `sudo journalctl -u valheim-log-parser.service -f`
