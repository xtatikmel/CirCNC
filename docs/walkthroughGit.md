# Lanzamiento de Circe CNC 🪄

El proyecto ha sido oficialmente renombrado a **Circe CNC**, inspirándose en la diosa de la transformación y el control. Se han actualizado todos los archivos de documentación, interfaces de usuario y comentarios del firmware.

## Cambios Realizados

### 1. Documentación Visual
- **README.md**: Título actualizado y adición de arte ASCII.
- **Docs**: Los archivos `TESTING.md`, `VERIFICACION.md` y `walkthrough.md` ahora reflejan el nuevo nombre y marca.

### 2. Interfaz de Usuario (Python)
- Se actualizó el título de la ventana en `gctrl_redimensionable.py`, `cnc_interface_python.py` y `demo_joystick_cntrl.py`.
- Se añadió el **arte ASCII** al inicio de los logs en la terminal de cada aplicación para dar una bienvenida mística al usuario.

### 3. Firmware de Arduino
- Actualizados los comentarios de cabecera y el mensaje de "Ready" que se envía por serial al conectar.

---

## Guía para el Cambio de Nombre y Colaboradores

> [!IMPORTANT]
> Para que el cambio sea efectivo en la nube y para el resto del equipo, sigue estos pasos:

### 1. Renombrar en GitHub (Tú como administrador)
1. Ve a la página de tu repositorio en GitHub.
2. Haz clic en **Settings** (Ajustes).
3. En la sección **General**, cambia el nombre del repositorio de `CNC-GCTRL-L293` a `Circe-CNC`.
4. Haz clic en el botón **Rename**.

### 2. Actualizar tu Repositorio Local
Una vez renombrado en GitHub, ejecuta estos comandos en tu terminal local:

```bash
# Cambiar la URL del servidor remoto
git remote set-url origin https://github.com/TU_USUARIO/Circe-CNC.git

# Empujar los cambios que acabo de hacer por ti
git add .
git commit -m "docs: rename project to Circe CNC and add ASCII art"
git push origin main
```

### 3. Guía para tus Colaboradores
Dile a tus colaboradores que ejecuten lo siguiente para que sus carpetas y remotos queden sincronizados:

```bash
# 1. Cambiar la URL del remoto
git remote set-url origin https://github.com/TU_USUARIO/Circe-CNC.git

# 2. Bajar los nuevos cambios
git pull origin main
```

> [!TIP]
> **Próximo Paso**: Una vez que confirmes que todo funciona bien con el nuevo nombre, procederemos con la creación del ejecutable (.exe) usando **PyInstaller** para finalizar la fase de despliegue.
