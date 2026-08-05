import dataclasses
import datetime
import jwt
import random
from django.conf import settings
from django.utils import timezone
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
    usuario = UsuariosModel.objects.filter(correo__iexact=correo).first()
    return usuario


def obtenerToken(idUsuario):
    payload = {
        "id": idUsuario,
        "exp": datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=24),
        "iat": datetime.datetime.now(datetime.timezone.utc)
    }

    token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm="HS256")
    return token


def generar_codigo_confirmacion(usuario: UsuariosModel):
    codigo = str(random.randint(100000, 999999))
    usuario.verification_code = codigo
    usuario.verification_code_expires = timezone.now() + datetime.timedelta(minutes=30)
    usuario.save(update_fields=["verification_code", "verification_code_expires"])
    return codigo


def enviar_correo_confirmacion(usuario: UsuariosModel):
    codigo = generar_codigo_confirmacion(usuario)
    mail_subject = "🔑 Tu código de verificación | Importaciones Los Bukis"
    html_body = f"""
    <div style="font-family: sans-serif; text-align: center; color: #333;">
        <h2 style="color: #d32f2f;">¡Bienvenido a Los Bukis!</h2>
        <p style="font-size: 1.1em; line-height: 1.5;">
            Gracias por registrarte. Para activar tu cuenta y comenzar a realizar pedidos, 
            ingresa el siguiente código de 6 dígitos en la página web:
        </p>
        <div style="margin: 30px 0;">
            <span style="font-size: 2.5em; font-weight: bold; letter-spacing: 5px; color: #111; background-color: #f4f4f4; padding: 15px 25px; border-radius: 10px; border: 1px solid #ddd;">
                {codigo}
            </span>
        </div>
        <p style="font-size: 0.9em; color: #888;">
            Este código expirará en 30 minutos. Si no solicitaste este registro, puedes ignorar este correo.
        </p>
    </div>
    """
    
    try:
        send_bukis_email(
            recipient_name=usuario.nombre,
            recipient_email=usuario.correo,
            mail_subject=mail_subject,
            html_body=html_body,
        )
        return True, "Correo enviado"
    except Exception as e:
        print(f"Error de SMTP al enviar correo a {usuario.correo}: {e}")
        return False, str(e)


def confirmar_cuenta_codigo(correo: str, codigo: str):
    usuario = UsuariosModel.objects.filter(correo=correo).first()
    
    if not usuario:
        return False, "El usuario no existe."
    
    if usuario.is_email_verified:
        return True, "La cuenta ya ha sido verificada previamente."
        
    if usuario.verification_code != codigo:
        return False, "El código de verificación es incorrecto."
        
    if not usuario.verification_code_expires or timezone.now() > usuario.verification_code_expires:
        return False, "El código de verificación ha expirado. Por favor solicita uno nuevo."
    
    usuario.is_email_verified = True
    usuario.verification_code = None
    usuario.verification_code_expires = None
    usuario.save(update_fields=["is_email_verified", "verification_code", "verification_code_expires"])
    return True, "Cuenta confirmada exitosamente."


def reenviar_correo_confirmacion(correo: str):
    usuario = filtrarUsuarioPorCorreo(correo)
    
    if not usuario:
        return False, "No se encontró ningún usuario con ese correo electrónico."
    
    if usuario.is_email_verified:
        return False, "Esta cuenta ya se encuentra verificada."
    
    exito, msg = enviar_correo_confirmacion(usuario)
    if not exito:
        return False, f"No se pudo enviar el correo por problemas en el servidor: {msg}"
        
    return True, f"Se ha reenviado el correo de confirmación exitosamente. En caso de que el correo haya llegado a la sección de SPAM, verifique que el remitente sea \"{settings.EMAIL_HOST_USER}\"."


def enviar_correo_recuperacion(usuario: UsuariosModel):
    codigo = generar_codigo_confirmacion(usuario)
    mail_subject = "🔒 Recuperación de contraseña | Importaciones Los Bukis"
    html_body = f"""
    <div style="font-family: sans-serif; text-align: center; color: #333;">
        <h2 style="color: #d32f2f;">Restablecimiento de contraseña</h2>
        <p style="font-size: 1.1em; line-height: 1.5;">
            Has solicitado restablecer tu contraseña. Ingresa el siguiente código de 6 dígitos en la página web:
        </p>
        <div style="margin: 30px 0;">
            <span style="font-size: 2.5em; font-weight: bold; letter-spacing: 5px; color: #111; background-color: #f4f4f4; padding: 15px 25px; border-radius: 10px; border: 1px solid #ddd;">
                {codigo}
            </span>
        </div>
        <p style="font-size: 0.9em; color: #888;">
            Este código expirará en 30 minutos. Si no solicitaste este cambio, puedes ignorar este correo; tu contraseña actual seguirá siendo válida.
        </p>
    </div>
    """
    
    try:
        send_bukis_email(
            recipient_name=usuario.nombre,
            recipient_email=usuario.correo,
            mail_subject=mail_subject,
            html_body=html_body,
        )
        return True, "Correo de recuperación enviado"
    except Exception as e:
        print(f"Error de SMTP al enviar correo a {usuario.correo}: {e}")
        return False, str(e)


def restablecer_password(correo: str, codigo: str, nueva_password: str):
    usuario = UsuariosModel.objects.filter(correo=correo).first()
    
    if not usuario:
        return False, "El usuario no existe."
        
    if usuario.verification_code != codigo:
        return False, "El código de verificación es incorrecto."
        
    if not usuario.verification_code_expires or timezone.now() > usuario.verification_code_expires:
        return False, "El código de verificación ha expirado. Por favor solicita uno nuevo."
    
    from django.contrib.auth.password_validation import validate_password
    from django.core.exceptions import ValidationError as DjangoValidationError
    try:
        validate_password(nueva_password)
    except DjangoValidationError as e:
        return False, " ".join(list(e.messages))
        
    usuario.set_password(nueva_password)
    usuario.is_email_verified = True # Por si recuperan contraseña sin haber verificado cuenta antes
    usuario.verification_code = None
    usuario.verification_code_expires = None
    usuario.save(update_fields=["password", "is_email_verified", "verification_code", "verification_code_expires"])
    
    return True, "Contraseña actualizada exitosamente."


#Pedidos (WIP)
def obtenerPedidosPorCliente(idCliente):
    pedidos = PedidosModel.objects.filter(cliente=idCliente)
    return pedidos