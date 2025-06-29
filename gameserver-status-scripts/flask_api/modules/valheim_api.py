from flask import Blueprint, Response
import json
import os

def read_json_file(file_path):
    """Liest eine JSON-Datei sicher ein."""
    if not os.path.exists(file_path):
        return []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            return [] if not content.strip() else json.loads(content)
    except (json.JSONDecodeError, FileNotFoundError):
        return []

def create_blueprint(instance_name, json_path):
    """
    Erstellt und konfiguriert einen Flask Blueprint für eine spezifische Valheim-Instanz.
    """
    blueprint_name = f'valheim_api_{instance_name}'
    valheim_bp = Blueprint(blueprint_name, __name__, url_prefix=f'/api/{instance_name}')

    @valheim_bp.route('/players')
    def get_players():
        """Definiert den Endpunkt /players für diese Valheim-Instanz."""
        player_data = read_json_file(json_path)
        return Response(json.dumps(player_data, indent=2, ensure_ascii=False),
                        mimetype='application/json; charset=utf-8')

    return valheim_bp
