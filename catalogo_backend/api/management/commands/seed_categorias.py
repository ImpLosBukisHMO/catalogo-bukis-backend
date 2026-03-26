"""
Management command: seed_categorias
Crea las categorías del catálogo y las asocia a los productos existentes según
patrones de nombre.

Uso:
    python manage.py seed_categorias
"""
from django.core.management.base import BaseCommand
from api.models import CategoriasModel, ProductosModel


# Categorías a crear (get_or_create — no duplica si ya existen)
NUEVAS_CATEGORIAS = [
    "Hoodies",
    "Camisetas",
    "Pantalones",
    "Accesorios",
    "Nuevos lanzamientos",
]

# Reglas: (patron_en_nombre_producto, nombre_categoria)
# El patrón se busca en el nombre del producto (case-insensitive, contiene)
REGLAS_ASOCIACION = [
    ("sudadera", "Hoodies"),
    ("hoodie", "Hoodies"),
    ("capucha", "Hoodies"),
    ("playera", "Camisetas"),
    ("camiseta", "Camisetas"),
    ("remera", "Camisetas"),
    ("pantalon", "Pantalones"),
    ("jogger", "Pantalones"),
    ("short", "Pantalones"),
    ("llavero", "Accesorios"),
    ("pin", "Accesorios"),
    ("accesorio", "Accesorios"),
    ("taza", "Tazas"),
    ("morral", "Morrales"),
    ("libreta", "Librería"),
    ("pluma", "Librería"),
]


class Command(BaseCommand):
    help = "Crea categorías base y asocia productos existentes según nombre."

    def handle(self, *args, **options):
        self.stdout.write("=== Creando categorías ===")

        categorias_map: dict[str, CategoriasModel] = {}

        for nombre in NUEVAS_CATEGORIAS:
            obj, created = CategoriasModel.objects.get_or_create(nombre=nombre)
            categorias_map[nombre] = obj
            status = "creada" if created else "ya existía"
            self.stdout.write(f"  [{status}] {nombre}")

        # También registramos las que ya existían para poder asociar
        for obj in CategoriasModel.objects.all():
            if obj.nombre not in categorias_map:
                categorias_map[obj.nombre] = obj

        self.stdout.write("\n=== Asociando productos a categorías ===")

        productos = ProductosModel.objects.prefetch_related("categorias").all()

        for producto in productos:
            nombre_lower = producto.nombre.lower()
            categorias_a_agregar = []

            for patron, cat_nombre in REGLAS_ASOCIACION:
                if patron in nombre_lower:
                    cat = categorias_map.get(cat_nombre)
                    if cat:
                        categorias_a_agregar.append(cat)

            if categorias_a_agregar:
                for cat in categorias_a_agregar:
                    producto.categorias.add(cat)
                nombres = [c.nombre for c in categorias_a_agregar]
                self.stdout.write(
                    f'  "{producto.nombre}" → {nombres}'
                )
            else:
                self.stdout.write(
                    f'  "{producto.nombre}" → sin regla (sin cambios)'
                )

        self.stdout.write(self.style.SUCCESS("\n¡Listo! Categorías y asociaciones completadas."))
