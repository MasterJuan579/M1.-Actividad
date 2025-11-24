import mesa
from mesa import Model
from mesa.space import ContinuousSpace
from mesa.datacollection import DataCollector
import networkx as nx
from agents import VehicleAgent, TrafficLightAgent

# Cell Types
BUILDING = 0
ROAD = 1
ROUNDABOUT = 2
PARKING = 3

class TrafficModel(Model):
    def __init__(self, num_vehicles=5):
        super().__init__()
        self.num_vehicles = num_vehicles
        self.step_count = 0
        
        # 25x25 Grid
        self.space = ContinuousSpace(x_max=25, y_max=25, torus=False)
        self.agents_list = [] 
        
        self.city_layout = [[BUILDING for y in range(25)] for x in range(25)]
        self.graph = nx.DiGraph()
        self.parking_spots = {} 
        self.traffic_lights = [] 
        
        self.build_city_graph()
        
        # --- AGENT PLACEMENT ---
        light_configs = [
            (12, 0, "GREEN"), (12, 1, "GREEN"), # Top
            (0, 12, "RED"),   (1, 12, "RED"),   # Left
            (12, 24, "GREEN"),(12, 23, "GREEN"),# Bottom
            (24, 12, "RED"),  (23, 12, "RED")   # Right
        ]
        
        for (x, y, state) in light_configs:
            pos = (x + 0.5, y + 0.5) 
            tl_agent = TrafficLightAgent(f"TL_{x}_{y}", self, direction="N")
            tl_agent.state = state
            self.space.place_agent(tl_agent, pos)
            self.agents_list.append(tl_agent)
            self.traffic_lights.append(tl_agent)

        self.parking_spots = {
            1: (12, 1),   # Top Inner
            2: (1, 12),   # Left Inner
            3: (12, 23),  # Bottom Inner
            4: (23, 12)   # Right Inner
        }
        
        parking_ids = list(self.parking_spots.keys())
        
        for i in range(self.num_vehicles):
            path_found = False
            for attempt in range(20): 
                start_id = self.random.choice(parking_ids)
                dest_id = self.random.choice([pid for pid in parking_ids if pid != start_id])
                
                start_pos = self.parking_spots[start_id]
                dest_pos = self.parking_spots[dest_id]
                
                start_node = self.get_nearest_node(start_pos)
                dest_node = self.get_nearest_node(dest_pos)
                
                try:
                    path_nodes = nx.shortest_path(self.graph, start_node, dest_node, weight='weight')
                    vehicle = VehicleAgent(f"Car_{i}", self, start_node, dest_node)
                    vehicle.path = [(x + 0.5, y + 0.5) for x, y in path_nodes]
                    spawn_pos = (start_node[0] + 0.5, start_node[1] + 0.5)
                    self.space.place_agent(vehicle, spawn_pos)
                    self.agents_list.append(vehicle)
                    path_found = True
                    break
                except nx.NetworkXNoPath:
                    continue
            
            if not path_found:
                print(f"CRITICAL: Car_{i} could not find a path.")

        self.datacollector = DataCollector(
            model_reporters={
                "Stopped_Cars": lambda m: sum(1 for a in m.agents_list if isinstance(a, VehicleAgent) and a.speed < 0.01),
                "Average_Speed": lambda m: self.get_avg_speed()
            }
        )

    def get_avg_speed(self):
        speeds = [a.speed for a in self.agents_list if isinstance(a, VehicleAgent)]
        return sum(speeds) / len(speeds) if speeds else 0
    
    def get_nearest_node(self, pos):
        return min(self.graph.nodes, key=lambda n: (n[0]-pos[0])**2 + (n[1]-pos[1])**2)

    def step(self):
        self.datacollector.collect(self)
        self.random.shuffle(self.agents_list)
        for agent in self.agents_list:
            agent.step()
        for agent in self.agents_list:
            if hasattr(agent, "advance"):
                agent.advance()     
        self.step_count += 1

    def build_city_graph(self):
        def add_line(start, end, direction, weight=1):
            curr = list(start)
            while curr != list(end):
                node_curr = tuple(curr)
                next_x = curr[0] + direction[0]
                next_y = curr[1] + direction[1]
                node_next = (next_x, next_y)
                
                if not (0 <= next_x < 25 and 0 <= next_y < 25):
                    break

                self.graph.add_node(node_curr)
                self.graph.add_node(node_next)
                self.graph.add_edge(node_curr, node_next, weight=weight)
                
                self.city_layout[curr[0]][curr[1]] = ROAD
                self.city_layout[next_x][next_y] = ROAD

                curr[0], curr[1] = next_x, next_y

        # ================= PERIMETER (2 Lanes) =================
        add_line((24, 0), (0, 0), (-1, 0)) # Top Outer
        add_line((23, 1), (1, 1), (-1, 0)) # Top Inner
        add_line((0, 0), (0, 24), (0, 1))  # Left Outer
        add_line((1, 1), (1, 23), (0, 1))  # Left Inner
        add_line((0, 24), (24, 24), (1, 0)) # Bottom Outer
        add_line((1, 23), (23, 23), (1, 0)) # Bottom Inner
        add_line((24, 24), (24, 0), (0, -1)) # Right Outer
        add_line((23, 23), (23, 1), (0, -1)) # Right Inner

        # Perimeter Merges
        self.graph.add_edge((12, 0), (11, 1), weight=3)
        self.graph.add_edge((12, 1), (11, 0), weight=3)
        self.graph.add_edge((0, 12), (1, 13), weight=3)
        self.graph.add_edge((1, 12), (0, 13), weight=3)
        self.graph.add_edge((12, 24), (13, 23), weight=3)
        self.graph.add_edge((12, 23), (13, 24), weight=3)
        self.graph.add_edge((24, 12), (23, 11), weight=3)
        self.graph.add_edge((23, 12), (24, 11), weight=3)

        # Perimeter Corners
        self.graph.add_edge((24, 0), (23, 0), weight=1)
        self.graph.add_edge((23, 0), (23, 1), weight=1)
        self.graph.add_edge((1, 1), (1, 2), weight=1)
        self.graph.add_edge((1, 23), (2, 23), weight=1)
        self.graph.add_edge((23, 23), (23, 22), weight=1)


        # ================= NEW: ROUNDABOUT RING (Corridor) =================
        # 1. North Corridor (y=8): Flows Left (12->8)
        add_line((12, 8), (8, 8), (-1, 0))
        
        # 2. West Corridor (x=8): Flows Down (8->12)
        add_line((8, 8), (8, 12), (0, 1))
        
        # 3. South Corridor (y=12): Flows Right (8->12)
        add_line((8, 12), (12, 12), (1, 0))
        
        # 4. East Corridor (x=12): Flows Up (12->8)
        add_line((12, 12), (12, 8), (0, -1))
        
        # Connect Corners to make it a loop
        self.graph.add_edge((8, 8), (8, 9), weight=1)   # Top-Left turn
        self.graph.add_edge((8, 12), (9, 12), weight=1) # Bottom-Left turn
        self.graph.add_edge((12, 12), (12, 11), weight=1) # Bottom-Right turn
        self.graph.add_edge((12, 8), (11, 8), weight=1)   # Top-Right turn

        # Paint the Brown Center
        for x in range(9, 12):
            for y in range(9, 12):
                self.city_layout[x][y] = ROUNDABOUT


        # ================= TOP INTERNAL ROAD (2 Lanes) =================
        
        # 1. Down Lane (x=11): Flows INTO Roundabout
        # Starts at (11, 1) -> Ends at (11, 8)
        add_line((11, 1), (11, 8), (0, 1))
        
        # 2. Up Lane (x=12): Flows OUT of Roundabout
        # Starts at (12, 8) -> Ends at (12, 1)
        add_line((12, 8), (12, 1), (0, -1))
        
        
        # ================= CONNECTIONS: Top Road <-> Roundabout =================
        
        # A. Entering Roundabout (Down Lane)
        # Car arrives at (11, 8) on the North Corridor.
        # It merges with the Leftward flow of the ring.
        # Flow on ring is (12,8)->(11,8)->(10,8).
        # Our Down Lane ends at (11,8). 
        # So we connect (11,8) -> (10,8) is already implied by the Ring.
        # But we need to ensure the Down Lane node connects to the Ring node.
        # Since they are the SAME coordinate, they are connected automatically!
        
        # B. Exiting Roundabout (Up Lane)
        # Car is at (12, 8) (Top-Right corner of Ring).
        # Choice 1: Turn Left (Continue on Ring) -> (11, 8) [Existing Edge]
        # Choice 2: Turn Up (Exit to Top Road) -> (12, 7)
        self.graph.add_edge((12, 8), (12, 7), weight=1)


        # ================= CONNECTIONS: Top Road <-> Perimeter =================
        self.graph.add_edge((11, 1), (11, 2), weight=1) # Enter City
        self.graph.add_edge((12, 1), (11, 1), weight=1) # Exit City (Merge Left)


        # ================= PARKING SPOTS =================
        road_nodes = list(self.graph.nodes)
        for pid, pos in self.parking_spots.items():
            self.graph.add_node(pos)
            self.city_layout[pos[0]][pos[1]] = PARKING
            nearest = min(road_nodes, key=lambda n: (n[0]-pos[0])**2 + (n[1]-pos[1])**2)
            self.graph.add_edge(pos, nearest, weight=1)
            self.graph.add_edge(nearest, pos, weight=1)