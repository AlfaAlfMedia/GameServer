# Modulare Game-Server Status API

Dieses Projekt stellt eine flexible, modulare Web-API bereit, die mit Flask und Gunicorn betrieben wird. Sie dient dazu, Spielerdaten aus verschiedenen JSON-Dateien (die von separaten Parser-Skripten erstellt werden) über eine saubere, erweiterbare HTTP-Schnittstelle zur Verfügung zu stellen.

Das System ist so konzipiert, dass neue Spiele oder mehrere Serverinstanzen desselben Spiels einfach durch Hinzufügen von Konfigurationen und Modulen unterstützt werden können, ohne den Kern der Anwendung zu verändern.

## Features

-   **Modulare Architektur:** Jedes Spiel oder jede Serverinstanz wird als eigenständiges "Plugin" (Modul) behandelt.
-   **Zentralisierte Konfiguration:** Alle aktivierten Instanzen und deren Parameter werden über eine einzige `config.ini`-Datei gesteuert.
-   **Dynamische URL-Endpunkte:** Die API-Pfade werden dynamisch aus der Konfiguration generiert (z.B. `/api/valheim-public/players`).
-   **Erweiterbarkeit:** Neue Spiele können hinzugefügt werden, ohne die Hauptanwendung `app.py` zu ändern.
-   **Robust:** Ausgelegt für den Betrieb als `systemd`-Dienst mit Gunicorn für Stabilität und Leistung.

## Projektstruktur

Die API erwartet die folgende Verzeichnisstruktur. Legen Sie diese auf Ihrem Web-API-Server an und ersetzen Sie `<api-benutzer>` durch Ihren gewählten Benutzernamen.

```
/home/<api-benutzer>/flask_api/
├── app.py                  # Das zentrale Herzstück der Anwendung
├── config.ini              # Die Steuerzentrale für alle Module
│
├── modules/
│   ├── __init__.py         # Leere Datei, wichtig für Python
│   ├── enshrouded_api.py   # Modul für Enshrouded-Instanzen
│   └── valheim_api.py      # Modul für Valheim-Instanzen
│
├── requirements.txt        # Python-Abhängigkeiten
└── venv/                     # Das Verzeichnis der virtuellen Umgebung
```

## Installation und Einrichtung

### Schritt 1: Vorbereitung (Benutzer und Verzeichnisse)

1.  **Benutzer erstellen** (falls noch nicht geschehen). Wählen Sie einen passenden Namen, z.B. `api-runner`:
    ```bash
    sudo adduser <api-benutzer> --disabled-password
    ```

2.  **Verzeichnisstruktur anlegen:**
    ```bash
    sudo mkdir -p /home/<api-benutzer>/flask_api/modules
    sudo chown -R <api-benutzer>:<api-benutzer> /home/<api-benutzer>/flask_api
    ```

### Schritt 2: Dateien kopieren

Kopieren Sie die Dateien aus diesem Repository an die entsprechenden Stellen in der oben gezeigten Struktur.

### Schritt 3: Python Virtual Environment (venv) einrichten

1.  **System-Pakete installieren:**
    ```bash
    sudo apt-get update && sudo apt-get install python3-venv python3-pip -y
    ```

2.  **Zum Benutzer wechseln:**
    ```bash
    sudo -i -u <api-benutzer>
    ```

3.  **Venv erstellen:**
    ```bash
    cd /home/<api-benutzer>/flask_api
    python3 -m venv venv
    ```

4.  **Abhängigkeiten installieren:**
    ```bash
    source venv/bin/activate
    pip install -r requirements.txt
    deactivate
    ```

5.  **Sitzung verlassen:**
    ```bash
    exit
    ```

### Schritt 4: Konfiguration anpassen (`config.ini`)

Bearbeiten Sie die `config.ini`-Datei (`sudo nano /home/<api-benutzer>/flask_api/config.ini`), um Ihre Serverinstanzen zu definieren.

-   **`[main]` Sektion:**
    -   `enabled_instances`: Fügen Sie hier die Namen der Sektionen ein, die Sie aktivieren möchten (z.B. `enshrouded-public,valheim-community`).

-   **Pro Instanz eine Sektion erstellen (z.B. `[enshrouded-public]`):**
    -   `module`: Der Name des zugehörigen Python-Moduls ohne `_api.py` (z.B. `enshrouded`).
    -   `api_endpoint`: Der einzigartige Name für die URL (z.B. `enshrouded-public`).
    -   `json_path`: Der vollständige Pfad zur JSON-Datei, die von dem entsprechenden Parser-Skript erstellt wird.

### Schritt 5: Systemd Service für Gunicorn einrichten

1.  **Service-Datei erstellen:**
    ```bash
    sudo nano /etc/systemd/system/gunicorn-games-api.service
    ```

2.  **Inhalt einfügen und anpassen:**
    Ersetzen Sie alle Platzhalter `<api-benutzer>` mit dem von Ihnen gewählten Benutzernamen.

    ```ini
    [Unit]
    Description=Gunicorn instance to serve Game Server API
    After=network.target

    [Service]
    User=<api-benutzer>
    Group=<api-benutzer>
    WorkingDirectory=/home/<api-benutzer>/flask_api
    ExecStart=/home/<api-benutzer>/flask_api/venv/bin/gunicorn --workers 3 --bind 0.0.0.0:8080 app:app
    Restart=always

    [Install]
    WantedBy=multi-user.target
    ```

## Firewall-Konfiguration (UFW)

Um die API abzusichern, sodass nur Ihr Webserver darauf zugreifen kann, verwenden Sie die folgende `ufw`-Regel.

**Ersetzen Sie `<IP-DES-WEBSERVERS>` mit der tatsächlichen IP-Adresse des Servers, der die Anfragen an die API stellt.**

```bash
# Erlaube eingehende Verbindungen auf Port 8080 NUR von der spezifischen IP des Webservers
sudo ufw allow from <IP-DES-WEBSERVERS> to any port 8080 proto tcp

# UFW aktivieren (falls noch nicht geschehen)
sudo ufw enable

# Status der Firewall prüfen
sudo ufw status
```

Die Ausgabe sollte Ihre neue Regel anzeigen.

## Betrieb des Dienstes

-   **Systemd neu laden:** `sudo systemctl daemon-reload`
-   **API-Dienst starten:** `sudo systemctl start gunicorn-games-api.service`
-   **Dienst für den Autostart aktivieren:** `sudo systemctl enable gunicorn-games-api.service`
-   **Status prüfen:** `sudo systemctl status gunicorn-games-api.service`
-   **Live-Logs ansehen:** `sudo journalctl -u gunicorn-games-api.service -f`

## Eine neue Spiel-Instanz hinzufügen

1.  **Parser einrichten:** Stellen Sie sicher, dass ein Parser-Skript für die neue Instanz läuft und eine einzigartige JSON-Datei erstellt.
2.  **API-Modul erstellen:** Falls es ein neues Spiel ist, erstellen Sie eine neue `..._api.py`-Datei im `modules`-Ordner.
3.  **`config.ini` erweitern:**
    -   Erstellen Sie eine neue Sektion, z.B. `[mein-neuer-server]`.
    -   Füllen Sie die Felder `module`, `api_endpoint` und `json_path`.
    -   Fügen Sie den Namen der neuen Sektion (`mein-neuer-server`) zur `enabled_instances`-Liste in der `[main]`-Sektion hinzu.
4.  **API neu starten:** `sudo systemctl restart gunicorn-games-api.service`

Der neue Endpunkt (z.B. `/api/mein-neuer-server/players`) ist jetzt aktiv.
