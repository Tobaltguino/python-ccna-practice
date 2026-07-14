"""
Examen - Cisco Networking Academy (versión Flet)
--------------------------------------------------
Reimplementación en Flet (Python) de la app original en Tkinter, pensada para
verse bien tanto en escritorio como en el celular (diseño responsivo).

CÓMO EJECUTAR
=============
1) Instala Flet (versión reciente):
       pip install "flet[all]"

2) Coloca este archivo en la MISMA carpeta donde tienes las carpetas:
       json/   -> con tus archivos .json de preguntas
       img/    -> con las imágenes referenciadas en las preguntas (opcional)

3) Ejecuta como app de escritorio:
       flet run examen_gui_flet.py

   O como app web (para probarla en el navegador del celular en tu misma red):
       flet run --web examen_gui_flet.py

4) Para verla en tu celular sin instalar nada, puedes instalar la app
   "Flet" (disponible en la App Store / Google Play) y usar
   `flet run` en modo web; o compilar un APK/IPA con `flet build apk` / `flet build ipa`.

La lógica de negocio (carga de JSON, mezcla de preguntas, evaluación,
modo práctica/examen, revisión, emparejamiento, etc.) es la misma que la
versión Tkinter original; sólo cambió la capa visual.
"""

import base64
import datetime
import json
import os
import random
import re
import threading
import time

import flet as ft

# --------------------------------------------------------------------------
# PALETA DE COLORES TIPO CISCO
# --------------------------------------------------------------------------
CISCO_NAVY = "#041424"
CISCO_BLUE = "#005073"
CISCO_CYAN = "#00bceb"
BG_WHITE = "#FFFFFF"
TEXT_DARK = "#333333"
TEXT_GRAY = "#666666"
SUCCESS_GREEN = "#6cc04a"
ERROR_RED = "#e2231a"
SKIPPED_YELLOW = "#ffcc00"

OPTION_BG = "#F5F6F8"
OPTION_SELECTED = "#00bceb"
OPTION_CIRCLE_IDLE = "#9AA0A6"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
JSON_DIR = os.path.join(BASE_DIR, "json")
IMG_DIR = os.path.join(BASE_DIR, "img")
HISTORY_FILE = os.path.join(BASE_DIR, "historial_puntajes.json")
TIEMPO_LIMITE_EXAMEN = 60 * 60  # 1 hora, en segundos, sólo para modo examen

# --------------------------------------------------------------------------
# PALETAS: MODO CLARO / MODO OSCURO
# --------------------------------------------------------------------------
PALETAS = {
    "light": {
        "bg": "#FFFFFF",
        "surface": "#FFFFFF",
        "text": "#333333",
        "text_gray": "#666666",
        "option_bg": "#F5F6F8",
        "idle_bg": "#e0e0e0",
        "correct_bg": "#e8f5e9",
        "incorrect_bg": "#ffebee",
        "heading": "#041424",
    },
    "dark": {
        "bg": "#0f1720",
        "surface": "#1b2530",
        "text": "#e6e6e6",
        "text_gray": "#a0a8b0",
        "option_bg": "#232e3a",
        "idle_bg": "#2a3540",
        "correct_bg": "#1e3d24",
        "incorrect_bg": "#3d1f1f",
        "heading": "#00bceb",
    },
}


# --------------------------------------------------------------------------
# APP
# --------------------------------------------------------------------------
class ExamenApp:
    def __init__(self, page: ft.Page):
        self.page = page
        page.title = "Examen - Cisco Networking Academy"
        page.padding = 0
        page.theme_mode = ft.ThemeMode.LIGHT
        page.scroll = None
        page.window.width = 1200
        page.window.height = 800
        page.window.min_width = 360
        page.window.min_height = 500

        # --- Estado de tema (claro/oscuro) ---
        self.C = PALETAS["light"]
        page.bgcolor = self.C["bg"]

        # --- Estado del examen (idéntico a la versión Tkinter) ---
        self.preguntas = []
        self.indice_actual = 0
        self.puntaje = 0
        self.estado_preguntas = {}
        self.modo = "practica"
        self.modulo_actual = None  # nombre del módulo cargado (para el historial)
        self._resultado_guardado = False
        self._comparacion_historial = (None, False)

        # --- Estado del temporizador (sólo aplica al modo examen) ---
        self.tiempo_inicio_intento = None
        self._timer_activo = False
        self._tiempo_agotado = False
        self._tiempo_final_segundos = 0
        self.timer_control = ft.Text("", size=13, weight=ft.FontWeight.BOLD, color=CISCO_CYAN)

        # --- Estado de selección "en vivo" de la pregunta actual ---
        self._selection_initialized_for = None
        self.var_multiple = set()
        self.var_single = -1
        self.dropdown_values = {}
        self.es_multiple = False

        # --- Estructura persistente de la página ---
        self.header = ft.Container(bgcolor=CISCO_NAVY, padding=ft.Padding.symmetric(horizontal=25, vertical=16))
        self.accent = ft.Container(height=4, bgcolor=CISCO_CYAN)
        self.body = ft.Column(expand=True, scroll=ft.ScrollMode.AUTO, spacing=14)

        page.add(
            ft.Column(
                [self.header, self.accent, ft.Container(self.body, expand=True, padding=ft.Padding.symmetric(horizontal=20, vertical=16))],
                expand=True,
                spacing=0,
            )
        )

        self.mostrar_menu()

    # ------------------------------------------------------------------
    # TEMA CLARO / OSCURO
    # ------------------------------------------------------------------
    def _preparar_tema(self, redibujar):
        """Recalcula la paleta activa y recuerda cómo redibujar la pantalla
        actual, para poder refrescarla al cambiar de tema."""
        es_oscuro = self.page.theme_mode == ft.ThemeMode.DARK
        self.C = PALETAS["dark"] if es_oscuro else PALETAS["light"]
        self.page.bgcolor = self.C["bg"]
        self._redibujar = redibujar

    def _alternar_tema(self, e=None):
        self.page.theme_mode = (
            ft.ThemeMode.LIGHT if self.page.theme_mode == ft.ThemeMode.DARK else ft.ThemeMode.DARK
        )
        if getattr(self, "_redibujar", None):
            self._redibujar()
        else:
            self.mostrar_menu()

    def _boton_tema(self):
        es_oscuro = self.page.theme_mode == ft.ThemeMode.DARK
        return ft.IconButton(
            icon=ft.Icons.LIGHT_MODE if es_oscuro else ft.Icons.DARK_MODE,
            icon_color=BG_WHITE,
            tooltip="Cambiar a modo claro" if es_oscuro else "Cambiar a modo oscuro",
            on_click=self._alternar_tema,
        )

    # ------------------------------------------------------------------
    # UTILIDADES
    # ------------------------------------------------------------------
    def _abrir_overlay(self, control):
        """Muestra un AlertDialog/SnackBar siendo compatible con varias versiones de Flet
        (algunas usan page.open(), otras page.show_dialog(), y las más antiguas
        page.dialog = control; control.open = True)."""
        page = self.page
        for metodo in ("show_dialog", "open"):
            fn = getattr(page, metodo, None)
            if fn:
                try:
                    fn(control)
                    return
                except Exception:
                    pass
        page.dialog = control
        control.open = True
        page.update()

    def _cerrar_overlay(self, control):
        page = self.page
        fn = getattr(page, "pop_dialog", None)
        if fn:
            try:
                fn()
                return
            except Exception:
                pass
        fn = getattr(page, "close", None)
        if fn:
            try:
                fn(control)
                return
            except Exception:
                pass
        control.open = False
        page.update()

    def _snack(self, texto, color=ERROR_RED):
        snack = ft.SnackBar(content=ft.Text(texto, color=BG_WHITE), bgcolor=color)
        self._abrir_overlay(snack)

    def _header_row(self, titulo, subtitulo_texto=None, subtitulo_color=CISCO_CYAN,
                     texto_volver="Volver Atrás", on_volver=None, mostrar_volver=True):
        izquierda = [ft.Text(titulo, size=17, weight=ft.FontWeight.BOLD, color=BG_WHITE)]
        if subtitulo_texto:
            izquierda.append(ft.Text(subtitulo_texto, size=12, weight=ft.FontWeight.BOLD, color=subtitulo_color))
        controles = [ft.Row(izquierda, wrap=True, spacing=16, run_spacing=4)]
        if mostrar_volver:
            controles.append(
                ft.TextButton(
                    texto_volver,
                    icon=ft.Icons.ARROW_BACK,
                    on_click=on_volver or (lambda e: self.mostrar_menu()),
                    style=ft.ButtonStyle(color=BG_WHITE),
                )
            )
        derecha = ft.Row(
            ([controles[1]] if mostrar_volver else []) + [self._boton_tema()],
            alignment=ft.MainAxisAlignment.END,
            spacing=4,
        )
        self.header.content = ft.ResponsiveRow(
            [
                ft.Container(controles[0], col={"xs": 12, "sm": 8}),
                ft.Container(derecha, col={"xs": 12, "sm": 4}, alignment=ft.Alignment.CENTER_RIGHT),
            ],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

    def _buscar_imagen(self, nombre_imagen):
        if not os.path.exists(IMG_DIR):
            return None
        for root_dir, _, files in os.walk(IMG_DIR):
            if nombre_imagen in files:
                return os.path.join(root_dir, nombre_imagen)
        return None

    def _imagen_base64(self, ruta):
        try:
            with open(ruta, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("utf-8")
            ext = os.path.splitext(ruta)[1].lower()
            mime = {
                ".png": "image/png",
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".gif": "image/gif",
                ".webp": "image/webp",
                ".bmp": "image/bmp",
                ".svg": "image/svg+xml",
            }.get(ext, "image/png")
            return f"data:{mime};base64,{b64}"
        except Exception:
            return None

    # ------------------------------------------------------------------
    # HISTORIAL DE PUNTAJES (persistido en JSON)
    # ------------------------------------------------------------------
    def _leer_historial(self):
        if not os.path.exists(HISTORY_FILE):
            return {}
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            self._snack(f"No se pudo leer el historial: {e}")
            return {}

    def _guardar_historial(self, modulo, modo, puntaje, total, tiempo_segundos=0):
        """Agrega un intento al historial y devuelve (comparacion, es_record_nuevo)
        comparando contra el intento anterior y el mejor puntaje histórico."""
        porcentaje = round((puntaje / total) * 100, 1) if total else 0.0
        historial = self._leer_historial()
        historial.setdefault(modulo, {}).setdefault(modo, [])
        intentos_previos = historial[modulo][modo]

        comparacion = None
        if intentos_previos:
            anterior = intentos_previos[-1]
            comparacion = {
                "porcentaje_anterior": anterior["porcentaje"],
                "diferencia": round(porcentaje - anterior["porcentaje"], 1),
            }

        mejor_anterior = max((a["porcentaje"] for a in intentos_previos), default=None)
        es_record_nuevo = mejor_anterior is None or porcentaje > mejor_anterior

        intentos_previos.append({
            "fecha": datetime.datetime.now().strftime("%d-%m-%Y %H:%M"),
            "puntaje": puntaje,
            "total": total,
            "porcentaje": porcentaje,
            "tiempo": self._formatear_duracion(tiempo_segundos),
            "tiempo_segundos": round(tiempo_segundos),
        })

        try:
            with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump(historial, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self._snack(f"No se pudo guardar el historial: {e}")

        return comparacion, es_record_nuevo

    # ------------------------------------------------------------------
    # TEMPORIZADOR DEL MODO EXAMEN (límite de 1 hora)
    # ------------------------------------------------------------------
    def _formatear_duracion(self, segundos):
        segundos = max(0, int(segundos))
        horas, resto = divmod(segundos, 3600)
        mins, secs = divmod(resto, 60)
        if horas:
            return f"{horas}h {mins:02d}m {secs:02d}s"
        return f"{mins:02d}:{secs:02d}"

    def _detener_temporizador(self):
        self._timer_activo = False

    def _iniciar_temporizador_examen(self):
        self._detener_temporizador()
        self._timer_activo = True

        def loop():
            while self._timer_activo:
                transcurrido = time.time() - self.tiempo_inicio_intento
                restante = TIEMPO_LIMITE_EXAMEN - transcurrido
                if not self._timer_activo:
                    break
                self.timer_control.value = f"⏱ Tiempo restante: {self._formatear_duracion(restante)}"
                self.timer_control.color = ERROR_RED if restante <= 300 else CISCO_CYAN
                try:
                    self.page.update()
                except Exception:
                    pass
                if restante <= 0:
                    self._timer_activo = False
                    self._finalizar_examen_por_tiempo()
                    break
                time.sleep(1)

        threading.Thread(target=loop, daemon=True).start()

    def _finalizar_examen_por_tiempo(self):
        self._tiempo_agotado = True
        try:
            self.guardar_respuesta_silenciosa()
        except Exception:
            pass
        self.evaluar_examen_completo()
        self.mostrar_resultados()

    def cargar_preguntas(self, ruta_archivo):
        try:
            with open(ruta_archivo, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            self._snack(f"No se pudo cargar el archivo: {e}")
            return []

    # ------------------------------------------------------------------
    # PANTALLA: MENÚ PRINCIPAL
    # ------------------------------------------------------------------
    def mostrar_menu(self):
        self._preparar_tema(self.mostrar_menu)
        self._detener_temporizador()
        self._header_row("Cisco Networking Academy - Módulos", mostrar_volver=False)

        contenido = [
            ft.Text("Selecciona el módulo a evaluar:", size=20, weight=ft.FontWeight.BOLD, color=self.C["heading"]),
            ft.Button(
                content=ft.Row(
                    [ft.Icon(ft.Icons.HISTORY, color=BG_WHITE), ft.Text("Ver historial de puntajes", size=14, weight=ft.FontWeight.BOLD, color=BG_WHITE)],
                    alignment=ft.MainAxisAlignment.CENTER,
                ),
                bgcolor=CISCO_CYAN,
                height=48,
                on_click=lambda e: self.mostrar_historial(),
            ),
        ]

        if not os.path.exists(JSON_DIR):
            contenido.append(
                ft.Text("Error: no se encontró la carpeta 'json' junto a este script.", color=ERROR_RED, size=14)
            )
        else:
            archivos_json = sorted(f for f in os.listdir(JSON_DIR) if f.endswith(".json"))
            if not archivos_json:
                contenido.append(ft.Text("No hay archivos .json dentro de la carpeta 'json'.", color=ERROR_RED, size=14))
            else:
                for archivo in archivos_json:
                    nombre_limpio = archivo.replace(".json", "").upper()
                    contenido.append(
                        ft.Button(
                            content=ft.Row(
                                [ft.Icon(ft.Icons.FOLDER, color=BG_WHITE), ft.Text(nombre_limpio, size=15, weight=ft.FontWeight.BOLD, color=BG_WHITE)],
                                alignment=ft.MainAxisAlignment.CENTER,
                            ),
                            bgcolor=CISCO_BLUE,
                            height=56,
                            on_click=lambda e, a=archivo: self.mostrar_opciones_modo(a),
                        )
                    )

        self.body.controls = contenido
        self.page.update()

    # ------------------------------------------------------------------
    # PANTALLA: SELECCIÓN DE MODO
    # ------------------------------------------------------------------
    def mostrar_opciones_modo(self, archivo):
        self._preparar_tema(lambda: self.mostrar_opciones_modo(archivo))
        self._header_row("Configuración de Evaluación", on_volver=lambda e: self.mostrar_menu())

        nombre_limpio = archivo.replace(".json", "").upper()
        self.body.controls = [
            ft.Text(f"Módulo: {nombre_limpio}", size=20, weight=ft.FontWeight.BOLD, color=self.C["heading"]),
            ft.Text("Por favor, selecciona el modo de evaluación:", size=14, color=self.C["text_gray"]),
            ft.Button(
                content=ft.Column(
                    [
                        ft.Text("📝 MODO PRÁCTICA", size=15, weight=ft.FontWeight.BOLD, color=BG_WHITE),
                        ft.Text("(Todas las preguntas con retroalimentación inmediata)", size=11, color=BG_WHITE),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=2,
                ),
                bgcolor=CISCO_BLUE,
                height=70,
                on_click=lambda e: self.iniciar_examen(os.path.join(JSON_DIR, archivo), "practica"),
            ),
            ft.Button(
                content=ft.Column(
                    [
                        ft.Text("⏱️ MODO EXAMEN", size=15, weight=ft.FontWeight.BOLD, color=BG_WHITE),
                        ft.Text("(35 preguntas, prioridad a emparejamiento, tiempo límite de 1 hora)", size=11, color=BG_WHITE),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=2,
                ),
                bgcolor="#003554",
                height=70,
                on_click=lambda e: self.iniciar_examen(os.path.join(JSON_DIR, archivo), "examen"),
            ),
        ]
        self.page.update()

    # ------------------------------------------------------------------
    # INICIO DE EXAMEN / CARGA Y MEZCLA DE PREGUNTAS (igual que Tkinter)
    # ------------------------------------------------------------------
    def iniciar_examen(self, ruta_archivo, modo):
        self.modo = modo
        self.modulo_actual = os.path.basename(ruta_archivo).replace(".json", "").upper()
        todas_las_preguntas = self.cargar_preguntas(ruta_archivo)
        if not todas_las_preguntas:
            return

        if self.modo == "examen":
            emparejamientos = [q for q in todas_las_preguntas if q.get("tipo") == "emparejamiento"]
            opciones_mult = [q for q in todas_las_preguntas if q.get("tipo") != "emparejamiento"]

            random.shuffle(emparejamientos)
            random.shuffle(opciones_mult)

            preguntas_seleccionadas = emparejamientos[:35]
            faltantes = 35 - len(preguntas_seleccionadas)
            if faltantes > 0:
                preguntas_seleccionadas += opciones_mult[:faltantes]

            self.preguntas = preguntas_seleccionadas
            random.shuffle(self.preguntas)
        else:
            self.preguntas = list(todas_las_preguntas)

        for q in self.preguntas:
            tipo_pregunta = q.get("tipo", "opcion_multiple")
            if tipo_pregunta == "opcion_multiple":
                opciones_originales = list(q.get("opciones", []))
                respuestas_correctas_originales = q.get("respuestas_correctas", [])

                opciones_mezcladas = list(opciones_originales)
                random.shuffle(opciones_mezcladas)
                q["opciones"] = opciones_mezcladas

                nuevas_respuestas_correctas = []
                for old_idx in respuestas_correctas_originales:
                    texto_correcto = opciones_originales[old_idx]
                    nuevo_idx = opciones_mezcladas.index(texto_correcto)
                    nuevas_respuestas_correctas.append(nuevo_idx)
                q["respuestas_correctas"] = nuevas_respuestas_correctas

            elif tipo_pregunta == "emparejamiento":
                if "opciones" in q:
                    random.shuffle(q["opciones"])
                if "objetivos" in q:
                    random.shuffle(q["objetivos"])

        self.indice_actual = 0
        self.puntaje = 0
        self.estado_preguntas = {}
        self._selection_initialized_for = None
        self._resultado_guardado = False
        self._comparacion_historial = (None, False)
        self._tiempo_agotado = False
        self.tiempo_inicio_intento = time.time()
        self._detener_temporizador()
        if self.modo == "examen":
            self._iniciar_temporizador_examen()

        self.mostrar_pregunta()

    def iniciar_revision(self):
        self.modo = "revision"
        self.indice_actual = 0
        self._selection_initialized_for = None
        self.mostrar_pregunta()

    # ------------------------------------------------------------------
    # ESTADO DE SELECCIÓN ACTUAL
    # ------------------------------------------------------------------
    def _inicializar_seleccion_si_hace_falta(self, q, tipo_pregunta):
        if self._selection_initialized_for == self.indice_actual:
            return
        estado = self.estado_preguntas.get(self.indice_actual, {})
        sel = estado.get("seleccion_usuario")

        self.var_multiple = set()
        self.var_single = -1
        self.dropdown_values = {}

        if tipo_pregunta == "emparejamiento":
            objetivos = q.get("objetivos", [])
            self.dropdown_values = {obj: None for obj in objetivos}
            if sel:
                for obj, val in sel.items():
                    if val and val != "Seleccione...":
                        self.dropdown_values[obj] = val
        else:
            self.es_multiple = len(q.get("respuestas_correctas", [])) > 1
            if sel:
                if self.es_multiple:
                    self.var_multiple = set(sel)
                else:
                    if sel and sel[0] != -1:
                        self.var_single = sel[0]

        self._selection_initialized_for = self.indice_actual

    def obtener_seleccion_actual(self, q, tipo_pregunta):
        if tipo_pregunta == "emparejamiento":
            return dict(self.dropdown_values)
        else:
            if self.es_multiple:
                return sorted(self.var_multiple)
            else:
                return [self.var_single] if self.var_single != -1 else []

    def determinar_si_tiene_respuesta(self, seleccion):
        if isinstance(seleccion, dict):
            return any(v not in (None, "", "Seleccione...") for v in seleccion.values())
        elif isinstance(seleccion, list):
            return len(seleccion) > 0 and seleccion[0] != -1
        return False

    def guardar_respuesta_silenciosa(self, forzar_estado=None):
        if self.modo == "revision":
            return

        q = self.preguntas[self.indice_actual]
        tipo_pregunta = q.get("tipo", "opcion_multiple")
        seleccion_usuario = self.obtener_seleccion_actual(q, tipo_pregunta)
        tiene_respuesta = self.determinar_si_tiene_respuesta(seleccion_usuario)
        estado_calc = "respondida" if tiene_respuesta else "sin_responder"
        if forzar_estado:
            estado_calc = forzar_estado

        estado_anterior = self.estado_preguntas.get(self.indice_actual, {})
        if self.modo == "practica" and estado_anterior.get("estado") == "respondida":
            estado_calc = "respondida"

        self.estado_preguntas[self.indice_actual] = {
            "seleccion_usuario": seleccion_usuario,
            "estado": estado_calc,
            "feedback_texto": estado_anterior.get("feedback_texto", ""),
            "color_feedback": estado_anterior.get("color_feedback", ""),
            "es_correcta": estado_anterior.get("es_correcta", False),
        }

    def evaluar_pregunta(self, indice):
        q = self.preguntas[indice]
        tipo = q.get("tipo", "opcion_multiple")
        estado = self.estado_preguntas.get(indice, {})
        sel = estado.get("seleccion_usuario")

        es_correcta = False
        feedback_texto = ""
        color = ""
        correctas_q = q.get("respuestas_correctas")

        fue_omitida = not sel or not self.determinar_si_tiene_respuesta(sel)

        if tipo == "emparejamiento":
            todas_correctas = True
            correctas_agrupadas, usuario_agrupadas = {}, {}

            for obj, correcta in correctas_q.items():
                base_obj = re.sub(r"\s*\(\d+\)$", "", obj).strip()
                correctas_agrupadas.setdefault(base_obj, []).append(correcta)

            if not fue_omitida:
                for obj, seleccion in sel.items():
                    base_obj = re.sub(r"\s*\(\d+\)$", "", obj).strip()
                    usuario_agrupadas.setdefault(base_obj, []).append(seleccion)

                for base_obj in correctas_agrupadas:
                    if sorted(correctas_agrupadas[base_obj]) != sorted(usuario_agrupadas.get(base_obj, [])):
                        todas_correctas = False
                        break
            else:
                todas_correctas = False

            if todas_correctas and not fue_omitida:
                es_correcta = True
                feedback_texto = "✔️ ¡Correcto! Has emparejado todo de forma perfecta."
                color = SUCCESS_GREEN
            else:
                texto_corr = "\n".join([f"• {k}: {v}" for k, v in correctas_q.items()])
                if fue_omitida:
                    feedback_texto = f"❌ Omitida. Las respuestas correctas eran:\n\n{texto_corr}"
                else:
                    feedback_texto = f"❌ Incorrecto. Las respuestas correctas eran:\n\n{texto_corr}"
                color = ERROR_RED
        else:
            if not fue_omitida and sorted(sel) == sorted(correctas_q):
                es_correcta = True
                feedback_texto = "✔️ ¡Correcto!"
                color = SUCCESS_GREEN
            else:
                correctas_texto = "\n".join([f"• {q['opciones'][i]}" for i in correctas_q])
                if fue_omitida:
                    feedback_texto = f"❌ Omitida. La respuesta correcta era:\n{correctas_texto}"
                else:
                    feedback_texto = f"❌ Incorrecto. La respuesta correcta era:\n{correctas_texto}"
                color = ERROR_RED

        if q.get("explicacion"):
            feedback_texto += f"\n\n💡 Explicación:\n{q['explicacion']}"

        estado["es_correcta"] = es_correcta
        estado["feedback_texto"] = feedback_texto
        estado["color_feedback"] = color
        self.estado_preguntas[indice] = estado

    # ------------------------------------------------------------------
    # NAVEGACIÓN
    # ------------------------------------------------------------------
    def ir_a_pregunta(self, indice_destino):
        self.guardar_respuesta_silenciosa()
        self.indice_actual = indice_destino
        self._selection_initialized_for = None
        self.mostrar_pregunta()

    def omitir_pregunta(self, e=None):
        self.guardar_respuesta_silenciosa(forzar_estado="omitida")
        self._avanzar_indice()

    def _avanzar_indice(self):
        if self.indice_actual < len(self.preguntas) - 1:
            self.indice_actual += 1
            self._selection_initialized_for = None
            self.mostrar_pregunta()
        else:
            if self.modo == "examen":
                self.confirmar_finalizacion_examen()
            else:
                self.mostrar_resultados()

    def pregunta_anterior(self, e=None):
        self.guardar_respuesta_silenciosa()
        if self.indice_actual > 0:
            self.indice_actual -= 1
            self._selection_initialized_for = None
            self.mostrar_pregunta()

    def siguiente_pregunta(self, e=None):
        self.guardar_respuesta_silenciosa()
        self._avanzar_indice()

    def verificar_respuesta(self, e=None):
        q = self.preguntas[self.indice_actual]
        tipo_pregunta = q.get("tipo", "opcion_multiple")
        seleccion_guardar = self.obtener_seleccion_actual(q, tipo_pregunta)

        if not self.determinar_si_tiene_respuesta(seleccion_guardar):
            self._snack("Por favor seleccione al menos una opción antes de confirmar.", ERROR_RED)
            return

        if tipo_pregunta == "emparejamiento":
            if any(val in (None, "", "Seleccione...") for val in seleccion_guardar.values()):
                self._snack("Por favor asigne una opción a todos los objetivos antes de confirmar.", ERROR_RED)
                return
        else:
            resp_corr = q["respuestas_correctas"]
            if self.es_multiple and len(seleccion_guardar) != len(resp_corr):
                self._snack(f"Esta pregunta requiere exactamente {len(resp_corr)} respuestas.", ERROR_RED)
                return

        estado = self.estado_preguntas.get(self.indice_actual, {})
        estado["seleccion_usuario"] = seleccion_guardar
        estado["estado"] = "respondida"
        self.estado_preguntas[self.indice_actual] = estado

        self.evaluar_pregunta(self.indice_actual)
        self.mostrar_pregunta()

    def confirmar_finalizacion_examen(self):
        respondidas = sum(1 for e in self.estado_preguntas.values() if e.get("estado") == "respondida")
        faltantes = len(self.preguntas) - respondidas

        if faltantes > 0:
            dlg = ft.AlertDialog(
                modal=True,
                title=ft.Text("Atención"),
                content=ft.Text(
                    f"Te faltan {faltantes} preguntas por responder u omitidas.\n\n"
                    "¿Estás seguro de que deseas finalizar y evaluar el examen ahora?"
                ),
                actions=[
                    ft.TextButton("Cancelar", on_click=lambda e: self._cerrar_overlay(dlg)),
                    ft.TextButton(
                        "Finalizar",
                        on_click=lambda e: (self._cerrar_overlay(dlg), self._finalizar_examen_ahora()),
                    ),
                ],
                actions_alignment=ft.MainAxisAlignment.END,
            )
            self._abrir_overlay(dlg)
        else:
            self._finalizar_examen_ahora()

    def _finalizar_examen_ahora(self):
        self._detener_temporizador()
        self.evaluar_examen_completo()
        self.mostrar_resultados()

    def evaluar_examen_completo(self):
        self.puntaje = 0
        for i in range(len(self.preguntas)):
            self.evaluar_pregunta(i)
            if self.estado_preguntas[i].get("es_correcta"):
                self.puntaje += 1

    # ------------------------------------------------------------------
    # CONSTRUCCIÓN DE TARJETAS DE OPCIÓN / EMPAREJAMIENTO
    # ------------------------------------------------------------------
    def _crear_opcion_card(self, indice, texto, multiple, bloqueada, resultado=None):
        seleccionado = (indice in self.var_multiple) if multiple else (self.var_single == indice)

        bg = self.C["option_bg"]
        fg = self.C["text"]
        icon_color = OPTION_CIRCLE_IDLE

        if resultado is not None:
            estado_idx = resultado.get(indice)
            if estado_idx is True:
                bg, fg, icon_color = SUCCESS_GREEN, BG_WHITE, BG_WHITE
                seleccionado = True
            elif estado_idx is False:
                bg, fg, icon_color = ERROR_RED, BG_WHITE, BG_WHITE
                seleccionado = True
            else:
                seleccionado = False
        elif seleccionado:
            bg, fg, icon_color = OPTION_SELECTED, BG_WHITE, BG_WHITE

        if multiple:
            icon_name = ft.Icons.CHECK_BOX if seleccionado else ft.Icons.CHECK_BOX_OUTLINE_BLANK
        else:
            icon_name = ft.Icons.RADIO_BUTTON_CHECKED if seleccionado else ft.Icons.RADIO_BUTTON_UNCHECKED

        return ft.Container(
            content=ft.Row(
                [
                    ft.Icon(icon_name, color=icon_color, size=22),
                    ft.Text(texto, size=14, color=fg, expand=True),
                ],
                spacing=14,
                vertical_alignment=ft.CrossAxisAlignment.START,
            ),
            bgcolor=bg,
            border_radius=8,
            padding=ft.Padding.symmetric(horizontal=18, vertical=12),
            ink=not bloqueada,
            on_click=(None if bloqueada else (lambda e, idx=indice: self._on_opcion_click(idx, multiple))),
        )

    def _on_opcion_click(self, idx, multiple):
        if multiple:
            if idx in self.var_multiple:
                self.var_multiple.remove(idx)
            else:
                self.var_multiple.add(idx)
        else:
            self.var_single = idx
        self.mostrar_pregunta()

    def _crear_fila_emparejamiento(self, obj, opciones_valores, bloqueada, resultado=None):
        valor_actual = self.dropdown_values.get(obj)

        bg, fg = self.C["option_bg"], self.C["text"]
        if resultado is True:
            bg, fg = SUCCESS_GREEN, BG_WHITE
        elif resultado is False:
            bg, fg = ERROR_RED, BG_WHITE
        elif valor_actual:
            bg, fg = OPTION_SELECTED, BG_WHITE

        dd = ft.Dropdown(
            value=valor_actual,
            options=[ft.DropdownOption(key=o, text=o) for o in opciones_valores],
            disabled=bloqueada,
            expand=True,
            hint_text="Seleccione...",
            bgcolor=self.C["surface"],
            content_padding=ft.Padding.symmetric(horizontal=10, vertical=6),
            on_select=lambda e, o=obj: self._on_dropdown_change(o, e.control.value),
        )

        return ft.Container(
            content=ft.ResponsiveRow(
                [
                    ft.Container(ft.Text(obj, size=13, weight=ft.FontWeight.BOLD, color=fg), col={"xs": 12, "sm": 5}),
                    ft.Container(dd, col={"xs": 12, "sm": 7}),
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            bgcolor=bg,
            border_radius=8,
            padding=ft.Padding.symmetric(horizontal=16, vertical=10),
        )

    def _on_dropdown_change(self, obj, valor):
        self.dropdown_values[obj] = valor
        self.mostrar_pregunta()

    # ------------------------------------------------------------------
    # PANTALLA: PREGUNTA (práctica / examen / revisión)
    # ------------------------------------------------------------------
    def mostrar_pregunta(self):
        self._preparar_tema(self.mostrar_pregunta)
        q = self.preguntas[self.indice_actual]
        tipo_pregunta = q.get("tipo", "opcion_multiple")

        self._inicializar_seleccion_si_hace_falta(q, tipo_pregunta)

        modo_texto = {"examen": "MODO EXAMEN", "practica": "MODO PRÁCTICA", "revision": "REVISIÓN DEL EXAMEN"}[self.modo]
        self._header_row(
            "Cisco Networking Academy",
            subtitulo_texto=modo_texto,
            texto_volver="Abandonar",
            on_volver=lambda e: self.mostrar_menu(),
        )

        estado = self.estado_preguntas.get(self.indice_actual, {})
        sel = estado.get("seleccion_usuario")
        esta_bloqueada = self.modo == "revision" or (self.modo == "practica" and estado.get("estado") == "respondida")

        # --- Panel de navegación (envuelve automáticamente -> responsivo) ---
        nav_botones = []
        for i in range(len(self.preguntas)):
            est_i = self.estado_preguntas.get(i, {})
            status = est_i.get("estado", "sin_responder")
            es_correcta_i = est_i.get("es_correcta")

            bg_nav, fg_nav = self.C["idle_bg"], self.C["text"]
            if self.modo == "revision" or (self.modo == "practica" and status == "respondida"):
                if es_correcta_i is True:
                    bg_nav, fg_nav = SUCCESS_GREEN, BG_WHITE
                elif es_correcta_i is False:
                    bg_nav, fg_nav = ERROR_RED, BG_WHITE
            else:
                if status == "respondida":
                    bg_nav, fg_nav = SUCCESS_GREEN, BG_WHITE
                elif status == "omitida":
                    bg_nav, fg_nav = SKIPPED_YELLOW, TEXT_DARK

            es_actual = i == self.indice_actual
            nav_botones.append(
                ft.Container(
                    content=ft.Text(str(i + 1), size=12, weight=ft.FontWeight.BOLD, color=BG_WHITE if es_actual else fg_nav),
                    bgcolor=CISCO_CYAN if es_actual else bg_nav,
                    width=32,
                    height=32,
                    border_radius=6,
                    alignment=ft.Alignment.CENTER,
                    border=ft.Border.all(2, self.C["heading"]) if es_actual else None,
                    on_click=lambda e, idx=i: self.ir_a_pregunta(idx),
                )
            )

        elementos = [
            ft.Row(nav_botones, wrap=True, spacing=6, run_spacing=6),
            ft.Text(f"Pregunta {self.indice_actual + 1} de {len(self.preguntas)}", size=13, weight=ft.FontWeight.BOLD, color=CISCO_CYAN),
        ]

        if self.modo == "examen" and self.tiempo_inicio_intento:
            restante = TIEMPO_LIMITE_EXAMEN - (time.time() - self.tiempo_inicio_intento)
            self.timer_control.value = f"⏱ Tiempo restante: {self._formatear_duracion(restante)}"
            self.timer_control.color = ERROR_RED if restante <= 300 else CISCO_CYAN
            elementos.append(self.timer_control)

        elementos.append(ft.Text(q["pregunta"], size=15, color=self.C["text"]))

        # --- Imagen (si aplica) ---
        nombre_imagen = q.get("imagen")
        if nombre_imagen:
            ruta_imagen = self._buscar_imagen(nombre_imagen)
            if ruta_imagen:
                b64 = self._imagen_base64(ruta_imagen)
                if b64:
                    elementos.append(
                        ft.Image(src=b64, fit=ft.BoxFit.CONTAIN, height=300, border_radius=8)
                    )
                else:
                    elementos.append(ft.Text(f"[Error al cargar la imagen: {nombre_imagen}]", color=ERROR_RED))
            else:
                elementos.append(ft.Text(f"[Archivo no encontrado: '{nombre_imagen}']", color=ERROR_RED))

        # --- Opciones / Emparejamiento ---
        if tipo_pregunta == "emparejamiento":
            opciones_emp = q.get("opciones", [])
            objetivos_emp = q.get("objetivos", [])
            respuestas_correctas_map = q.get("respuestas_correctas", {})

            seleccionadas = [v for v in self.dropdown_values.values() if v not in (None, "", "Seleccione...")]
            disponibles = [o for o in opciones_emp if seleccionadas.count(o) == 0]

            filas = []
            for obj in objetivos_emp:
                resultado_fila = None
                if esta_bloqueada:
                    correcta_obj = respuestas_correctas_map.get(obj)
                    valor_usuario = sel.get(obj) if sel else None
                    resultado_fila = valor_usuario is not None and valor_usuario == correcta_obj
                filas.append(self._crear_fila_emparejamiento(obj, opciones_emp, esta_bloqueada, resultado=resultado_fila))

            panel_disponibles = ft.Column(
                [ft.Text("Opciones a colocar:", size=13, weight=ft.FontWeight.BOLD, color=self.C["heading"])]
                + (
                    [ft.Container(ft.Text(o, size=12, color=self.C["text"]), bgcolor=self.C["option_bg"], border_radius=6,
                                  padding=ft.Padding.symmetric(horizontal=12, vertical=8)) for o in disponibles]
                    if disponibles
                    else [ft.Text("(Todas las opciones han sido asignadas)", size=11, italic=True, color=self.C["text_gray"])]
                ),
                spacing=6,
            )
            panel_objetivos = ft.Column([ft.Text("Objetivos:", size=13, weight=ft.FontWeight.BOLD, color=self.C["heading"])] + filas, spacing=8)

            elementos.append(
                ft.ResponsiveRow(
                    [
                        ft.Container(panel_disponibles, col={"xs": 12, "md": 4}),
                        ft.Container(panel_objetivos, col={"xs": 12, "md": 8}),
                    ]
                )
            )
        else:
            self.es_multiple = len(q.get("respuestas_correctas", [])) > 1
            if self.es_multiple:
                elementos.append(
                    ft.Text(f"(Seleccione {len(q['respuestas_correctas'])} opciones)", size=12, italic=True, color=self.C["text_gray"])
                )

            resultado_visual = None
            if esta_bloqueada:
                correctas_q = set(q.get("respuestas_correctas", []))
                seleccion_usuario = set(sel) if sel else set()
                resultado_visual = {}
                for idx in range(len(q.get("opciones", []))):
                    if idx in correctas_q:
                        resultado_visual[idx] = True
                    elif idx in seleccion_usuario:
                        resultado_visual[idx] = False
                    else:
                        resultado_visual[idx] = None

            tarjetas = []
            for i, opcion in enumerate(q.get("opciones", [])):
                tarjetas.append(
                    self._crear_opcion_card(i, opcion, self.es_multiple, esta_bloqueada, resultado=resultado_visual)
                )
            elementos.append(ft.Column(tarjetas, spacing=6))

        # --- Feedback ---
        if esta_bloqueada:
            color_fb = estado.get("color_feedback", self.C["surface"])
            elementos.append(
                ft.Container(
                    content=ft.Text(estado.get("feedback_texto", ""), size=13, color=BG_WHITE),
                    bgcolor=color_fb,
                    border_radius=8,
                    padding=14,
                )
            )

        # --- Botonera inferior ---
        btn_anterior = ft.Button(
            "⬅ Anterior",
            on_click=self.pregunta_anterior,
            disabled=(self.indice_actual == 0),
            bgcolor=CISCO_BLUE if self.indice_actual > 0 else self.C["idle_bg"],
            color=BG_WHITE if self.indice_actual > 0 else self.C["text_gray"],
        )

        botones_fila = [btn_anterior]

        if self.modo != "revision":
            botones_fila.append(
                ft.Button(
                    "Omitir ⏭",
                    on_click=self.omitir_pregunta,
                    bgcolor=SKIPPED_YELLOW if not esta_bloqueada else self.C["idle_bg"],
                    color=TEXT_DARK if not esta_bloqueada else self.C["text_gray"],
                    disabled=esta_bloqueada,
                )
            )

        if self.modo == "practica":
            botones_fila.append(
                ft.Button(
                    "Confirmar Respuesta",
                    on_click=self.verificar_respuesta,
                    bgcolor=CISCO_BLUE if not esta_bloqueada else self.C["idle_bg"],
                    color=BG_WHITE if not esta_bloqueada else self.C["text_gray"],
                    disabled=esta_bloqueada,
                )
            )

        texto_siguiente = "Siguiente ➔"
        bg_siguiente = CISCO_BLUE
        habilitar_siguiente = True
        if self.modo == "examen" and self.indice_actual == len(self.preguntas) - 1:
            texto_siguiente = "Finalizar Examen ➔"
            bg_siguiente = CISCO_CYAN
        elif self.modo == "revision" and self.indice_actual == len(self.preguntas) - 1:
            texto_siguiente = "Volver al Resumen ➔"
            bg_siguiente = CISCO_CYAN
        elif self.modo == "practica" and not esta_bloqueada:
            habilitar_siguiente = False
            bg_siguiente = self.C["idle_bg"]

        btn_siguiente = ft.Button(
            texto_siguiente,
            on_click=(self._volver_al_resumen if (self.modo == "revision" and self.indice_actual == len(self.preguntas) - 1) else self.siguiente_pregunta),
            bgcolor=bg_siguiente if habilitar_siguiente else self.C["idle_bg"],
            color=BG_WHITE if habilitar_siguiente else self.C["text_gray"],
            disabled=not habilitar_siguiente,
        )
        botones_fila.append(btn_siguiente)

        elementos.append(ft.Row(botones_fila, wrap=True, spacing=10, run_spacing=10))
        elementos.append(ft.Container(height=20))

        self.body.controls = elementos
        self.page.update()

    def _volver_al_resumen(self, e=None):
        self.mostrar_resultados()

    # ------------------------------------------------------------------
    # PANTALLA: RESULTADOS
    # ------------------------------------------------------------------
    def mostrar_resultados(self):
        self._preparar_tema(self.mostrar_resultados)
        self._detener_temporizador()
        if self.modo == "practica":
            self.evaluar_examen_completo()

        self._header_row("Resumen de Evaluación", mostrar_volver=False)

        porcentaje = (self.puntaje / len(self.preguntas)) * 100
        color_porcentaje = SUCCESS_GREEN if porcentaje >= 70 else ERROR_RED
        texto_aprobacion = "¡Aprobado!" if porcentaje >= 70 else "Requiere más estudio"

        if not self._resultado_guardado and self.modulo_actual and self.modo in ("practica", "examen"):
            self._tiempo_final_segundos = (
                time.time() - self.tiempo_inicio_intento if self.tiempo_inicio_intento else 0
            )
            self._comparacion_historial = self._guardar_historial(
                self.modulo_actual, self.modo, self.puntaje, len(self.preguntas), self._tiempo_final_segundos
            )
            self._resultado_guardado = True

        comparacion, es_record_nuevo = self._comparacion_historial
        progreso_texto, progreso_color = None, None
        if es_record_nuevo and comparacion:
            progreso_texto = (
                f"🏆 ¡Superaste tu intento anterior! ({comparacion['porcentaje_anterior']}% → {porcentaje:.1f}%)"
            )
            progreso_color = SUCCESS_GREEN
        elif es_record_nuevo:
            progreso_texto = "🏆 ¡Es tu primer intento registrado en este módulo!"
            progreso_color = CISCO_CYAN
        elif comparacion:
            diff = comparacion["diferencia"]
            if diff > 0:
                progreso_texto = f"📈 Mejoraste respecto a tu intento anterior (+{diff}%)"
                progreso_color = SUCCESS_GREEN
            elif diff < 0:
                progreso_texto = f"📉 Bajaste respecto a tu intento anterior ({diff}%)"
                progreso_color = ERROR_RED
            else:
                progreso_texto = "➖ Obtuviste el mismo resultado que tu intento anterior"
                progreso_color = self.C["text_gray"]

        elementos = [
            ft.Text("Resumen de Evaluación", size=24, weight=ft.FontWeight.BOLD, color=self.C["heading"]),
            ft.Container(
                content=ft.Column(
                    [
                        ft.Text(f"Puntaje Obtenido: {self.puntaje} de {len(self.preguntas)}", size=16, color=self.C["text"]),
                        ft.Text(f"Rendimiento: {porcentaje:.1f}%", size=22, weight=ft.FontWeight.BOLD, color=color_porcentaje),
                        ft.Text(texto_aprobacion, size=13, italic=True, color=self.C["text_gray"]),
                        ft.Text(
                            f"⏱ Tiempo utilizado: {self._formatear_duracion(getattr(self, '_tiempo_final_segundos', 0))}",
                            size=12, color=self.C["text_gray"],
                        ),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=6,
                ),
                border=ft.Border.all(2, CISCO_CYAN),
                border_radius=10,
                padding=20,
                alignment=ft.Alignment.CENTER,
            ),
        ]

        if self._tiempo_agotado:
            elementos.append(
                ft.Container(
                    content=ft.Text(
                        "⏰ Se acabó el tiempo (1 hora). El examen se finalizó y evaluó automáticamente.",
                        size=13, weight=ft.FontWeight.BOLD, color=BG_WHITE,
                    ),
                    bgcolor=ERROR_RED,
                    border_radius=8,
                    padding=12,
                    alignment=ft.Alignment.CENTER,
                )
            )

        if progreso_texto:
            elementos.append(
                ft.Container(
                    content=ft.Text(progreso_texto, size=14, weight=ft.FontWeight.BOLD, color=BG_WHITE),
                    bgcolor=progreso_color,
                    border_radius=8,
                    padding=12,
                    alignment=ft.Alignment.CENTER,
                )
            )

        elementos.append(ft.Text("Detalle de Preguntas", size=18, weight=ft.FontWeight.BOLD, color=self.C["heading"]))

        for i, q in enumerate(self.preguntas):
            estado = self.estado_preguntas.get(i, {})
            es_correcta = estado.get("es_correcta", False)
            respondida = estado.get("estado") == "respondida"

            if es_correcta:
                bg_card, fg_text, texto_estado = self.C["correct_bg"], SUCCESS_GREEN, "✔️ Correcta"
            else:
                bg_card, fg_text = self.C["incorrect_bg"], ERROR_RED
                texto_estado = "❌ Omitida (Incorrecta)" if not respondida else "❌ Incorrecta"

            elementos.append(
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Text(f"Pregunta {i + 1}: {q['pregunta']}", size=13, weight=ft.FontWeight.BOLD, color=self.C["text"]),
                            ft.Text(texto_estado, size=12, weight=ft.FontWeight.BOLD, color=fg_text),
                        ],
                        spacing=4,
                    ),
                    bgcolor=bg_card,
                    border=ft.Border.all(1, fg_text),
                    border_radius=6,
                    padding=12,
                )
            )

        elementos.append(
            ft.Row(
                [
                    ft.Button("Revisar Examen 🔍", bgcolor=CISCO_CYAN, color=BG_WHITE, on_click=lambda e: self.iniciar_revision()),
                    ft.Button("Ver Historial 📊", bgcolor=CISCO_BLUE, color=BG_WHITE, on_click=lambda e: self.mostrar_historial()),
                    ft.Button("Volver al Menú Principal", bgcolor=CISCO_NAVY, color=BG_WHITE, on_click=lambda e: self.mostrar_menu()),
                ],
                wrap=True,
                spacing=10,
                run_spacing=10,
            )
        )
        elementos.append(ft.Container(height=20))

        self.body.controls = elementos
        self.page.update()

    # ------------------------------------------------------------------
    # PANTALLA: HISTORIAL DE PUNTAJES
    # ------------------------------------------------------------------
    def mostrar_historial(self):
        self._preparar_tema(self.mostrar_historial)
        self._header_row("Historial de Puntajes", on_volver=lambda e: self.mostrar_menu())

        historial = self._leer_historial()

        elementos = [
            ft.Text("Historial de Puntajes", size=24, weight=ft.FontWeight.BOLD, color=self.C["heading"]),
            ft.Text(
                "Tu progreso se guarda automáticamente en historial_puntajes.json junto a este script.",
                size=12, italic=True, color=self.C["text_gray"],
            ),
        ]

        if not historial:
            elementos.append(
                ft.Text(
                    "Todavía no hay intentos registrados. ¡Realiza una práctica o examen para empezar tu historial!",
                    size=14, color=self.C["text_gray"],
                )
            )
        else:
            etiquetas_modo = {"practica": "📝 Práctica", "examen": "⏱️ Examen"}
            for modulo in sorted(historial.keys()):
                elementos.append(ft.Text(modulo, size=18, weight=ft.FontWeight.BOLD, color=self.C["heading"]))

                for modo_key, etiqueta in etiquetas_modo.items():
                    intentos = historial[modulo].get(modo_key, [])
                    if not intentos:
                        continue

                    mejor = max(a["porcentaje"] for a in intentos)
                    elementos.append(ft.Text(etiqueta, size=13, weight=ft.FontWeight.BOLD, color=self.C["text_gray"]))

                    filas = []
                    anterior_pct = None
                    for intento in intentos:
                        pct = intento["porcentaje"]
                        if anterior_pct is None:
                            icono = "🆕"
                        elif pct > anterior_pct:
                            icono = "📈"
                        elif pct < anterior_pct:
                            icono = "📉"
                        else:
                            icono = "➖"
                        anterior_pct = pct

                        color_pct = SUCCESS_GREEN if pct >= 70 else ERROR_RED
                        filas.append(
                            ft.Container(
                                content=ft.Row(
                                    [
                                        ft.Text(intento["fecha"], size=12, color=self.C["text_gray"], expand=True),
                                        ft.Text(f"{intento['puntaje']}/{intento['total']}", size=12, color=self.C["text"]),
                                        ft.Text(f"{pct:.1f}%", size=13, weight=ft.FontWeight.BOLD, color=color_pct),
                                        ft.Text(f"⏱ {intento.get('tiempo', '-')}", size=12, color=self.C["text_gray"]),
                                        ft.Text(icono, size=14),
                                        ft.Text("🏅" if pct == mejor else "", size=14, width=20),
                                    ],
                                    spacing=10,
                                ),
                                bgcolor=self.C["option_bg"],
                                border_radius=6,
                                padding=ft.Padding.symmetric(horizontal=14, vertical=8),
                            )
                        )
                    elementos.append(ft.Column(filas, spacing=4))

        elementos.append(ft.Container(height=10))
        elementos.append(
            ft.Row(
                [ft.Button("Volver al Menú Principal", bgcolor=CISCO_NAVY, color=BG_WHITE, on_click=lambda e: self.mostrar_menu())],
                wrap=True, spacing=10, run_spacing=10,
            )
        )
        elementos.append(ft.Container(height=20))

        self.body.controls = elementos
        self.page.update()


def main(page: ft.Page):
    ExamenApp(page)


if __name__ == "__main__":
    ft.run(main)