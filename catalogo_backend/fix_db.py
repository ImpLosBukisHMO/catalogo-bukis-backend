import os
import sys
import shutil

def clean_and_setup():
    # Obtener rutas absolutas
    base_dir = os.path.dirname(os.path.abspath(__file__))
    db_path = os.path.join(base_dir, 'db.sqlite3')
    migrations_dir = os.path.join(base_dir, 'api', 'migrations')

    print(f"--- 🛠️  Iniciando reparación del proyecto en: {base_dir} ---")

    # 1. Eliminar base de datos existente
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
            print("✅ Base de datos (db.sqlite3) eliminada.")
        except PermissionError:
            print("❌ ERROR CRÍTICO: No se pudo eliminar db.sqlite3.")
            print("⚠️  POR FAVOR, DETÉN EL SERVIDOR (Ctrl+C en la terminal donde corre runserver) y vuelve a intentar.")
            return
    else:
        print("ℹ️  No se encontró db.sqlite3, continuando...")

    # 2. Eliminar archivos de migración corruptos/antiguos
    if os.path.exists(migrations_dir):
        count = 0
        for filename in os.listdir(migrations_dir):
            if filename != "__init__.py" and filename.endswith(".py"):
                file_path = os.path.join(migrations_dir, filename)
                try:
                    os.remove(file_path)
                    count += 1
                except Exception as e:
                    print(f"❌ Error eliminando {filename}: {e}")
        print(f"✅ Se eliminaron {count} archivos de migración antiguos.")
    else:
        os.makedirs(migrations_dir)

    # Asegurar que existe __init__.py para que Python reconozca el paquete
    if not os.path.exists(os.path.join(migrations_dir, "__init__.py")):
        open(os.path.join(migrations_dir, "__init__.py"), "w").close()
    
    # 3. Ejecutar comandos de Django
    python_exe = sys.executable  # Usar el mismo python que ejecuta este script
    
    print("\n--- 📦 Creando nuevas migraciones (makemigrations) ---")
    if os.system(f'"{python_exe}" manage.py makemigrations api') != 0:
        print("❌ Error en makemigrations. Revisa tu código.")
        return

    print("\n--- 🚀 Aplicando migraciones (migrate) ---")
    if os.system(f'"{python_exe}" manage.py migrate') != 0:
        print("❌ Error en migrate.")
        return

    print("\n--- 👤 Creando Superusuario Automático ---")
    # Script inline para crear superusuario sin interacción manual
    create_superuser_script = """
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'catalogo_backend.settings')
django.setup()
from api.models import UsuariosModel
try:
    if not UsuariosModel.objects.filter(correo='admin@test.com').exists():
        UsuariosModel.objects.create_superuser(
            nombre='Admin', 
            apellido='General', 
            correo='admin@test.com', 
            telefono='5555555555', 
            password='adminpassword123'
        )
        print('✅ ¡ÉXITO! Superusuario creado.')
        print('   Correo: admin@test.com')
        print('   Pass:   adminpassword123')
    else:
        print('ℹ️ El superusuario ya existe.')
except Exception as e:
    print(f'❌ Error creando superusuario: {e}')
"""
    import subprocess
    subprocess.run([python_exe, '-c', create_superuser_script])
    
    print("\n--- 🏁 Proceso finalizado. Ahora puedes correr 'python manage.py runserver' ---")

if __name__ == "__main__":
    clean_and_setup()