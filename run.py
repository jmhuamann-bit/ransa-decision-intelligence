import os
import socket

from app import create_app

app = create_app()


def _pick_port(preferred: int) -> int:
    """Usa PORT/el puerto preferido si esta libre; si no, busca el siguiente libre.
    Evita chocar con otros servidores locales (p. ej. otro proyecto Flask en el mismo equipo)."""
    for port in range(preferred, preferred + 10):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    return preferred


if __name__ == "__main__":
    requested = int(os.environ.get("PORT", 5000))
    port = _pick_port(requested)
    if port != requested:
        print(f"AVISO: el puerto {requested} esta ocupado por otro proceso. Usando el puerto {port} en su lugar.")
    app.run(host="0.0.0.0", port=port, debug=True, use_reloader=False)
