# Cómo correr el bot todos los días (Windows)

Este bot scrapea Zonaprop y Remax con los filtros de `config.yaml`, guarda las
publicaciones nuevas en una base SQLite (`scrapdep.db`) y manda a Telegram solo
las que todavía no mandó.

> ⚠️ **Lo más importante:** el bot SIEMPRE tiene que correrse parado dentro de la
> carpeta `mudarme-bot`. La base de datos se guarda con ruta relativa
> (`scrapdep.db`), así que si lo corrés desde otra carpeta, Python crea una base
> nueva y vacía y te reenvía cosas que ya habías mandado. El archivo `run_daily.bat`
> se encarga de esto solo, por eso conviene usarlo.

---

## Opción A — A mano, cuando quieras (lo más simple)

1. Abrí el **Explorador de archivos** y entrá a la carpeta:
   `C:\Users\Muttdata\Documents\repos\mudarme-bot`
2. Hacé **doble clic** en `run_daily.bat`.

Se abre una ventana negra, corre una pasada y al terminar se cierra. Las
publicaciones nuevas te llegan al grupo de Telegram.

> Si querés ver qué pasó sin que se cierre la ventana: abrí PowerShell y corré
> el `.bat` desde ahí (ver Opción B), o agregá `pause` como última línea del `.bat`.

---

## Opción B — Desde la terminal (PowerShell)

```powershell
cd "C:\Users\Muttdata\Documents\repos\mudarme-bot"
.\run_daily.bat
```

Equivale a hacer (lo mismo, pero explícito):

```powershell
cd "C:\Users\Muttdata\Documents\repos\mudarme-bot"
.\venv\Scripts\python.exe main.py config.yaml
```

Ese `cd` del principio es la parte clave: te para dentro de `mudarme-bot` para que
use la base correcta.

---

## Opción C — Automático todos los días (Programador de tareas)

**Forma rápida:** doble clic en `programar_tarea_diaria.bat`. Crea la tarea
`mudarme-bot` que corre todos los días a las **12:00 y 20:00** (ventana
minimizada). Corre aunque la compu esté bloqueada, intenta despertarla si está
suspendida y, si estaba apagada, corre apenas se prende. Hacelo en **cada**
compu: como el estado está en la base compartida, nunca se duplican avisos.
Para cambiar horarios, editá `$Horas` en `scripts/programar_tarea_diaria.ps1`
y volvé a hacer doble clic.

**Forma manual** (si preferís hacerlo a mano):

Para que corra solo, sin que tengas que abrirlo, usá el **Programador de tareas**
de Windows (Task Scheduler).

1. Apretá la tecla **Windows**, escribí **"Programador de tareas"** y abrilo.
2. Panel derecho → **Crear tarea básica…**
3. **Nombre:** `mudarme-bot diario` → Siguiente.
4. **Desencadenador:** elegí **Diariamente** → Siguiente. Poné la hora que quieras
   (por ej. 09:00) → Siguiente.
5. **Acción:** elegí **Iniciar un programa** → Siguiente.
6. En **Programa o script** poné exactamente esta ruta (con comillas):

   ```
   "C:\Users\Muttdata\Documents\repos\mudarme-bot\run_daily.bat"
   ```

   Dejá vacíos "Agregar argumentos" e "Iniciar en". → Siguiente → **Finalizar**.

Listo. Todos los días a esa hora va a correr una pasada y mandarte lo nuevo.

> **Tip:** si querés que corra aunque no tengas la sesión iniciada, después de
> crearla: doble clic en la tarea → pestaña **General** → tildá
> **"Ejecutar tanto si el usuario inició sesión como si no"**.

### Probar la tarea sin esperar al día siguiente
En el Programador de tareas, buscá `mudarme-bot diario` en la lista, clic derecho →
**Ejecutar**. Tendría que abrirse (o correr en segundo plano) y mandarte lo nuevo.

---

## Notas sobre la configuración (`config.yaml`)

- **`pages: 1`** → cuántas páginas de resultados scrapea por sitio. Cada página
  trae ~24-30 publicaciones. Si querés mirar más profundo, subí el número
  (ej. `pages: 3`).
- **`persist: false`** → corre **una sola pasada** y termina. Es lo correcto para
  usar con el Programador de tareas (Opción C), porque el Programador se encarga
  de repetir. **Dejalo en `false`.**
  - (`persist: true` haría que el script quede corriendo en un loop infinito
    esperando `sleep_time` segundos entre vuelta y vuelta. Solo sirve si lo dejás
    abierto a mano; no lo uses junto con el Programador.)
- Las URLs (`zonaprop_full_url`, `remax_full_url`) ya tienen tus filtros. Si querés
  cambiar zona/precio/ambientes, generá la búsqueda nueva en cada sitio y reemplazá
  el número de página por `{}` en la URL.

## ¿Cómo sé que anduvo?
- Lo más directo: te llegan (o no) mensajes nuevos al grupo de Telegram.
- Si algún envío falla, queda registrado en `send_failures.log` dentro de la carpeta.
- La base `scrapdep.db` acumula todo lo ya visto/enviado; gracias a eso no se
  repiten publicaciones entre corridas.
