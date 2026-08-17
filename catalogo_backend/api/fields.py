import base64
from django.db import models
from django.conf import settings
from cryptography.fernet import Fernet, InvalidToken

def get_cipher():
    # Asegurar que la llave tenga 32 bytes y sea urlsafe base64
    key = settings.SECRET_KEY.encode('utf-8')[:32].ljust(32, b'0')
    b64_key = base64.urlsafe_b64encode(key)
    return Fernet(b64_key)

class EncryptedCharField(models.CharField):
    description = "A field that encrypts its contents using Fernet."

    def __init__(self, *args, **kwargs):
        # Aumentamos el max_length internamente porque la encriptación expande el tamaño
        kwargs['max_length'] = max(kwargs.get('max_length', 255), 255)
        super().__init__(*args, **kwargs)

    def from_db_value(self, value, expression, connection):
        if value is None or value == "":
            return value
        try:
            return get_cipher().decrypt(value.encode('utf-8')).decode('utf-8')
        except InvalidToken:
            # Si falla la desencriptación, asumimos que es texto plano (datos legados)
            return value
        except Exception:
            return value

    def to_python(self, value):
        if value is None or value == "":
            return value
        # to_python es llamado por formularios/serializadores, el valor ya debería ser plano.
        return value

    def get_prep_value(self, value):
        value = super().get_prep_value(value)
        if value is None or value == "":
            return value
        
        value_str = str(value)
        # Para evitar encriptar algo que ya está encriptado (si Django lo pasa varias veces)
        try:
            get_cipher().decrypt(value_str.encode('utf-8'))
            return value_str # Ya está encriptado
        except InvalidToken:
            # No está encriptado, lo encriptamos
            return get_cipher().encrypt(value_str.encode('utf-8')).decode('utf-8')
        except Exception:
            # Cualquier otro error, intentamos encriptar
            return get_cipher().encrypt(value_str.encode('utf-8')).decode('utf-8')
