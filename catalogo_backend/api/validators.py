import re
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _


class ComplexPasswordValidator:
    passwordRegex = r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&._-])[A-Za-z\d@$!%*?&._-]{8,}$'

    def validate(self, password, user=None):
        if not re.match(self.passwordRegex, password):
            raise ValidationError(
                "La contraseña debe tener al menos 8 caracteres, incluir una mayúscula, una minúscula, un número y un carácter especial (@$!%*?&).",
                code='password_no_complex',
            )
    
    def get_help_text(self):
        return "Tu contraseña debe tener al menos 8 caracteres, una mayúscula, una minúscula, un número y un carácter especial."