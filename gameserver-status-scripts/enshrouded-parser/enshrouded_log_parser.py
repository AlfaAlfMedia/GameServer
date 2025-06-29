import re
import json
import time
import os
import logging
import subprocess
import configparser
import sys
from collections import deque

# --- Logger initialisieren ---
# Die Konfiguration des Loggers erfolgt im __main__-Block, nachdem die Konfig geladen wurde.
logger = logging.getLogger(__name__)

# --- Globale Datenstrukturen ---
# Diese werden später aus der Konfigurationsdatei befüllt
CONFIG = {}
player_handles_info = {}
active_players = {}

# --- Regex-Muster ---
PLAYER_SESSION_START_PATTERN = re.compile(r"Remote player added\. Player handle: (\d+)\(\d+\)")
PLAYER_MACHINE_LOGIN_PATTERN = re.compile(r"Player '(\d+)\((\d+)\)' logged in")
PLAYER_NAME_LOGIN_PATTERN = re.compile(r"Player '([^']+)' logged in with Permissions:")
PERMISSION_PATTERN = re.compile(r"\[[A-Z] \d{2}:\d{2}:\d{2},\d{3}\]\s+- (Can[A-Za-z]+)$")
PLAYER_LOGOUT_PATTERN = re.compile(r"Remove Player '([^']+)'")
PEER_DISCONNECT_PATTERN = re.compile(r"(?:Disconnecting|Removed) peer #(\d+)")

# --- Hilfsfunktionen ---
def assign_role(permissions):
    """Weist eine Rolle basierend auf den Berechtigungen zu."""
    if "CanKickBan" in permissions:
        return "Admin"
    elif "CanAccessInventories" in permissions or "CanEditBase" in permissions or "CanExtendBase" in permissions:
        return "Community"
    else:
        return "Guest"

def write_players_to_json():
    """Schreibt die aktiven Spielerdaten in die JSON-Datei."""
    try:
        output_list = list(active_players.values())
        with open(CONFIG['main']['output_json_path'], "w") as f:
            json.dump(output_list, f, indent=2)
        logger.debug(f"Aktualisierte Spielerdaten geschrieben. Aktive Spieler: {len(active_players)}")
    except Exception as e:
        logger.error(f"Beim Schreiben der JSON-Datei: {e}", exc_info=True)

def process_log_line(line):
    """Verarbeitet eine einzelne Logzeile auf Login/Logout-Events."""
    global player_handles_info, active_players
    timestamp = time.time()

    # Logik dieser Funktion bleibt im Kern unverändert
    match_session_start = PLAYER_SESSION_START_PATTERN.search(line)
    if match_session_start:
        handle_id = int(match_session_start.group(1))
        if handle_id not in player_handles_info:
            player_handles_info[handle_id] = {"name": None, "permissions": [], "last_activity": timestamp, "status": "session_started"}
            logger.debug(f"Session für Handle {handle_id} gestartet.")
        return

    match_name_login = PLAYER_NAME_LOGIN_PATTERN.search(line)
    if match_name_login:
        player_name = match_name_login.group(1)
        linked_handle_id = next((h_id for h_id, info in player_handles_info.items() if info["name"] is None and (timestamp - info["last_activity"] < 30)), None)
        if linked_handle_id:
            player_handles_info[linked_handle_id].update({"name": player_name, "status": "awaiting_permissions"})
            active_players[player_name] = {"id": linked_handle_id, "name": player_name, "permissions": [], "role": assign_role([]), "last_seen": timestamp}
            logger.info(f"Spieler '{player_name}' (Handle: {linked_handle_id}) in aktive Spieler aufgenommen.")
            write_players_to_json()
        else:
            logger.warning(f"Konnte kein passendes Handle für Spieler '{player_name}' finden.")
        return

    match_permission = PERMISSION_PATTERN.search(line)
    if match_permission:
        permission = match_permission.group(1)
        player_to_update = next((info for info in player_handles_info.values() if info.get("status") == "awaiting_permissions"), None)
        if player_to_update and player_to_update.get('name') and player_to_update['name'] in active_players:
            player_name = player_to_update['name']
            active_players[player_name]['permissions'].append(permission)
            active_players[player_name]['role'] = assign_role(active_players[player_name]['permissions'])
            logger.debug(f"Berechtigung '{permission}' für '{player_name}' hinzugefügt. Neue Rolle: {active_players[player_name]['role']}")
            write_players_to_json()
        return

    match_logout = PLAYER_LOGOUT_PATTERN.search(line)
    if match_logout:
        player_name = match_logout.group(1)
        if player_name in active_players:
            del active_players[player_name]
            logger.info(f"Spieler '{player_name}' abgemeldet.")
            write_players_to_json()
        handle_to_remove = next((h_id for h_id, info in player_handles_info.items() if info.get("name") == player_name), None)
        if handle_to_remove: del player_handles_info[handle_to_remove]
        return

    match_peer_disconnect = PEER_DISCONNECT_PATTERN.search(line)
    if match_peer_disconnect:
        handle_id = int(match_peer_disconnect.group(1))
        if handle_id in player_handles_info:
            player_name = player_handles_info[handle_id].get("name")
            if player_name and player_name in active_players:
                del active_players[player_name]
                logger.info(f"Spieler '{player_name}' via Peer-Disconnect entfernt.")
                write_players_to_json()
            del player_handles_info[handle_id]
        return

def handle_heartbeat_and_timeout():
    """Aktualisiert Zeitstempel und entfernt Spieler bei Timeout."""
    current_time = time.time()
    
    for player_data in active_players.values():
        player_data['last_seen'] = current_time

    last_check_time = getattr(handle_heartbeat_and_timeout, 'last_check_time', 0)
    if current_time - last_check_time > 10:
        timeout = int(CONFIG['main']['player_timeout_seconds'])
        players_to_remove = {name for name, data in active_players.items() if current_time - data.get("last_seen", 0) > timeout}
        if players_to_remove:
            for name in players_to_remove:
                logger.info(f"Spieler '{name}' aufgrund von Timeout entfernt.")
                del active_players[name]
            write_players_to_json()
        setattr(handle_heartbeat_and_timeout, 'last_check_time', current_time)

def tail_log_file(filepath):
    """Liest eine Logdatei kontinuierlich (für den 'native' Modus)."""
    try:
        with open(filepath, "r") as f:
            f.seek(0, os.SEEK_END)
            logger.info(f"Überwache Logdatei: {filepath}")
            while True:
                line = f.readline()
                if not line:
                    time.sleep(0.1)
                    handle_heartbeat_and_timeout()
                    continue
                handle_heartbeat_and_timeout()
                process_log_line(line)
    except FileNotFoundError:
        logger.error(f"Logdatei nicht gefunden: {filepath}. Warte und versuche erneut...")
        time.sleep(10)
        tail_log_file(filepath)
    except Exception as e:
        logger.critical(f"Kritischer Fehler in tail_log_file: {e}", exc_info=True)

def tail_docker_logs(container_name):
    """Liest Logs eines Docker-Containers (für den 'docker' Modus)."""
    logger.info(f"Überwache Docker-Logs für Container: {container_name}")
    process = None
    while True:
        if process is None or process.poll() is not None:
            if process: logger.warning(f"Docker logs Prozess beendet. Versuche Neustart...")
            try:
                process = subprocess.Popen(["docker", "logs", "--since", "1s", "-f", container_name], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)
                logger.info(f"Docker logs -f '{container_name}' gestartet.")
            except Exception as e:
                logger.error(f"Konnte Docker-Logs nicht starten: {e}", exc_info=True)
                time.sleep(10)
                continue
        
        line = process.stdout.readline()
        if not line:
            time.sleep(0.1)
            handle_heartbeat_and_timeout()
            continue
        
        handle_heartbeat_and_timeout()
        process_log_line(line)

def load_and_validate_config(config_path='config.ini'):
    """Lädt und validiert die Konfiguration aus der INI-Datei."""
    global CONFIG
    parser = configparser.ConfigParser()
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Konfigurationsdatei '{config_path}' nicht gefunden.")
    
    parser.read(config_path)
    CONFIG = {section: dict(parser.items(section)) for section in parser.sections()}
    logger.info("Konfiguration erfolgreich geladen.")

    # Validierung der Konfiguration
    mode = CONFIG.get('main', {}).get('mode')
    if mode == 'native':
        log_path = CONFIG.get('native', {}).get('log_path', '')
        if not log_path or '<' in log_path or '>' in log_path:
            raise ValueError("Konfigurationsfehler: 'log_path' in Sektion [native] ist nicht gesetzt oder ein Platzhalter.")
    elif mode == 'docker':
        container_name = CONFIG.get('docker', {}).get('container_name', '')
        if not container_name or '<' in container_name or '>' in container_name:
            raise ValueError("Konfigurationsfehler: 'container_name' in Sektion [docker] ist nicht gesetzt oder ein Platzhalter.")
    else:
        raise ValueError(f"Konfigurationsfehler: Unbekannter Modus '{mode}' in Sektion [main]. Muss 'native' oder 'docker' sein.")

    logger.info(f"Skript läuft im '{mode}'-Modus.")
    return True

# --- Hauptausführung ---
if __name__ == "__main__":
    CONFIG_PATH = 'config.ini'
    EXAMPLE_CONFIG_PATH = 'config.ini.example'

    # Prüfen, ob eine Konfigurationsdatei existiert, bevor das Logging eingerichtet wird.
    if not os.path.exists(CONFIG_PATH):
        print(f"FEHLER: Konfigurationsdatei '{CONFIG_PATH}' nicht gefunden.", file=sys.stderr)
        if os.path.exists(EXAMPLE_CONFIG_PATH):
            print(f"-> Bitte kopieren Sie '{EXAMPLE_CONFIG_PATH}' nach '{CONFIG_PATH}' und passen Sie die Werte an.", file=sys.stderr)
        sys.exit(1)

    try:
        # Konfiguration laden und validieren
        load_and_validate_config(CONFIG_PATH)

        # Logging-Handler einrichten
        log_handler_path = CONFIG['main']['log_file_path']
        log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        logger.setLevel(logging.INFO) # Für Debugging auf logging.DEBUG umstellen
        logger.addHandler(logging.StreamHandler()) # Immer an die Konsole loggen
        try:
            file_handler = logging.FileHandler(log_handler_path)
            file_handler.setFormatter(log_formatter)
            logger.addHandler(file_handler)
        except PermissionError:
            logger.error(f"Keine Schreibrechte für {log_handler_path}. Bitte Berechtigungen prüfen.")
        
        logger.info("Starte Enshrouded Log-Parser...")
        write_players_to_json()

        # Je nach Modus die passende Funktion starten
        mode = CONFIG['main']['mode']
        if mode == 'native':
            tail_log_file(CONFIG['native']['log_path'])
        elif mode == 'docker':
            tail_docker_logs(CONFIG['docker']['container_name'])

    except (FileNotFoundError, ValueError, KeyError) as e:
        logger.critical(f"Kritischer Startfehler aufgrund der Konfiguration: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Skript durch Benutzer beendet.")
    except Exception as e:
        logger.critical("Ein unerwarteter, kritischer Fehler ist aufgetreten:", exc_info=True)
        sys.exit(1)
