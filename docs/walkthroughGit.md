# Guía para Colaboradores: CirCNC 🪄

El proyecto se llama oficialmente **CirCNC**, inspirándose en la diosa de la transformación y el control. El repositorio ya fue renombrado en GitHub. Esta guía es para que tú y tus colaboradores sincronicen sus entornos locales.

## Cambios Realizados en el Proyecto

### 1. Documentación Visual y Branding
- **README.md**: Título **CirCNC** y arte ASCII.
- **Docs**: `TESTING.md`, `VERIFICACION.md` y `walkthrough.md` actualizados.
- **Interfaz GUI**: Logotipo integrado, icono de app configurado.

### 2. Interfaz de Usuario (Python)
- Título actualizado en `gctrl_redimensionable.py`, `cnc_interface_python.py` y `demo_joystick_cntrl.py`.
- **Arte ASCII** en el log de inicio de cada aplicación.
- **Selector de perfil de motor**: 80mm (Nema 9294) o 40mm (DVD Stepper), sin modificar el firmware.

### 3. Firmware de Arduino
- Límites por defecto: **80×80mm**.
- Mensaje serial: `🪄 CirCNC (Bresenham Optimized) ready!`

---

## Guía para Sincronizar el Repositorio

> [!IMPORTANT]
> El repositorio ya fue renombrado en GitHub de `CNC-GCTRL-L293` a `CirCNC`. Sigue estos pasos para actualizar tu entorno local.

### Como Administrador (ya hecho en GitHub)
Si aún necesitas verificar o repetir el proceso:
1. Ve a tu repositorio en GitHub → **Settings** → **General**.
2. Cambia el nombre a `CirCNC` → **Rename**.

### Actualizar tu Clon Local
```bash
# Actualizar la URL del remoto al nuevo nombre
git remote set-url origin https://github.com/TU_USUARIO/CirCNC.git

# Subir todos los cambios de esta sesión
git add .
git commit -m "feat: rename to CirCNC, add motor profiles (80mm/40mm) and branding"
git push origin main
```

### Guía para tus Colaboradores
Dile a cada colaborador que ejecute esto en su máquina:

```bash
# 1. Actualizar la URL del remoto
git remote set-url origin https://github.com/TU_USUARIO/CirCNC.git

# 2. Descargar todos los cambios
git pull origin main
```

> [!TIP]
> **Próximo Paso**: Con el sistema completamente renombrado y los perfiles de motor funcionando, el siguiente paso es generar el **ejecutable (.exe)** con PyInstaller para distribución.
