from datetime import datetime
import dataclasses
import datetime
import jwt
from django.conf import settings
# pyrefly: ignore [missing-import]
from .models import UsuariosModel, PedidosModel
# pyrefly: ignore [missing-import]
from .utils.emails import send_bukis_email


# Usuarios (Data Class)
@dataclasses.dataclass
class DataClassUsuarios:
    nombre: str = ""
    apellido: str = ""
    correo: str = ""
    telefono: str = ""
    password: str = None
    id: int = None

    @classmethod
    def from_instance(cls, usuario: "UsuariosModel"):
        return cls(
            nombre = usuario.nombre,
            apellido = usuario.apellido,
            correo = usuario.correo,
            telefono = usuario.telefono,
            id = usuario.id
        )


def crear_usuario(dcUsuario: "DataClassUsuarios"):
    instancia = UsuariosModel(
        nombre = dcUsuario.nombre, 
        apellido = dcUsuario.apellido, 
        correo = dcUsuario.correo,
        telefono = dcUsuario.telefono,
    )

    if dcUsuario.password is not None:
        instancia.set_password(dcUsuario.password)
    
    instancia.save()
    return DataClassUsuarios.from_instance(instancia)


def filtrarUsuarioPorCorreo(correo):
    usuario = UsuariosModel.objects.filter(correo=correo).first()
    return usuario


def obtenerToken(idUsuario):
    payload = {
        "id": idUsuario,
        "exp": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=24),
        "iat": datetime.datetime.now(datetime.timezone.utc)
    }

    token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm="HS256")
    return token


def generar_token_confirmacion(user_id: int):
    payload = {
        "user_id": user_id,
        "type": "email_confirmation",
        "exp": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=24),
        "iat": datetime.datetime.now(datetime.timezone.utc)
    }
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm="HS256")


def verificar_token_confirmacion(token: str):
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=["HS256"])

        if payload.get("type") != "email_confirmation":
            return None

        return payload.get("user_id")
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None


def enviar_correo_confirmacion(usuario: UsuariosModel):
    token = generar_token_confirmacion(usuario.id)
    confirmation_url = f"{settings.FRONTEND_URL}/confirmar-cuenta?token={token}"
    mail_subject = "🔑 Confirma tu cuenta | Importaciones Los Bukis"
    html_body = f"""
    <p style="font-size: 1.1em; line-height: 1.5;">
        Gracias por registrarte. Para activar tu cuenta y comenzar a realizar pedidos, 
        por favor confirma tu correo electrónico haciendo clic en el siguiente botón:
    </p>
    <div style="text-align: center; margin: 25px 0;">
        <a href="{confirmation_url}" 
           style="background-color: #007bff; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; font-weight: bold; display: inline-block;">
            Confirmar mi cuenta
        </a>
    </div>
    <p style="font-size: 0.95em; color: #555;">
        Si el botón no funciona, copia y pega este enlace en tu navegador:<br>
        <a href="{confirmation_url}" style="color: #007bff;">{confirmation_url}</a>
    </p>
    <p style="font-size: 0.9em; color: #888;">
        Este enlace expirará en 24 horas.
    </p>
    """
    
    send_bukis_email(
        recipient_name=usuario.nombre,
        recipient_email=usuario.correo,
        mail_subject=mail_subject,
        html_body=html_body,
    )


def confirmar_cuenta_token(token: str):
    user_id = verificar_token_confirmacion(token)
    
    if not user_id:
        return False, "El enlace de confirmación es inválido o ha expirado."
    
    usuario = UsuariosModel.objects.filter(id=user_id).first()
    
    if not usuario:
        return False, "El usuario no existe."
    
    if usuario.is_email_verified:
        return True, "La cuenta ya ha sido verificada previamente."
    
    usuario.is_email_verified = True
    usuario.save()
    return True, "Cuenta confirmada exitosamente."


def reenviar_correo_confirmacion(correo: str):
    usuario = filtrarUsuarioPorCorreo(correo)
    
    if not usuario:
        return False, "No se encontró ningún usuario con ese correo electrónico."
    
    if usuario.is_email_verified:
        return False, "Esta cuenta ya se encuentra verificada."
    
    enviar_correo_confirmacion(usuario)
    return True, "Se ha reenviado el correo de confirmación exitosamente."


#Pedidos (WIP)
def obtenerPedidosPorCliente(idCliente):
    pedidos = PedidosModel.objects.filter(cliente=idCliente)
    return pedidos