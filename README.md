# Stock Management System - Bicicleteria

Sistema de gestión de inventario para bicicletería.

## Requisitos

- Python 3.10+ instalado
- Conexión a internet (primera vez, para instalar dependencias)

## Instalación

1. Extraer el archivo ZIP en una carpeta
2. Ejecutar el lanzador según tu sistema operativo

## Uso

### Windows
Doble click en `run_app.bat`

### Linux/Mac
```bash
chmod +x run_app.sh
./run_app.sh
```

## Características

- 📊 **Stock & Pricing**: Visualización de productos en grilla, edición de stock
- 📦 **Restocking**: Gestión de pedidos de reposición con ID único
- 🛒 **Point of Sale**: Sistema de ventas con control de stock

## Archivos Importantes

- `products.db` - Base de datos SQLite con productos
- `static/` - Imágenes de productos
- `logs/` - Archivos de órdenes y ventas

## Notas

- La aplicación se abre automáticamente en el navegador
- URL por defecto: http://localhost:8501
- Presiona Ctrl+C en la terminal para cerrar el servidor