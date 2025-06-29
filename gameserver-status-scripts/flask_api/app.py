from flask import Flask
import configparser
import importlib
import os
import sys

# Flask-Anwendung initialisieren
app = Flask(__name__)

def load_and_register_modules(app_instance):
    """Liest die Konfiguration, lädt die Module für aktivierte Instanzen und registriert deren Endpunkte."""
    config = configparser.ConfigParser()
    config_path = os.path.join(os.path.dirname(__file__), 'config.ini')
    
    if not os.path.exists(config_path):
        print(f"FEHLER: Konfigurationsdatei '{config_path}' nicht gefunden.", file=sys.stderr)
        return

    config.read(config_path)

    try:
        # Lese die Liste der zu aktivierenden Sektionen (z.B. 'enshrouded-public', 'valheim-community')
        enabled_instances_str = config.get('main', 'enabled_instances')
        enabled_instances = [name.strip() for name in enabled_instances_str.split(',') if name.strip()]
    except (configparser.NoSectionError, configparser.NoOptionError):
        print("FEHLER: 'enabled_instances' in Sektion [main] der config.ini nicht gefunden.", file=sys.stderr)
        return

    print(f"Zu aktivierende Instanzen: {', '.join(enabled_instances)}")

    for instance_name in enabled_instances:
        try:
            # Hole die Konfiguration für diese spezifische Instanz
            instance_config = config[instance_name]
            
            # Der 'module'-Schlüssel sagt uns, welche Python-Datei wir laden müssen (z.B. 'enshrouded')
            module_key = instance_config['module']
            api_endpoint = instance_config['api_endpoint']
            json_path = instance_config['json_path']

            # Baue den Modulnamen zusammen (z.B. 'modules.enshrouded_api')
            module_name = f"modules.{module_key}_api"
            
            # Dynamischer Import des Moduls
            game_module = importlib.import_module(module_name)
            
            # Rufe die 'create_blueprint'-Funktion aus dem Modul auf
            # Wir übergeben den einzigartigen Endpunkt-Namen und den JSON-Pfad
            game_blueprint = game_module.create_blueprint(api_endpoint, json_path)
            
            # Registriere den Blueprint bei der Haupt-App
            app_instance.register_blueprint(game_blueprint)
            print(f"-> Instanz '{instance_name}' ({module_key}) erfolgreich geladen. Endpunkt: /api/{api_endpoint}/players")

        except ImportError:
            print(f"WARNUNG: Modul '{module_name}' für Instanz '{instance_name}' nicht gefunden. Überspringe.")
        except KeyError as e:
            print(f"WARNUNG: Fehlender Schlüssel '{e}' in der Konfigurations-Sektion '[{instance_name}]'. Überspringe.")
        except Exception as e:
            print(f"FEHLER beim Laden der Instanz '{instance_name}': {e}", file=sys.stderr)

# Führe die Ladefunktion beim Start der Anwendung aus
load_and_register_modules(app)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)
