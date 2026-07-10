import tkinter as tk
from tkinter import ttk, messagebox
import json
import random
import os
import re

# Intentar importar Pillow para el manejo de imágenes
try:
    from PIL import Image, ImageTk
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

# --- PALETA DE COLORES TIPO CISCO ---
CISCO_NAVY = "#041424"      
CISCO_BLUE = "#005073"      
CISCO_CYAN = "#00bceb"      
BG_WHITE = "#FFFFFF"        
TEXT_DARK = "#333333"       
TEXT_GRAY = "#666666"       
SUCCESS_GREEN = "#6cc04a"   
ERROR_RED = "#e2231a"       
SKIPPED_YELLOW = "#ffcc00"  

# --- ESTILO DE TARJETAS DE OPCIÓN (tipo captura de referencia) ---
OPTION_BG = "#F5F6F8"        
OPTION_BG_LOCKED = "#F5F6F8" 
OPTION_SELECTED = "#00bceb"  
OPTION_CIRCLE_IDLE = "#9AA0A6"

class ExamenApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Examen - Cisco Networking Academy")
        self.root.configure(bg=BG_WHITE)

        # Maximizar la ventana para aprovechar toda la pantalla y minimizar el scroll
        try:
            self.root.state('zoomed')  # Windows y algunas distros de Linux
        except tk.TclError:
            try:
                self.root.attributes('-zoomed', True)  # Linux (algunos gestores de ventanas)
            except tk.TclError:
                ancho = self.root.winfo_screenwidth()
                alto = self.root.winfo_screenheight()
                self.root.geometry(f"{ancho}x{alto}+0+0")
        self.root.minsize(1100, 700)
        
        self.preguntas = []
        self.indice_actual = 0
        self.puntaje = 0
        self.imagen_actual = None 
        self.estado_preguntas = {} 
        self.modo = 'practica' 
        self.nav_buttons = [] 
        
        style = ttk.Style()
        style.theme_use('clam')
        self.style = style
        
        self.mostrar_menu()

    def mostrar_menu(self):
        for widget in self.root.winfo_children():
            widget.destroy()

        self.frame_header = tk.Frame(self.root, bg=CISCO_NAVY, height=80)
        self.frame_header.pack(side="top", fill="x")
        self.frame_header.pack_propagate(False) 
        
        lbl_titulo_app = tk.Label(self.frame_header, text="Cisco Networking Academy - Módulos", 
                                  font=("Segoe UI", 18, "bold"), bg=CISCO_NAVY, fg=BG_WHITE)
        lbl_titulo_app.pack(side="left", padx=30, pady=20)
        
        frame_acento = tk.Frame(self.root, bg=CISCO_CYAN, height=4)
        frame_acento.pack(fill="x")

        container = tk.Frame(self.root, bg=BG_WHITE, padx=40, pady=40)
        container.pack(fill="both", expand=True)

        tk.Label(container, text="Selecciona el módulo a evaluar:", font=("Segoe UI", 20, "bold"), bg=BG_WHITE, fg=CISCO_NAVY).pack(pady=(0, 30))

        if not os.path.exists("json"):
            tk.Label(container, text="Error: No se encontró la carpeta 'json' en el directorio principal.", 
                     font=("Segoe UI", 14), fg=ERROR_RED, bg=BG_WHITE).pack()
            return

        archivos_json = [f for f in os.listdir("json") if f.endswith('.json')]

        if not archivos_json:
            tk.Label(container, text="No hay archivos .json dentro de la carpeta 'json'.", 
                     font=("Segoe UI", 14), fg=ERROR_RED, bg=BG_WHITE).pack()
            return

        for archivo in archivos_json:
            nombre_limpio = archivo.replace(".json", "").upper()
            btn = tk.Button(container, text=f"📂 {nombre_limpio}", 
                            font=("Segoe UI", 14, "bold"), bg=CISCO_BLUE, fg=BG_WHITE, 
                            activebackground=CISCO_CYAN, activeforeground=BG_WHITE,
                            relief="flat", cursor="hand2", padx=20, pady=10,
                            command=lambda a=archivo: self.mostrar_opciones_modo(a))
            btn.pack(pady=10, fill="x")

    def mostrar_opciones_modo(self, archivo):
        for widget in self.root.winfo_children():
            widget.destroy()

        self.frame_header = tk.Frame(self.root, bg=CISCO_NAVY, height=80)
        self.frame_header.pack(side="top", fill="x")
        self.frame_header.pack_propagate(False) 
        
        lbl_titulo_app = tk.Label(self.frame_header, text="Configuración de Evaluación", 
                                  font=("Segoe UI", 18, "bold"), bg=CISCO_NAVY, fg=BG_WHITE)
        lbl_titulo_app.pack(side="left", padx=30, pady=20)
        
        btn_volver = tk.Button(self.frame_header, text="Volver Atrás", command=self.mostrar_menu,
                               font=("Segoe UI", 10, "bold"), bg="#555555", fg=BG_WHITE,
                               activebackground=ERROR_RED, relief="flat", cursor="hand2", padx=10)
        btn_volver.pack(side="right", padx=30, pady=25)
        
        frame_acento = tk.Frame(self.root, bg=CISCO_CYAN, height=4)
        frame_acento.pack(fill="x")

        container = tk.Frame(self.root, bg=BG_WHITE, padx=40, pady=40)
        container.pack(fill="both", expand=True)

        nombre_limpio = archivo.replace(".json", "").upper()
        tk.Label(container, text=f"Módulo: {nombre_limpio}", font=("Segoe UI", 20, "bold"), bg=BG_WHITE, fg=CISCO_NAVY).pack(pady=(0, 10))
        tk.Label(container, text="Por favor, selecciona el modo de evaluación:", font=("Segoe UI", 14), bg=BG_WHITE, fg=TEXT_GRAY).pack(pady=(0, 30))

        btn_practica = tk.Button(container, text="📝 MODO PRÁCTICA\n(Todas las preguntas con retroalimentación inmediata)", 
                            font=("Segoe UI", 14, "bold"), bg=CISCO_BLUE, fg=BG_WHITE, 
                            activebackground=CISCO_CYAN, activeforeground=BG_WHITE,
                            relief="flat", cursor="hand2", padx=20, pady=15,
                            command=lambda: self.iniciar_examen(os.path.join("json", archivo), 'practica'))
        btn_practica.pack(pady=10, fill="x")

        btn_examen = tk.Button(container, text="⏱️ MODO EXAMEN\n(35 preguntas, prioridad a conectar, evaluación al final)", 
                            font=("Segoe UI", 14, "bold"), bg="#003554", fg=BG_WHITE, 
                            activebackground=CISCO_CYAN, activeforeground=BG_WHITE,
                            relief="flat", cursor="hand2", padx=20, pady=15,
                            command=lambda: self.iniciar_examen(os.path.join("json", archivo), 'examen'))
        btn_examen.pack(pady=10, fill="x")

    def iniciar_examen(self, ruta_archivo, modo):
        self.modo = modo
        todas_las_preguntas = self.cargar_preguntas(ruta_archivo)
        if not todas_las_preguntas:
            return
            
        if self.modo == 'examen':
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
            self.preguntas = todas_las_preguntas
            random.shuffle(self.preguntas)

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

        for widget in self.root.winfo_children():
            widget.destroy()

        self.crear_interfaz()
        self.crear_elementos_pregunta()
        self.mostrar_pregunta()

    def iniciar_revision(self):
        self.modo = 'revision'
        self.indice_actual = 0
        self.crear_elementos_pregunta()
        self.mostrar_pregunta()

    def cargar_preguntas(self, ruta_archivo):
        try:
            with open(ruta_archivo, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            messagebox.showerror("Error Crítico", f"No se pudo cargar el archivo:\n{e}")
            return []

    def buscar_imagen(self, nombre_imagen):
        if not os.path.exists("img"):
            return None
        for root_dir, _, files in os.walk("img"):
            if nombre_imagen in files:
                return os.path.join(root_dir, nombre_imagen)
        return None

    def crear_interfaz(self):
        self.frame_header = tk.Frame(self.root, bg=CISCO_NAVY, height=64)
        self.frame_header.pack(side="top", fill="x")
        self.frame_header.pack_propagate(False) 
        
        lbl_titulo_app = tk.Label(self.frame_header, text="Cisco Networking Academy", 
                                  font=("Segoe UI", 16, "bold"), bg=CISCO_NAVY, fg=BG_WHITE)
        lbl_titulo_app.pack(side="left", padx=25, pady=14)

        modo_texto = "MODO EXAMEN" if self.modo == 'examen' else "MODO PRÁCTICA"
        self.lbl_modo_header = tk.Label(self.frame_header, text=modo_texto, font=("Segoe UI", 12, "bold"), bg=CISCO_NAVY, fg=CISCO_CYAN)
        self.lbl_modo_header.pack(side="left", padx=20, pady=18)

        btn_volver = tk.Button(self.frame_header, text="Abandonar", command=self.mostrar_menu,
                               font=("Segoe UI", 10, "bold"), bg="#555555", fg=BG_WHITE,
                               activebackground=ERROR_RED, relief="flat", cursor="hand2", padx=10)
        btn_volver.pack(side="right", padx=25, pady=18)
        
        frame_acento = tk.Frame(self.root, bg=CISCO_CYAN, height=3)
        frame_acento.pack(fill="x")
        
        self.scroll_container = tk.Frame(self.root, bg=BG_WHITE)
        self.scroll_container.pack(fill="both", expand=True)

        self.canvas = tk.Canvas(self.scroll_container, bg=BG_WHITE, highlightthickness=0)
        self.scrollbar = tk.Scrollbar(self.scroll_container, orient="vertical", command=self.canvas.yview)
        self.main_container = tk.Frame(self.canvas, bg=BG_WHITE, padx=35, pady=12)

        self.canvas_window = self.canvas.create_window((0, 0), window=self.main_container, anchor="nw")
        self.canvas.configure(yscrollcommand=self.scrollbar.set)

        self.canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")

        self.main_container.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", self._ajustar_ancho_canvas)
        self.root.bind_all("<MouseWheel>", self._on_mousewheel)

    def crear_elementos_pregunta(self):
        self.btn_omitir = None
        self.btn_confirmar = None
        for widget in self.main_container.winfo_children():
            widget.destroy()

        if self.modo == 'revision':
            self.lbl_modo_header.config(text="REVISIÓN DEL EXAMEN")

        # Calcula el ancho real disponible para adaptar columnas del panel de navegación
        # y el ancho de los textos (wraplength), y así aprovechar toda la pantalla.
        self.root.update_idletasks()
        ancho_ventana = self.root.winfo_width()
        if ancho_ventana < 300:
            ancho_ventana = self.root.winfo_screenwidth()
        self.ancho_contenido = max(750, ancho_ventana - 130)
        columnas_maximas = max(15, (ancho_ventana - 80) // 58)

        self.frame_nav = tk.Frame(self.main_container, bg=BG_WHITE)
        self.frame_nav.pack(fill="x", pady=(0, 12))
        
        self.nav_buttons = []
        for i in range(len(self.preguntas)):
            btn = tk.Button(self.frame_nav, text=str(i+1), width=3, font=("Segoe UI", 9, "bold"),
                            bg="#e0e0e0", fg=TEXT_DARK, relief="flat", cursor="hand2",
                            command=lambda idx=i: self.ir_a_pregunta(idx))
            btn.grid(row=i // columnas_maximas, column=i % columnas_maximas, padx=2, pady=2)
            self.nav_buttons.append(btn)

        self.frame_pregunta = tk.Frame(self.main_container, bg=BG_WHITE)
        self.frame_pregunta.pack(anchor="w", fill="x")

        self.lbl_contador = tk.Label(self.frame_pregunta, text="", font=("Segoe UI", 12, "bold"), bg=BG_WHITE, fg=CISCO_CYAN)
        self.lbl_contador.pack(anchor="w")
        
        self.lbl_pregunta = tk.Label(self.frame_pregunta, text="", font=("Segoe UI", 14), bg=BG_WHITE, fg=TEXT_DARK, wraplength=self.ancho_contenido, justify="left")
        self.lbl_pregunta.pack(anchor="w", pady=(6, 8))
        
        self.lbl_imagen = tk.Label(self.frame_pregunta, bg=BG_WHITE)
        self.lbl_imagen.pack(anchor="w", pady=(0, 10))
        
        self.frame_opciones = tk.Frame(self.main_container, bg=BG_WHITE)
        self.frame_opciones.pack(anchor="w", fill="both", expand=True)
        
        self.frame_botones = tk.Frame(self.main_container, bg=BG_WHITE)
        self.frame_botones.pack(fill="x", pady=12)
        
        self.btn_anterior = tk.Button(self.frame_botones, text="⬅ Anterior", command=self.pregunta_anterior, 
                                       font=("Segoe UI", 12, "bold"), bg="#e0e0e0", fg=TEXT_GRAY, 
                                       activebackground="#cccccc", activeforeground=TEXT_DARK,
                                       relief="flat", cursor="hand2", padx=20, pady=8)
        self.btn_anterior.pack(side="left", padx=(0, 10))

        if self.modo != 'revision':
            self.btn_omitir = tk.Button(self.frame_botones, text="Omitir ⏭", command=self.omitir_pregunta, 
                                        font=("Segoe UI", 12, "bold"), bg=SKIPPED_YELLOW, fg=TEXT_DARK, 
                                        activebackground="#e6b800", activeforeground=TEXT_DARK,
                                        relief="flat", cursor="hand2", padx=20, pady=8)
            self.btn_omitir.pack(side="left", padx=(0, 10))

        if self.modo == 'practica':
            self.btn_confirmar = tk.Button(self.frame_botones, text="Confirmar Respuesta", command=self.verificar_respuesta, 
                                           font=("Segoe UI", 12, "bold"), bg=CISCO_BLUE, fg=BG_WHITE, 
                                           activebackground=CISCO_CYAN, activeforeground=BG_WHITE,
                                           relief="flat", cursor="hand2", padx=20, pady=8)
            self.btn_confirmar.pack(side="left")
        
        self.btn_siguiente = tk.Button(self.frame_botones, text="Siguiente ➔", command=self.siguiente_pregunta, 
                                       font=("Segoe UI", 12, "bold"), bg="#e0e0e0", fg=TEXT_GRAY, 
                                       activebackground="#cccccc", activeforeground=TEXT_DARK,
                                       relief="flat", cursor="hand2", padx=20, pady=8)
        self.btn_siguiente.pack(side="right")

        self.lbl_feedback = tk.Label(self.main_container, text="", font=("Segoe UI", 12), bg=BG_WHITE, wraplength=self.ancho_contenido, justify="left")
        self.lbl_feedback.pack(anchor="w", pady=8)

    def _ajustar_ancho_canvas(self, event):
        self.canvas.itemconfig(self.canvas_window, width=event.width)

    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")

    def actualizar_opciones_disponibles(self, event=None):
        if not hasattr(self, 'comboboxes') or not self.comboboxes: return
        seleccionadas = [cb.get() for _, cb in self.comboboxes if cb.get() != "Seleccione..."]
        
        for widget in self.frame_izquierda.winfo_children():
            widget.destroy()
            
        tk.Label(self.frame_izquierda, text="Opciones a colocar:", font=("Segoe UI", 12, "bold"), bg=BG_WHITE, fg=CISCO_NAVY).pack(anchor="w", pady=(0,10))
        
        quedan = False
        for opt in self.opciones_emparejamiento:
            if seleccionadas.count(opt) == 0:
                card_opt = tk.Frame(self.frame_izquierda, bg=OPTION_BG)
                card_opt.pack(fill="x", pady=4)
                tk.Label(card_opt, text=opt, font=("Segoe UI", 11), bg=OPTION_BG, fg=TEXT_DARK,
                         wraplength=330, justify="left", anchor="w").pack(anchor="w", padx=15, pady=10)
                quedan = True
                
        if not quedan:
            tk.Label(self.frame_izquierda, text="(Todas las opciones han sido asignadas)", font=("Segoe UI", 10, "italic"), bg=BG_WHITE, fg=TEXT_GRAY).pack(anchor="w", pady=4)

    def actualizar_panel_navegacion(self):
        for i, btn in enumerate(self.nav_buttons):
            estado = self.estado_preguntas.get(i, {})
            status = estado.get("estado", "sin_responder")
            es_correcta = estado.get("es_correcta")
            
            bg_color = "#e0e0e0"
            fg_color = TEXT_DARK
            
            if self.modo == 'revision' or (self.modo == 'practica' and status == 'respondida'):
                if es_correcta is True:
                    bg_color = SUCCESS_GREEN
                    fg_color = BG_WHITE
                elif es_correcta is False:
                    # Si fue omitida, se pinta roja igual en la revisión
                    bg_color = ERROR_RED
                    fg_color = BG_WHITE
            else:
                if status == "respondida":
                    bg_color = SUCCESS_GREEN 
                    fg_color = BG_WHITE
                elif status == "omitida":
                    bg_color = SKIPPED_YELLOW
                    fg_color = TEXT_DARK
            
            if i == self.indice_actual:
                btn.config(bg=CISCO_CYAN, fg=BG_WHITE, relief="solid", bd=2)
            else:
                btn.config(bg=bg_color, fg=fg_color, relief="flat", bd=0)

    def _crear_opcion_card(self, parent, indice, texto, multiple):
        """Crea una tarjeta de opción estilo 'lista con círculo' como en la captura de referencia."""
        frame = tk.Frame(parent, bg=OPTION_BG, cursor="hand2")
        frame.pack(fill="x", pady=4)

        inner = tk.Frame(frame, bg=OPTION_BG)
        inner.pack(fill="x", padx=18, pady=10)

        canvas_circulo = tk.Canvas(inner, width=20, height=20, bg=OPTION_BG, highlightthickness=0)
        canvas_circulo.pack(side="left", padx=(0, 14))

        wraplength_opcion = max(400, getattr(self, "ancho_contenido", 780) - 90)
        lbl_texto = tk.Label(inner, text=texto, font=("Segoe UI", 12), bg=OPTION_BG, fg=TEXT_DARK,
                              wraplength=wraplength_opcion, justify="left", anchor="w")
        lbl_texto.pack(side="left", fill="x", expand=True)

        card = {
            "frame": frame, "inner": inner, "canvas": canvas_circulo, "label": lbl_texto,
            "indice": indice, "multiple": multiple, "bloqueado": False
        }

        def on_click(event=None, idx=indice):
            if card["bloqueado"]:
                return
            if multiple:
                var = self.variables_opciones[idx]
                var.set(0 if var.get() == 1 else 1)
            else:
                self.var_radio.set(idx)
            self._refrescar_opciones_visual()

        for w in (frame, inner, canvas_circulo, lbl_texto):
            w.bind("<Button-1>", on_click)

        self.opcion_cards.append(card)
        return card

    def _dibujar_circulo(self, card, seleccionado, color_borde, color_fondo_canvas):
        canvas = card["canvas"]
        canvas.config(bg=color_fondo_canvas)
        canvas.delete("all")
        if seleccionado:
            canvas.create_oval(2, 2, 20, 20, outline=color_borde, width=2, fill="")
            canvas.create_oval(6, 6, 16, 16, fill=color_borde, outline="")
        else:
            canvas.create_oval(2, 2, 20, 20, outline=color_borde, width=2, fill="")

    def _refrescar_opciones_visual(self, resultado=None):
        """resultado=None -> estado normal (interactivo).
        resultado={indice: True/False/None} -> estado bloqueado con corrección (verde/rojo)."""
        if not self.opcion_cards:
            return

        if self.opcion_cards[0]["multiple"]:
            seleccion_actual = [i for i, var in enumerate(self.variables_opciones) if var.get() == 1]
        else:
            val = self.var_radio.get()
            seleccion_actual = [val] if val != -1 else []

        for card in self.opcion_cards:
            idx = card["indice"]
            seleccionado = idx in seleccion_actual

            bg_color = OPTION_BG
            fg_color = TEXT_DARK
            circulo_color = OPTION_CIRCLE_IDLE

            if resultado is not None:
                estado_idx = resultado.get(idx)
                if estado_idx is True:
                    bg_color = SUCCESS_GREEN
                    fg_color = BG_WHITE
                    circulo_color = BG_WHITE
                elif estado_idx is False:
                    bg_color = ERROR_RED
                    fg_color = BG_WHITE
                    circulo_color = BG_WHITE
                seleccionado = estado_idx is True or (seleccionado and estado_idx is False)
            elif seleccionado:
                bg_color = OPTION_SELECTED
                fg_color = BG_WHITE
                circulo_color = BG_WHITE

            card["frame"].config(bg=bg_color)
            card["inner"].config(bg=bg_color)
            card["label"].config(bg=bg_color, fg=fg_color)
            self._dibujar_circulo(card, seleccionado, circulo_color, bg_color)

    def _crear_fila_emparejamiento(self, parent, indice, obj, opciones_valores):
        """Crea una fila tipo tarjeta (etiqueta + combobox) con el mismo estilo que las opciones."""
        card = tk.Frame(parent, bg=OPTION_BG, cursor="hand2")
        card.pack(fill="x", pady=4)

        inner = tk.Frame(card, bg=OPTION_BG)
        inner.pack(fill="x", padx=18, pady=8)

        lbl_obj = tk.Label(inner, text=obj, font=("Segoe UI", 11, "bold"), bg=OPTION_BG, fg=TEXT_DARK,
                            wraplength=230, justify="left", anchor="w")
        lbl_obj.pack(side="left", fill="x", expand=True)

        style_name = f"Match{indice}.TCombobox"
        self.style.configure(style_name, fieldbackground=OPTION_BG, background=OPTION_BG,
                              foreground=TEXT_DARK, arrowcolor=TEXT_DARK, bordercolor=OPTION_BG,
                              lightcolor=OPTION_BG, darkcolor=OPTION_BG, padding=6, relief="flat")
        self.style.map(style_name,
                        fieldbackground=[('readonly', OPTION_BG), ('disabled', OPTION_BG)],
                        foreground=[('readonly', TEXT_DARK), ('disabled', TEXT_DARK)])

        cb = ttk.Combobox(inner, values=["Seleccione..."] + opciones_valores, state="readonly",
                           width=38, font=("Segoe UI", 10), style=style_name)
        cb.set("Seleccione...")
        cb.pack(side="right")

        fila = {"card": card, "inner": inner, "label": lbl_obj, "combobox": cb, "obj": obj,
                "style_name": style_name}

        def on_change(event=None):
            self.actualizar_opciones_disponibles()
            self._refrescar_fila_emparejamiento(fila)

        cb.bind("<<ComboboxSelected>>", on_change)

        self.filas_emparejamiento.append(fila)
        self.comboboxes.append((obj, cb))
        return fila

    def _refrescar_fila_emparejamiento(self, fila, resultado=None):
        """resultado=None -> normal (gris/azul según selección). True/False -> verde/rojo bloqueado."""
        valor = fila["combobox"].get()
        seleccionado = valor != "Seleccione..."

        bg_color = OPTION_BG
        fg_color = TEXT_DARK

        if resultado is True:
            bg_color = SUCCESS_GREEN
            fg_color = BG_WHITE
        elif resultado is False:
            bg_color = ERROR_RED
            fg_color = BG_WHITE
        elif seleccionado:
            bg_color = OPTION_SELECTED
            fg_color = BG_WHITE

        fila["card"].config(bg=bg_color)
        fila["inner"].config(bg=bg_color)
        fila["label"].config(bg=bg_color, fg=fg_color)
        self.style.configure(fila["style_name"], fieldbackground=bg_color, background=bg_color,
                              foreground=fg_color, arrowcolor=fg_color, bordercolor=bg_color,
                              lightcolor=bg_color, darkcolor=bg_color)
        self.style.map(fila["style_name"],
                        fieldbackground=[('readonly', bg_color), ('disabled', bg_color)],
                        foreground=[('readonly', fg_color), ('disabled', fg_color)])

    def obtener_seleccion_actual(self):
        q = self.preguntas[self.indice_actual]
        if q.get("tipo", "opcion_multiple") == "emparejamiento":
            return {obj: cb.get() for obj, cb in self.comboboxes}
        else:
            if self.es_multiple: return [i for i, var in enumerate(self.variables_opciones) if var.get() == 1]
            else:
                seleccion = self.var_radio.get()
                return [seleccion] if seleccion != -1 else []

    def determinar_si_tiene_respuesta(self, seleccion):
        if isinstance(seleccion, dict): return any(val != "Seleccione..." for val in seleccion.values())
        elif isinstance(seleccion, list): return len(seleccion) > 0 and seleccion[0] != -1
        return False

    def guardar_respuesta_silenciosa(self, forzar_estado=None):
        if self.modo == 'revision': return 
            
        seleccion_usuario = self.obtener_seleccion_actual()
        tiene_respuesta = self.determinar_si_tiene_respuesta(seleccion_usuario)
        estado = "respondida" if tiene_respuesta else "sin_responder"
        if forzar_estado: estado = forzar_estado

        estado_anterior = self.estado_preguntas.get(self.indice_actual, {})
        if self.modo == 'practica' and estado_anterior.get("estado") == "respondida":
            estado = "respondida"

        self.estado_preguntas[self.indice_actual] = {
            "seleccion_usuario": seleccion_usuario,
            "estado": estado,
            "feedback_texto": estado_anterior.get("feedback_texto", ""),
            "color_feedback": estado_anterior.get("color_feedback", ""),
            "es_correcta": estado_anterior.get("es_correcta", False)
        }

    def evaluar_pregunta(self, indice):
        """Evalúa silenciosamente una pregunta, considerando las omitidas como errores que muestran la respuesta correcta"""
        q = self.preguntas[indice]
        tipo = q.get("tipo", "opcion_multiple")
        estado = self.estado_preguntas.get(indice, {})
        sel = estado.get("seleccion_usuario")
        
        es_correcta = False
        feedback_texto = ""
        color = ""
        correctas_q = q.get("respuestas_correctas")
        
        # Identificar si la pregunta fue dejada en blanco u omitida intencionalmente
        fue_omitida = not sel or not self.determinar_si_tiene_respuesta(sel)

        if tipo == "emparejamiento":
            todas_correctas = True
            correctas_agrupadas, usuario_agrupadas = {}, {}
            
            for obj, correcta in correctas_q.items():
                base_obj = re.sub(r'\s*\(\d+\)$', '', obj).strip()
                correctas_agrupadas.setdefault(base_obj, []).append(correcta)
            
            if not fue_omitida:
                for obj, seleccion in sel.items():
                    base_obj = re.sub(r'\s*\(\d+\)$', '', obj).strip()
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

        if "explicacion" in q and q["explicacion"]:
            feedback_texto += f"\n\n💡 Explicación:\n{q['explicacion']}"

        estado["es_correcta"] = es_correcta
        estado["feedback_texto"] = feedback_texto
        estado["color_feedback"] = color
        self.estado_preguntas[indice] = estado

    def ir_a_pregunta(self, indice_destino):
        self.guardar_respuesta_silenciosa()
        self.indice_actual = indice_destino
        self.mostrar_pregunta()

    def omitir_pregunta(self):
        self.guardar_respuesta_silenciosa(forzar_estado="omitida")
        self.avanzar_indice()

    def avanzar_indice(self):
        if self.indice_actual < len(self.preguntas) - 1:
            self.indice_actual += 1
            self.mostrar_pregunta()
        else:
            if self.modo == 'examen': self.confirmar_finalizacion_examen()
            else: self.mostrar_resultados()

    def pregunta_anterior(self):
        self.guardar_respuesta_silenciosa()
        if self.indice_actual > 0:
            self.indice_actual -= 1
            self.mostrar_pregunta()

    def siguiente_pregunta(self):
        self.guardar_respuesta_silenciosa()
        self.avanzar_indice()

    def verificar_respuesta(self):
        seleccion_guardar = self.obtener_seleccion_actual()
        if not self.determinar_si_tiene_respuesta(seleccion_guardar):
            messagebox.showwarning("Atención", "Por favor seleccione al menos una opción antes de confirmar.")
            return

        q = self.preguntas[self.indice_actual]
        if q.get("tipo") == "emparejamiento":
            if any(val == "Seleccione..." for val in seleccion_guardar.values()):
                messagebox.showwarning("Atención", "Por favor asigne una opción a todos los objetivos antes de confirmar.")
                return
        else:
            resp_corr = q["respuestas_correctas"]
            if self.es_multiple and len(seleccion_guardar) != len(resp_corr):
                messagebox.showwarning("Atención", f"Esta pregunta requiere exactamente {len(resp_corr)} respuestas.")
                return

        estado = self.estado_preguntas.get(self.indice_actual, {})
        estado["seleccion_usuario"] = seleccion_guardar
        estado["estado"] = "respondida"
        self.estado_preguntas[self.indice_actual] = estado
        
        self.evaluar_pregunta(self.indice_actual)
        self.mostrar_pregunta() 

    def mostrar_pregunta(self):
        q = self.preguntas[self.indice_actual]
        tipo_pregunta = q.get("tipo", "opcion_multiple")
        
        self.actualizar_panel_navegacion()
        self.lbl_contador.config(text=f"Pregunta {self.indice_actual + 1} de {len(self.preguntas)}")
        self.lbl_pregunta.config(text=q["pregunta"])
        self.canvas.yview_moveto(0)
        
        if self.indice_actual > 0: self.btn_anterior.config(state=tk.NORMAL, bg=CISCO_BLUE, fg=BG_WHITE)
        else: self.btn_anterior.config(state=tk.DISABLED, bg="#e0e0e0", fg=TEXT_GRAY)

        if self.modo == 'examen':
            self.btn_siguiente.config(state=tk.NORMAL, text="Siguiente ➔", bg=CISCO_BLUE, fg=BG_WHITE)
            if self.indice_actual == len(self.preguntas) - 1:
                self.btn_siguiente.config(text="Finalizar Examen ➔", bg=CISCO_CYAN)
        elif self.modo == 'revision':
            self.btn_siguiente.config(state=tk.NORMAL, text="Siguiente ➔", bg=CISCO_BLUE, fg=BG_WHITE)
            if self.indice_actual == len(self.preguntas) - 1:
                self.btn_siguiente.config(text="Volver al Resumen ➔", bg=CISCO_CYAN)

        self.lbl_imagen.config(image='') 
        self.imagen_actual = None
        nombre_imagen = q.get("imagen")
        if nombre_imagen:
            ruta_imagen = self.buscar_imagen(nombre_imagen)
            if not HAS_PIL:
                self.lbl_imagen.config(text=f"[Imagen requerida: {nombre_imagen}]\nInstala 'Pillow' para verla.", fg=ERROR_RED)
            elif ruta_imagen:
                try:
                    img = Image.open(ruta_imagen)
                    img.thumbnail((750, 400))
                    self.imagen_actual = ImageTk.PhotoImage(img)
                    self.lbl_imagen.config(image=self.imagen_actual, text="")
                except Exception as e:
                    self.lbl_imagen.config(text=f"[Error al cargar la imagen: {e}]", fg=ERROR_RED)
            else:
                self.lbl_imagen.config(text=f"[Archivo no encontrado: '{nombre_imagen}']", fg=ERROR_RED)
        else:
            self.lbl_imagen.config(text="")

        for widget in self.frame_opciones.winfo_children(): widget.destroy()
        self.variables_opciones = []
        self.comboboxes = []
        self.opcion_cards = []
        self.filas_emparejamiento = []
        
        if tipo_pregunta == "emparejamiento":
            self.opciones_emparejamiento = q.get("opciones", [])
            self.objetivos_emparejamiento = q.get("objetivos", [])
            
            self.frame_izquierda = tk.Frame(self.frame_opciones, bg=BG_WHITE, width=400)
            self.frame_izquierda.pack(side="left", fill="y", padx=(0, 40))
            self.frame_derecha = tk.Frame(self.frame_opciones, bg=BG_WHITE)
            self.frame_derecha.pack(side="left", fill="both", expand=True)

            tk.Label(self.frame_derecha, text="Objetivos:", font=("Segoe UI", 12, "bold"), bg=BG_WHITE, fg=CISCO_NAVY).pack(anchor="w", pady=(0,10))

            for i, obj in enumerate(self.objetivos_emparejamiento):
                self._crear_fila_emparejamiento(self.frame_derecha, i, obj, self.opciones_emparejamiento)
            self.actualizar_opciones_disponibles()

        else:
            self.es_multiple = len(q.get("respuestas_correctas", [])) > 1
            if self.es_multiple:
                tk.Label(self.frame_opciones, text=f"(Seleccione {len(q['respuestas_correctas'])} opciones)", font=("Segoe UI", 11, "italic"), bg=BG_WHITE, fg=TEXT_GRAY).pack(anchor="w", pady=(0, 15))

            if self.es_multiple:
                self.variables_opciones = [tk.IntVar() for _ in q.get("opciones", [])]
            else:
                self.var_radio = tk.IntVar(value=-1)

            for i, opcion in enumerate(q.get("opciones", [])):
                self._crear_opcion_card(self.frame_opciones, i, opcion, self.es_multiple)

        estado = self.estado_preguntas.get(self.indice_actual, {})
        sel = estado.get("seleccion_usuario")
        
        if sel:
            if tipo_pregunta == "emparejamiento":
                for obj, cb in self.comboboxes:
                    if obj in sel: cb.set(sel[obj])
                self.actualizar_opciones_disponibles()
            else:
                if self.es_multiple:
                    for idx in sel: self.variables_opciones[idx].set(1)
                else:
                    if sel and sel[0] != -1: self.var_radio.set(sel[0])

        esta_bloqueada = self.modo == 'revision' or (self.modo == 'practica' and estado.get("estado") == "respondida")

        if tipo_pregunta == "emparejamiento":
            respuestas_correctas_map = q.get("respuestas_correctas", {})
            for fila in self.filas_emparejamiento:
                if esta_bloqueada:
                    correcta_obj = respuestas_correctas_map.get(fila["obj"])
                    valor_usuario = sel.get(fila["obj"]) if sel else None
                    es_correcta_fila = (valor_usuario is not None and valor_usuario == correcta_obj)
                    self._refrescar_fila_emparejamiento(fila, resultado=es_correcta_fila)
                    fila["combobox"].config(state=tk.DISABLED)
                else:
                    self._refrescar_fila_emparejamiento(fila)
        else:
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
                for card in self.opcion_cards:
                    card["bloqueado"] = True
            self._refrescar_opciones_visual(resultado=resultado_visual)

        if esta_bloqueada:
            self.lbl_feedback.config(text=estado.get("feedback_texto", ""), fg=estado.get("color_feedback", BG_WHITE))
            
            if self.btn_confirmar is not None and self.btn_confirmar.winfo_exists():
                self.btn_confirmar.config(state=tk.DISABLED, bg="#e0e0e0", fg=TEXT_GRAY)
            if self.btn_omitir is not None and self.btn_omitir.winfo_exists():
                self.btn_omitir.config(state=tk.DISABLED, bg="#e0e0e0", fg=TEXT_GRAY)
            self.btn_siguiente.config(state=tk.NORMAL, bg=CISCO_BLUE, fg=BG_WHITE)
            
        else: 
            self.lbl_feedback.config(text="")
            if self.btn_omitir is not None and self.btn_omitir.winfo_exists():
                self.btn_omitir.config(state=tk.NORMAL, bg=SKIPPED_YELLOW, fg=TEXT_DARK)
            if self.btn_confirmar is not None and self.btn_confirmar.winfo_exists():
                self.btn_confirmar.config(state=tk.NORMAL, bg=CISCO_BLUE, fg=BG_WHITE)
            self.btn_siguiente.config(state=tk.NORMAL if self.modo == 'examen' else tk.DISABLED)

        self.root.update_idletasks()
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def confirmar_finalizacion_examen(self):
        respondidas = sum(1 for e in self.estado_preguntas.values() if e.get("estado") == "respondida")
        faltantes = len(self.preguntas) - respondidas
        
        if faltantes > 0:
            if not messagebox.askyesno("Atención", f"Te faltan {faltantes} preguntas por responder u omitidas.\n\n¿Estás seguro de que deseas finalizar y evaluar el examen ahora?"):
                return
                
        self.evaluar_examen_completo()
        self.mostrar_resultados()

    def evaluar_examen_completo(self):
        self.puntaje = 0
        for i in range(len(self.preguntas)):
            self.evaluar_pregunta(i)
            if self.estado_preguntas[i].get("es_correcta"):
                self.puntaje += 1

    def mostrar_resultados(self):
        if self.modo == 'practica':
            self.evaluar_examen_completo()
            
        for widget in self.main_container.winfo_children():
            widget.destroy()
            
        porcentaje = (self.puntaje / len(self.preguntas)) * 100
        color_porcentaje = SUCCESS_GREEN if porcentaje >= 70 else ERROR_RED
        texto_aprobacion = "¡Aprobado!" if porcentaje >= 70 else "Requiere más estudio"
        
        tk.Label(self.main_container, text="Resumen de Evaluación", font=("Segoe UI", 28, "bold"), bg=BG_WHITE, fg=CISCO_NAVY).pack(pady=(40, 10))
        
        frame_resultados = tk.Frame(self.main_container, bg=BG_WHITE, highlightbackground=CISCO_CYAN, highlightthickness=2, padx=40, pady=20)
        frame_resultados.pack(pady=10)
        
        tk.Label(frame_resultados, text=f"Puntaje Obtenido:\n{self.puntaje} de {len(self.preguntas)}", font=("Segoe UI", 18), bg=BG_WHITE, fg=TEXT_DARK).pack(pady=5)
        tk.Label(frame_resultados, text=f"Rendimiento: {porcentaje:.1f}%", font=("Segoe UI", 24, "bold"), bg=BG_WHITE, fg=color_porcentaje).pack(pady=5)
        tk.Label(frame_resultados, text=texto_aprobacion, font=("Segoe UI", 14, "italic"), bg=BG_WHITE, fg=TEXT_GRAY).pack(pady=5)

        tk.Label(self.main_container, text="Detalle de Preguntas", font=("Segoe UI", 20, "bold"), bg=BG_WHITE, fg=CISCO_NAVY).pack(pady=(30, 10))
        
        frame_lista = tk.Frame(self.main_container, bg=BG_WHITE)
        frame_lista.pack(fill="both", expand=True, padx=20)

        for i, q in enumerate(self.preguntas):
            estado = self.estado_preguntas.get(i, {})
            es_correcta = estado.get("es_correcta", False)
            respondida = estado.get("estado") == "respondida"
            
            if es_correcta:
                bg_card = "#e8f5e9"
                fg_text = SUCCESS_GREEN
                texto_estado = "✔️ Correcta"
            else:
                bg_card = "#ffebee"
                fg_text = ERROR_RED
                if not respondida:
                    texto_estado = "❌ Omitida (Incorrecta)"
                else:
                    texto_estado = "❌ Incorrecta"
            
            card = tk.Frame(frame_lista, bg=bg_card, highlightbackground=fg_text, highlightthickness=1, padx=15, pady=10)
            card.pack(fill="x", pady=5)
            
            lbl_q = tk.Label(card, text=f"Pregunta {i + 1}: {q['pregunta']}", font=("Segoe UI", 12, "bold"), bg=bg_card, fg=TEXT_DARK, wraplength=800, justify="left")
            lbl_q.pack(anchor="w")
            lbl_status = tk.Label(card, text=texto_estado, font=("Segoe UI", 11, "bold"), bg=bg_card, fg=fg_text)
            lbl_status.pack(anchor="w", pady=(5,0))
            
        btn_revisar = tk.Button(self.main_container, text="Revisar Examen 🔍", command=self.iniciar_revision, 
                                font=("Segoe UI", 14, "bold"), bg=CISCO_CYAN, fg=BG_WHITE, 
                                activebackground=CISCO_BLUE, activeforeground=BG_WHITE,
                                relief="flat", cursor="hand2", padx=30, pady=12)
        btn_revisar.pack(pady=(30, 10))

        btn_salir = tk.Button(self.main_container, text="Volver al Menú Principal", command=self.mostrar_menu, 
                              font=("Segoe UI", 14, "bold"), bg=CISCO_NAVY, fg=BG_WHITE, 
                              activebackground=CISCO_BLUE, activeforeground=BG_WHITE,
                              relief="flat", cursor="hand2", padx=30, pady=12)
        btn_salir.pack(pady=10)
        
        self.root.update_idletasks()
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        self.canvas.yview_moveto(0)

if __name__ == "__main__":
    root = tk.Tk()
    app = ExamenApp(root)
    root.mainloop()