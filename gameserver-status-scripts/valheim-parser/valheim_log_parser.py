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
logger = logging.getLogger(__name__)

# --- Globale Datenstrukturen ---
CONFIG = {}
players_in_progress = {}
active_players = {}
admin_steam_ids = set()

# --- Regex-Muster (vereinfacht, um auf nativen & Docker-Logs zu funktionieren) ---
# Wir suchen nur noch nach den einzigartigen Teilen der Nachricht, unabhängig vom Präfix.
PLAYER_CONNECT_PATTERN = re.compile(r"Got connection SteamID (?P<steamid>\d{17})")
PLAYER_NAME_LOGIN_PATTERN = re.compile(r"Got character ZDOID from (?P<playername>[^:]+)\s+:")
PLAYER_DISCONNECT_PATTERN = re.compile(r"Closing socket (?P<steamid>\d{17})")

# --- Hilfsfunktionen ---
def load_admin_list():
    """Liest die SteamIDs aus der adminlist.txt und speichert sie in einem Set."""
    global admin_steam_ids
    try:
        with open(CONFIG['main']['admin_list_path'], 'r') as f:
            ids = {line.strip() for line in f if line.strip()}
            admin_steam_ids = ids
            logger.info(f"Admin-Liste erfolgreich geladen. {len(admin_steam_ids)} Admin(s) gefunden.")
    except FileNotFoundError:
        logger.warning(f"Admin-Liste unter {CONFIG['main']['admin_list_path']} nicht gefunden.")
    except Exception as e:
        logger.error(f"Beim Lesen der Admin-Liste: {e}", exc_info=True)

def assign_role(steam_id):
    """Weist einem Spieler basierend auf der Admin-Liste eine Rolle zu."""
    if steam_id and str(steam_id) in admin_steam_ids:
        return "Admin"
    return "Community"

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
    global players_in_progress, active_players
    timestamp = time.time()

    match_connect = PLAYER_CONNECT_PATTERN.search(line)
    if match_connect:
        steam_id = match_connect.group("steamid")
        if steam_id not in players_in_progress:
            players_in_progress[steam_id] = {"name": None, "last_activity": timestamp}
            logger.debug(f"Neue Verbindung (SteamID: {steam_id}).")
        return

    match_name_login = PLAYER_NAME_LOGIN_PATTERN.search(line)
    if match_name_login:
        player_name = match_name_login.group("playername").strip()
        linked_steam_id = next((s_id for s_id, info in players_in_progress.items() if info["name"] is None and (timestamp - info["last_activity"]) < 60), None)
        if linked_steam_id:
            role = assign_role(linked_steam_id)
            active_players[player_name] = {"name": player_name, "steam_id": linked_steam_id, "role": role, "last_seen": timestamp}
            players_in_progress[linked_steam_id]['name'] = player_name
            logger.info(f"Spieler '{player_name}' (Rolle: {role}) in aktive Spieler aufgenommen.")
            write_players_to_json()
        else:
            logger.warning(f"Konnte keine passende SteamID für Spieler '{player_name}' finden.")
        return

    match_disconnect = PLAYER_DISCONNECT_PATTERN.search(line)
    if match_disconnect:
        steam_id = match_disconnect.group("steamid")
        player_name_to_remove = next((name for name, data in active_players.items() if data["steam_id"] == steam_id), None)
        if player_name_to_remove:
            if player_name_to_remove in active_players: del active_players[player_name_to_remove]
            logger.info(f"Spieler '{player_name_to_remove}' abgemeldet.")
            write_players_to_json()
        if steam_id in players_in_progress:
            del players_in_progress[steam_id]
        return

def handle_heartbeat_and_timeout():
    """Aktualisiert Zeitstempel, prüft auf Timeouts und lädt die Admin-Liste neu."""
    current_time = time.time()
    
    for player_data in active_players.values():
        player_data['last_seen'] = current_time

    last_check_time = getattr(handle_heartbeat_and_timeout, 'last_check_time', 0)
    if current_time - last_check_time > 10:
        timeout = int(CONFIG['main']['player_timeout_seconds'])
        players_to_remove = {name for name, data in active_players.items() if current_time - data.get("last_seen", 0) > timeout}
        if players_to_remove:
            for name in players_to_remove:
                if name in active_players: del active_players[name]
                logger.info(f"Spieler '{name}' aufgrund von Timeout entfernt.")
            write_players_to_json()
        
        try:
            admin_list_path = CONFIG['main']['admin_list_path']
            last_mod_time = os.path.getmtime(admin_list_path)
            last_load_time = getattr(handle_heartbeat_and_timeout, 'last_admin_load_time', 0)
            if last_mod_time > last_load_time:
                logger.info("adminlist.txt wurde geändert. Lade neu...")
                load_admin_list()
                setattr(handle_heartbeat_and_timeout, 'last_admin_load_time', last_mod_time)
        except FileNotFoundError:
            if admin_steam_ids:
                logger.warning("adminlist.txt wurde entfernt. Leere Admin-Liste.")
                admin_steam_ids.clear()

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
    """Lädt und validiert die Konfiguration."""
    global CONFIG
    parser = configparser.ConfigParser()
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Konfigurationsdatei '{config_path}' nicht gefunden.")
    
    parser.read(config_path)
    CONFIG = {section: dict(parser.items(section)) for section in parser.sections()}
    logger.info("Konfiguration erfolgreich geladen.")

    mode = CONFIG.get('main', {}).get('mode')
    if mode == 'native':
        if not CONFIG.get('native', {}).get('log_path', ''):
            raise ValueError("Konfigurationsfehler: 'log_path' in Sektion [native] ist nicht gesetzt.")
    elif mode == 'docker':
        if not CONFIG.get('docker', {}).get('container_name', ''):
            raise ValueError("Konfigurationsfehler: 'container_name' in Sektion [docker] ist nicht gesetzt.")
    else:
        raise ValueError(f"Konfigurationsfehler: Unbekannter Modus '{mode}'. Muss 'native' oder 'docker' sein.")

    logger.info(f"Skript läuft im '{mode}'-Modus.")
    return True

# --- Hauptausführung ---
if __name__ == "__main__":
    CONFIG_PATH = 'config.ini'
    EXAMPLE_CONFIG_PATH = 'config.ini.example'

    if not os.path.exists(CONFIG_PATH):
        print(f"FEHLER: Konfigurationsdatei '{CONFIG_PATH}' nicht gefunden.", file=sys.stderr)
        if os.path.exists(EXAMPLE_CONFIG_PATH):
            print(f"-> Bitte kopieren Sie '{EXAMPLE_CONFIG_PATH}' nach '{CONFIG_PATH}' und passen Sie die Werte an.", file=sys.stderr)
        sys.exit(1)

    try:
        load_and_validate_config(CONFIG_PATH)

        log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        log_handler_path = CONFIG['main']['log_file_path']
        logger.setLevel(logging.INFO)
        logger.addHandler(logging.StreamHandler())
        try:
            file_handler = logging.FileHandler(log_handler_path)
            file_handler.setFormatter(log_formatter)
            logger.addHandler(file_handler)
        except PermissionError:
            logger.error(f"Keine Schreibrechte für {log_handler_path}. Bitte Berechtigungen prüfen.")
        
        logger.info("Starte Valheim Log-Parser...")
        load_admin_list()
        try:
            setattr(handle_heartbeat_and_timeout, 'last_admin_load_time', os.path.getmtime(CONFIG['main']['admin_list_path']))
        except FileNotFoundError:
            setattr(handle_heartbeat_and_timeout, 'last_admin_load_time', 0)

        write_players_to_json()
        
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
