from django.middleware.csrf import get_token

class CSRFHeaderMiddleware:
    """
    Middleware para inyectar explícitamente el token CSRF en los headers de las respuestas.
    Esto permite que en entornos Cross-Origin (Frontend en dominio distinto al Backend),
    el Frontend pueda leer el header X-CSRFToken y usarlo en sus peticiones POST, ya que
    document.cookie no puede leer cookies de dominios externos.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        # get_token garantiza que la cookie csrftoken se genere, y devuelve el token
        token = get_token(request)
        if token:
            response['X-CSRFToken'] = token
        return response
