from mesa.visualization import SolaraViz, SpaceRenderer, make_plot_component
from mesa.visualization.components import AgentPortrayalStyle
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from model import TrafficModel, BUILDING, ROAD, ROUNDABOUT, PARKING
from agents import VehicleAgent, TrafficLightAgent

def traffic_portrayal(agent):
    if agent is None: return

    portrayal = AgentPortrayalStyle(
        size=50,
        marker="o",
        zorder=2,
    )

    if isinstance(agent, TrafficLightAgent):
        portrayal.update(("marker", "s"), ("size", 180), ("zorder", 3))
        if agent.state == "GREEN":
            portrayal.update(("color", "#00AA00"))
        elif agent.state == "YELLOW":
            portrayal.update(("color", "#FFD700"))
        else:
            portrayal.update(("color", "#CC0000"))
            
    elif isinstance(agent, VehicleAgent):
        portrayal.update(("color", "black"), ("size", 70), ("zorder", 4))
        if agent.speed < 0.01:
             portrayal.update(("color", "gray"))

    return portrayal

model_params = {
    "num_vehicles": {
        "type": "SliderInt",
        "value": 5,
        "label": "Number of Vehicles",
        "min": 1,
        "max": 20,
        "step": 1,
    }
}

def post_process_map(ax):
    ax.set_aspect("equal")
    # UPGRADE: Extend limits to 25
    ax.set_xlim(-0.5, 24.5)
    ax.set_ylim(-0.5, 24.5)
    ax.invert_yaxis() 
    
    ax.figure.set_size_inches(10, 10)
    
    # UPGRADE: Show ticks 0-24
    ax.set_xticks(range(25))
    ax.set_yticks(range(25))
    ax.xaxis.tick_top()
    ax.grid(color='white', linestyle='-', linewidth=0.2, alpha=0.5)
    
    temp_model = TrafficModel(num_vehicles=0)
    layout = temp_model.city_layout
    
    colors = {
        BUILDING: "#4682B4",   
        ROAD: "#D3D3D3",       
        ROUNDABOUT: "#8B4513", 
        PARKING: "#FFD700"     
    }

    # UPGRADE: Loop 0-24
    for x in range(25):
        for y in range(25):
            cell_type = layout[x][y]
            color = colors[cell_type]
            
            rect = patches.Rectangle(
                (x - 0.5, y - 0.5), 1, 1, 
                facecolor=color, 
                edgecolor='white', 
                linewidth=0.5,
                zorder=0
            )
            ax.add_patch(rect)

lineplot_component = make_plot_component(
    {"Stopped_Cars": "tab:red", "Average_Speed": "tab:blue"},
)

traffic_model = TrafficModel()

renderer = SpaceRenderer(
    traffic_model,
    backend="matplotlib",
)
renderer.draw_agents(traffic_portrayal)
renderer.post_process = post_process_map

page = SolaraViz(
    traffic_model,
    renderer,
    components=[lineplot_component], 
    model_params=model_params,
    name="Traffic Jam Model"
)

page