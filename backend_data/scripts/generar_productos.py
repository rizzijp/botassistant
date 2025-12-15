import pandas as pd
import random
import os

# Rutas de archivos
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Ajusta esta ruta para apuntar a backend_data/app/etl/data_raw/
DATA_DIR = os.path.join(BASE_DIR, "../app/etl/data_raw")

FILE_PRODUCTS = os.path.join(DATA_DIR, "products.csv")
FILE_SALES = os.path.join(DATA_DIR, "sales.csv")

# Configuración de Generación
NUM_PRODUCTOS = 200 

CATEGORIAS = {
    "Electrónica": ["Laptop", "Mouse", "Teclado", "Monitor", "Auriculares", "Smartphone", "Tablet"],
    "Hogar": ["Lámpara", "Silla", "Mesa", "Organizador", "Toalla", "Sábana", "Cuadro"],
    "Ropa": ["Camiseta", "Pantalón", "Chaqueta", "Zapatillas", "Gorra", "Bufanda"],
    "Juguetes": ["Muñeca", "Auto", "Rompecabezas", "Pelota", "Juego de Mesa", "Robot"],
    "Deportes": ["Pesas", "Colchoneta", "Bicicleta", "Raqueta", "Balón", "Botella"]
}
ADJETIVOS = ["Pro", "Slim", "Max", "Ultra", "Básico", "Premium", "Vintage", "Moderno"]

def fix_all_data():
    print("🚑 INICIANDO REPARACIÓN DE DATOS (CONSISTENCIA TOTAL)...")
    
    # 1. GENERAR PRODUCTOS NUEVOS
    # ---------------------------
    print("   🔨 Generando 200 productos nuevos...")
    prod_data = []
    used_names = set()
    
    for i in range(1, NUM_PRODUCTOS + 1):
        cat = random.choice(list(CATEGORIAS.keys()))
        base = random.choice(CATEGORIAS[cat])
        adj = random.choice(ADJETIVOS)
        nombre = f"{base} {adj}"
        
        counter = 1
        while nombre in used_names:
            nombre = f"{base} {adj} {counter}"
            counter += 1
        used_names.add(nombre)
        
        # Precio base aleatorio
        precio = round(random.uniform(15.0, 800.0), 2)
        
        prod_data.append({
            "product_id": i,
            "product_name": nombre,
            "category": cat,
            "unit_price": precio
        })

    df_products = pd.DataFrame(prod_data)

    # 2. ACTUALIZAR VENTAS (Para que coincidan con los nuevos precios)
    # --------------------------------------------------------------
    print("   🔄 Recalculando montos en SALES.CSV...")
    if not os.path.exists(FILE_SALES):
        print(f"❌ ERROR: No encuentro {FILE_SALES}. Asegúrate de que la ruta sea correcta.")
        return

    df_sales = pd.read_csv(FILE_SALES)
    
    # Hacemos un Merge para traer el precio nuevo al DataFrame de ventas
    # (Usamos el product_id para unir)
    df_merged = df_sales.merge(df_products[['product_id', 'unit_price']], on='product_id', how='left')
    
    # Si hay ventas con productos > 200, les asignamos un precio por defecto o borramos
    # Aquí asumimos que sales tiene IDs 1-200. Si hay NULL, rellenamos con precio promedio.
    avg_price = df_products['unit_price'].mean()
    df_merged['unit_price'] = df_merged['unit_price'].fillna(avg_price)

    # --- CÁLCULOS MATEMÁTICOS ---
    # 1. Subtotal = Cantidad * Precio Nuevo
    df_merged['subtotal'] = df_merged['quantity'] * df_merged['unit_price']
    
    # 2. Descuento ($) = Subtotal * (Porcentaje / 100)
    # Aseguramos que discount_percentage sea numérico
    df_merged['discount_percentage'] = pd.to_numeric(df_merged['discount_percentage'], errors='coerce').fillna(0)
    df_merged['discount_amount'] = df_merged['subtotal'] * (df_merged['discount_percentage'] / 100)
    
    # 3. Total = Subtotal - Descuento
    df_merged['total'] = df_merged['subtotal'] - df_merged['discount_amount']
    
    # Redondear a 2 decimales para que parezca dinero real
    for col in ['subtotal', 'discount_amount', 'total']:
        df_merged[col] = df_merged[col].round(2)

    # Limpiar columnas auxiliares (quitamos unit_price porque sales.csv original no lo tenía)
    # Si quieres guardarlo, déjalo. Si quieres respetar el formato original, bórralo.
    # El usuario dijo "sales no tiene precio unitario", así que lo quitamos para respetar estructura.
    df_final_sales = df_merged.drop(columns=['unit_price'])

    # 3. GUARDAR LOS ARCHIVOS CORREGIDOS
    # ----------------------------------
    print("   💾 Guardando archivos...")
    df_products.to_csv(FILE_PRODUCTS, index=False)
    df_final_sales.to_csv(FILE_SALES, index=False)
    
    print(f"✅ ¡ÉXITO! Productos generados y Ventas recalculadas.")
    print(f"   - Productos: {len(df_products)} filas")
    print(f"   - Ventas: {len(df_final_sales)} filas (Montos actualizados)")

if __name__ == "__main__":
    fix_all_data()