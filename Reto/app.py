import solara
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.collections import PatchCollection
from matplotlib.figure import Figure
import numpy as np
import time
import asyncio  # <--- IMPORTANTE: Importar asyncio para la ejecución no bloqueante

from model import TrafficModel, BUILDING, ROAD, ROUNDABOUT, PARKING
from agents import VehicleAgent, TrafficLightAgent

# --- CONFIGURATION ---
GRID_WIDTH = 25
GRID_HEIGHT = 25

COLOR_MAP = {
    BUILDING: "#4682B4",   # Steel Blue
    ROAD: "#D3D3D3",       # Light Gray
    ROUNDABOUT: "#8B4513", # Saddle Brown
    PARKING: "#FFD700"     # Gold
}

AGENT_COLORS = {
    "moving": "black",
    "stopped": "red",
    "light_green": "#00FF00",
    "light_yellow": "#FFFF00",
    "light_red": "#FF0000"
}

# --- PRE-LOAD ---
static_model = TrafficModel(num_vehicles=0)
CITY_LAYOUT = static_model.city_layout

# --- STATE ---
model_state = solara.reactive(None)
current_step = solara.reactive(0)
is_playing = solara.reactive(False)
play_speed = solara.reactive(0.1) 
num_vehicles_param = solara.reactive(5)

def initialize_model():
    model_state.value = TrafficModel(num_vehicles=num_vehicles_param.value)
    current_step.value = 0
    is_playing.value = False

def step_model():
    if model_state.value is not None:
        model_state.value.step()
        model_state.value = model_state.value 
        current_step.value += 1

def create_city_visualization(model: TrafficModel) -> Figure:
    fig, ax = plt.subplots(figsize=(10, 10))
    
    # 1. DRAW MAP
    rects = []
    colors = []
    for x in range(GRID_WIDTH):
        for y in range(GRID_HEIGHT):
            cell_type = CITY_LAYOUT[x][y]
            # CORRECCIÓN: Usar (x, y) directamente en lugar de restar 0.5
            # Esto alinea el cuadro gris con el sistema de coordenadas de Mesa
            rect = patches.Rectangle((x, y), 1, 1)
            rects.append(rect)
            colors.append(COLOR_MAP[cell_type])

    collection = PatchCollection(rects, facecolors=colors, edgecolors='white', linewidths=0.5, zorder=0)
    ax.add_collection(collection)
    
    # 2. DRAW PARKING
    for pid, pos in model.parking_spots.items():
        px, py = pos
        # Ajustamos el borde del parking para que coincida con la nueva cuadrícula
        border = patches.Rectangle((px, py), 1, 1, linewidth=2, edgecolor='black', facecolor='none', zorder=5)
        ax.add_patch(border)
        # Ajustamos el texto para que esté en el centro (x+0.5, y+0.5)
        ax.text(px + 0.5, py + 0.5, "P", color='black', fontsize=10, ha='center', va='center', fontweight='bold', zorder=6)

    # 3. DRAW AGENTS
    vehicle_count = 0
    
    for agent in model.agents_list:
        # Mesa guarda posiciones como (float, float). Ej: (12.5, 3.5)
        x, y = agent.pos
        
        if isinstance(agent, VehicleAgent):
            vehicle_count += 1
            color = AGENT_COLORS["moving"]
            if agent.speed < 0.01:
                color = AGENT_COLORS["stopped"]
            
            # El coche ya está en x.5, y.5, así que se dibuja en el centro correctamente
            circle = patches.Circle((x, y), radius=0.35, facecolor=color, edgecolor='white', linewidth=1, zorder=15)
            ax.add_patch(circle)
            
        elif isinstance(agent, TrafficLightAgent):
            if agent.state == "GREEN": c = AGENT_COLORS["light_green"]
            elif agent.state == "YELLOW": c = AGENT_COLORS["light_yellow"]
            else: c = AGENT_COLORS["light_red"]
            
            # El semáforo está en (x.5, y.5).
            # Para llenar la celda, restamos 0.5 para obtener la esquina inferior izquierda (x.0, y.0)
            rect = patches.Rectangle(
                (x - 0.5, y - 0.5), 
                1.0, 1.0, 
                facecolor=c, 
                edgecolor='none', 
                alpha=0.6, # Hacemos los semáforos un poco transparentes
                zorder=20
            )
            ax.add_patch(rect)

    ax.set_aspect("equal")
    
    # CORRECCIÓN: Ajustar los límites de 0 a 25 exactos
    ax.set_xlim(0, 25)
    ax.set_ylim(0, 25)
    
    ax.invert_yaxis() # Mantiene el (0,0) arriba a la izquierda visualmente
    
    # Ajustar etiquetas de ejes para que se vean limpias
    ax.set_xticks(np.arange(0.5, 25.5, 1))
    ax.set_yticks(np.arange(0.5, 25.5, 1))
    ax.set_xticklabels(range(25))
    ax.set_yticklabels(range(25))
    ax.tick_params(left=False, bottom=False, labeltop=True, labelbottom=False)
    
    ax.set_title(f"Step: {current_step.value} | Vehicles: {vehicle_count}", fontsize=14)
    
    return fig

@solara.component
def StatisticsPanel():
    if model_state.value is None: return
    vehicles = [a for a in model_state.value.agents_list if isinstance(a, VehicleAgent)]
    total = len(vehicles)
    stopped = sum(1 for v in vehicles if v.speed < 0.01)
    avg_speed = model_state.value.get_avg_speed()
    
    with solara.Card("Live Statistics"):
        solara.Markdown(f"**Step:** {current_step.value}")
        solara.Markdown(f"**Vehicles:** {total}")
        solara.Markdown(f"**Stopped:** {stopped}")
        solara.Markdown(f"**Avg Speed:** {avg_speed:.2f}")

@solara.component
def TrafficSimulation():
    if model_state.value is None:
        initialize_model()

    # Definimos el efecto de forma SÍNCRONA
    def run_loop_effect():
        # Definimos la lógica asíncrona dentro
        async def loop_logic():
            while is_playing.value:
                step_model()
                await asyncio.sleep(play_speed.value)

        # Si está reproduciendo, creamos la tarea en segundo plano
        if is_playing.value:
            task = asyncio.create_task(loop_logic())
            
            # Devolvemos una función de limpieza para cancelar la tarea
            # si el usuario pausa o cambia de página.
            def cleanup():
                task.cancel()
            return cleanup
            
        return None # No hay nada que limpiar si no está reproduciendo

    # Pasamos la función síncrona al use_effect
    solara.use_effect(run_loop_effect, [is_playing.value])

    with solara.Sidebar():
        solara.Markdown("## 🎮 Controls")
        solara.Button("🔄 Reset", color="primary", on_click=initialize_model, block=True)
        if is_playing.value:
            solara.Button("⏸️ Pause", color="warning", on_click=lambda: is_playing.set(False), block=True)
        else:
            solara.Button("▶️ Play", color="success", on_click=lambda: is_playing.set(True), block=True)
        solara.Button("⏭️ Step +1", color="info", on_click=step_model, disabled=is_playing.value, block=True)
        solara.SliderFloat("Speed", value=play_speed, min=0.01, max=1.0, step=0.05)
        solara.SliderInt("Vehicles", value=num_vehicles_param, min=1, max=20)
        StatisticsPanel()

    with solara.Column(style={"padding": "20px", "align-items": "center"}):
        solara.Markdown("# 🚦 Traffic Jam Simulation")
        if model_state.value is not None:
            fig = create_city_visualization(model_state.value)
            solara.FigureMatplotlib(fig, dependencies=[current_step.value])
            plt.close(fig)

@solara.component
def Page():
    TrafficSimulation()