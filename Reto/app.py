from mesa.visualization import SolaraViz, SpaceRenderer, make_plot_component
from mesa.visualization.components import AgentPortrayalStyle
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from model import TrafficModel
from agents import VehicleAgent, TrafficLightAgent

# 1. Define how agents look (The Portrayal)
def traffic_portrayal(agent):
    if agent is None:
        return

    portrayal = AgentPortrayalStyle(
        size=50,
        marker="o",
        zorder=2,
    )

    if isinstance(agent, TrafficLightAgent):
        # Traffic Lights as Squares (Blocks)
        portrayal.update(("marker", "s"), ("size", 180), ("zorder", 3))
        
        # Color logic
        if agent.state == "GREEN":
            portrayal.update(("color", "#00AA00")) # Bright Green
        elif agent.state == "YELLOW":
            portrayal.update(("color", "#FFD700")) # Gold
        else:
            portrayal.update(("color", "#CC0000")) # Red
            
    elif isinstance(agent, VehicleAgent):
        # Cars as Circles
        portrayal.update(("color", "black"), ("size", 70), ("zorder", 4))
        # Change color if stopped
        if agent.speed < 0.01:
             portrayal.update(("color", "gray")) # Gray if stopped

    return portrayal

# 2. Model Parameters
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

# 3. Custom Map Drawing (The City Blocks)
def post_process_map(ax):
    # Setup grid
    ax.set_aspect("equal")
    ax.set_xlim(-0.5, 23.5)
    ax.set_ylim(-0.5, 23.5)
    ax.invert_yaxis() # Invert Y so (0,0) is top-left
    
    # Hide axis numbers (optional)
    ax.set_xticks([])
    ax.set_yticks([])
    
    # We create a temporary instance to read the map data
    temp_model = TrafficModel(num_vehicles=0)
    
    # DRAW THE GRID
    for x in range(24):
        for y in range(24):
            pos = (x, y)
            
            # DEFAULT: Building (Blue)
            color = "#4682B4" # SteelBlue
            
            # CHECK: Parking Spot (Yellow)
            if pos in temp_model.parking_spots.values():
                color = "#FFD700" # Gold
            
            # CHECK: Roundabout (Brown Area)
            # Coordinates approx 10-13 horizontal, 9-12 vertical based on image
            elif 10 <= x <= 13 and 9 <= y <= 12:
                color = "#8B4513" # SaddleBrown
                
            # CHECK: Road (Light Gray)
            # If it's a node in the graph, it's a road
            elif pos in temp_model.graph.nodes:
                color = "#D3D3D3" # LightGray
            
            # Draw the cell
            rect = patches.Rectangle(
                (x - 0.5, y - 0.5), 1, 1, 
                facecolor=color, 
                edgecolor='white', 
                linewidth=0.5,
                zorder=0
            )
            ax.add_patch(rect)

# 4. Plots
lineplot_component = make_plot_component(
    {"Stopped_Cars": "tab:red", "Average_Speed": "tab:blue"},
)

# 5. Instantiate
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