# QR Generator

Generador local de QRs dinámicos. Cada QR codifica una URL fija
(`<URL base>/r/<slug>`) que redirige al destino real, así que puedes cambiar
el destino cuando quieras sin reimprimir el QR.

## Uso

Doble clic en `start.bat`. La primera vez crea el entorno virtual e instala
las dependencias. Después abre el panel en http://127.0.0.1:5000.

- **Crear**: slug (va dentro del QR y no se puede cambiar), nombre y URL de destino.
- **Editar destino**: cambia la URL y pulsa Guardar.
- **Descargar**: PNG (alta resolución) o SVG (vectorial, para imprenta).

El panel solo responde desde este PC. Si alguien accede por el túnel o por
la red, recibe un 404. Lo único público es `/r/<slug>`.

## Importante: la URL base

Quien escanea el QR necesita llegar a la URL base desde su móvil, así que
`http://127.0.0.1:5000` solo sirve para pruebas. **Configura la URL base
definitiva en "Publicación" antes de imprimir nada**: si la cambias después,
los QR ya impresos dejarán de funcionar.

Tienes dos opciones:

### A. Estático con GitHub Pages (recomendada: gratis, sin tener el PC encendido)

1. Crea un repo en GitHub (por ejemplo `qr`) y sube este proyecto.
2. En el repo: Settings → Pages → Branch `main`, carpeta `/docs`.
3. En el panel: modo **Estático**, URL base `https://<usuario>.github.io/qr`.
4. Después de crear o editar QRs, ejecuta `export.bat` (exporta, hace commit y push).
   Los cambios se ven en 1-2 minutos.

En este modo no se cuentan los escaneos.

### B. Servidor + túnel (cuenta escaneos, pero el PC tiene que estar encendido)

Expón el puerto 5000 con un túnel de dominio fijo, por ejemplo Cloudflare Tunnel:

```
cloudflared tunnel --url http://127.0.0.1:5000        # prueba rápida (URL aleatoria)
```

Para producción necesitas un túnel con nombre y un dominio propio (por ejemplo
`qr.tudominio.com`), porque la URL aleatoria cambia en cada arranque. Pon esa
URL como URL base en modo **Servidor**.

## Datos

- `data/qr.db`: SQLite con los QRs (no se sube a git).
- `data/config.json`: URL base y modo.
- `docs/`: redirects estáticos generados para GitHub Pages.

Exportar sin abrir el panel: `.venv\Scripts\python app.py --export`
