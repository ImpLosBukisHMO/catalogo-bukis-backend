import dataclasses
import datetime
import jwt
from .models import UsuariosModel, PedidosModel
from django.conf import settings


#Usuarios
@dataclasses.dataclass
class DataClassUsuarios:
    nombre: str
    apellido: str
    correo: str
    telefono: str
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


def crear_usuario(dcUsuario: 'DataClassUsuarios'):
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
        'id': idUsuario,
        'exp': datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=24),
        'iat': datetime.datetime.now(datetime.timezone.utc)
    }

    token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm='HS256')
    return token




#Pedidos (WIP)
def obtenerPedosPorCliente(idCliente):
    pedidos = PedidosModel.objects.filter(cliente=idCliente)
    return pedidos