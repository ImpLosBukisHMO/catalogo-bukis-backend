from django.core.management.base import BaseCommand
from django.core.files.uploadedfile import SimpleUploadedFile
from api.models import UsuariosModel, CategoriasModel, ColorModel, ProductosModel, ProductoVariantesModel
import random

class Command(BaseCommand):
    help = "Genera datos de prueba específicos para validar el flujo del Worker Panel"

    def handle(self, *args, **options):
        self.stdout.write("--- 🛠️ Iniciando Seed para pruebas de Worker ---")

        # 1. Crear Usuario Worker
        worker, created = UsuariosModel.objects.get_or_create(
            correo="worker@test.com",
            defaults={
                "nombre": "Juan",
                "apellido": "Worker",
                "telefono": "1234567890",
                "is_staff": True,
                "is_active": True
            }
        )
        if created:
            worker.set_password("workerpassword123")
            worker.save()
            self.stdout.write(f"✅ Usuario Worker creado: worker@test.com / workerpassword123")
        else:
            self.stdout.write("ℹ️ Usuario Worker ya existía.")

        # 2. Crear Colores
        colores_data = [
            ("Negro", "#000000"),
            ("Blanco", "#FFFFFF"),
            ("Rojo Intenso", "#FF0000"),
            ("Azul Marino", "#000080"),
            ("Verde Lima", "#32CD32"),
        ]
        colores_objs = []
        for nombre, hex_code in colores_data:
            # Buscamos si ya existe un color con ese nombre o con ese código HEX
            c = ColorModel.objects.filter(nombre=nombre).first() or ColorModel.objects.filter(hex=hex_code).first()
            
            if not c:
                c = ColorModel.objects.create(nombre=nombre, hex=hex_code)
            
            colores_objs.append(c)
        self.stdout.write(f"✅ {len(colores_objs)} Colores listos.")

        # 3. Crear Categorías
        cat_names = ["Hoodies", "Playeras", "Accesorios", "Edición Limitada"]
        categorias_objs = []
        for name in cat_names:
            cat, _ = CategoriasModel.objects.get_or_create(nombre=name)
            categorias_objs.append(cat)
        self.stdout.write(f"✅ {len(categorias_objs)} Categorías listas.")

        # 4. Crear Productos y Variantes
        # Imagen dummy para cumplir con el modelo
        dummy_img = SimpleUploadedFile(
            name='test_product.jpg',
            content=b'\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00\x05\x04\x04\x00\x00\x00\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02\x44\x01\x00\x3b',
            content_type='image/jpeg'
        )

        productos_data = [
            {"nombre": "Sudadera Oversize Urban", "precio": 850.00, "cat": categorias_objs[0]},
            {"nombre": "Playera Algodón Premium", "precio": 350.00, "cat": categorias_objs[1]},
            {"nombre": "Gorra Trucker Bukis", "precio": 299.00, "cat": categorias_objs[2]},
            {"nombre": "Hoodie Reflective Night", "precio": 1200.00, "cat": categorias_objs[3]},
        ]

        for p_info in productos_data:
            prod, p_created = ProductosModel.objects.get_or_create(
                nombre=p_info["nombre"],
                defaults={
                    "descripcion": f"Descripción detallada para {p_info['nombre']}",
                    "precio": p_info["precio"],
                    "peso": 0.5,
                    "medidas": "30x40x5 cm",
                    "imagen": dummy_img,
                    "worker": worker,
                    "disponible": True
                }
            )
            if p_created:
                prod.categorias.add(p_info["cat"])
            
            # Seleccionamos colores únicos para este producto para evitar errores de UniqueConstraint
            colores_seleccionados = random.sample(colores_objs, k=3)

            # Variante 1: Stock normal
            # Variant 1: Stock normal
            ProductoVariantesModel.objects.get_or_create(
                producto=prod,
                color=colores_seleccionados[0],
                defaults={
                    "item": f"SKU-{prod.id}-REG",
                    "stock": random.randint(15, 50),
                    "activo": True
                }
            )
            # Variante 2: Stock bajo (para probar alertas del dashboard)
            ProductoVariantesModel.objects.get_or_create(
                producto=prod,
                color=colores_seleccionados[1],
                defaults={
                    "item": f"SKU-{prod.id}-LOW",
                    "stock": random.randint(1, 4),
                    "activo": True
                }
            )
            # Variante 3: Sin stock (Agotado)
            ProductoVariantesModel.objects.get_or_create(
                producto=prod,
                color=colores_seleccionados[2],
                defaults={
                    "item": f"SKU-{prod.id}-OUT",
                    "stock": 0,
                    "activo": True
                }
            )

        self.stdout.write(self.style.SUCCESS("--- 🏁 Seed completado con éxito ---"))
        self.stdout.write("Usa 'worker@test.com' / 'workerpassword123' para entrar al panel.")
