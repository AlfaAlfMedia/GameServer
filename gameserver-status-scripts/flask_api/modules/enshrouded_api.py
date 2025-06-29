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
    Erstellt und konfiguriert einen Flask Blueprint für eine spezifische Spiel-Instanz.
    
    :param instance_name: Der einzigartige Name der Instanz (z.B. 'enshrouded-public'),
                          der als URL-Präfix verwendet wird.
    :param json_path: Der Pfad zur zugehörigen JSON-Datei.
    :return: Ein konfigurierter Flask Blueprint.
    """
    # Erstelle einen einzigartigen Blueprint-Namen, um Konflikte zu vermeiden.
    blueprint_name = f'enshrouded_api_{instance_name}'
    
    # Der url_prefix baut die dynamische URL, z.B. /api/enshrouded-public
    enshrouded_bp = Blueprint(blueprint_name, __name__, url_prefix=f'/api/{instance_name}')

    @enshrouded_bp.route('/players')
    def get_players():
        """Definiert den Endpunkt /players relativ zum Blueprint-Präfix."""
        player_data = read_json_file(json_path)
        return Response(json.dumps(player_data, indent=2, ensure_ascii=False),
                        mimetype='application/json; charset=utf-8')

    # Hier könnten in Zukunft weitere Routen hinzugefügt werden, z.B.:
    # @enshrouded_bp.route('/map')
    # def get_map_info():
    #     ...

    return enshrouded_bp
