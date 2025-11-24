import mesa
from mesa import Model
from mesa.space import ContinuousSpace
from mesa.datacollection import DataCollector
import networkx as nx
from agents import VehicleAgent, TrafficLightAgent

class TrafficModel(Model):
    def __init__(self, num_vehicles=5):
        super().__init__()
        self.num_vehicles = num_vehicles
        self.step_count = 0
        
        self.space = ContinuousSpace(x_max=24, y_max=24, torus=False)
        self.agents_list = [] 
        
        self.graph = nx.DiGraph()
        self.parking_spots = {} 
        self.traffic_lights = [] 
        
        self.build_city_graph()
        
        # --- AGENT PLACEMENT ---
        light_configs = [
            (12, 1, "RED"), (2, 5, "RED"), (10, 2, "GREEN"), 
            (0, 3, "GREEN"), (0, 7, "GREEN"), (23, 6, "GREEN"), 
            (23, 12, "GREEN"), (12, 23, "RED"), (21, 5, "RED"), (21, 10, "RED")
        ]
        
        for (x, y, state) in light_configs:
            pos = (x + 0.5, y + 0.5) 
            tl_agent = TrafficLightAgent(f"TL_{x}_{y}", self, direction="N")
            tl_agent.state = state
            self.space.place_agent(tl_agent, pos)
            self.agents_list.append(tl_agent)
            self.traffic_lights.append(tl_agent)

        parking_ids = list(self.parking_spots.keys())
        
        for i in range(self.num_vehicles):
            # Try to find a valid Start/End pair (Retry logic)
            path_found = False
            vehicle = None
            
            for attempt in range(10): # Try 10 times to find a valid route
                start_id = self.random.choice(parking_ids)
                dest_id = self.random.choice([pid for pid in parking_ids if pid != start_id])
                
                start_pos = self.parking_spots[start_id]
                dest_pos = self.parking_spots[dest_id]
                
                # Snap to nodes
                start_node = self.get_nearest_node(start_pos)
                dest_node = self.get_nearest_node(dest_pos)
                
                try:
                    path_nodes = nx.shortest_path(self.graph, start_node, dest_node)
                    # If we get here, path exists
                    vehicle = VehicleAgent(f"Car_{i}", self, start_node, dest_node)
                    vehicle.path = [(x + 0.5, y + 0.5) for x, y in path_nodes]
                    
                    spawn_pos = (start_node[0] + 0.5, start_node[1] + 0.5)
                    self.space.place_agent(vehicle, spawn_pos)
                    self.agents_list.append(vehicle)
                    path_found = True
                    print(f"Car_{i}: Route found from P{start_id} to P{dest_id}")
                    break
                except nx.NetworkXNoPath:
                    continue # Try another pair
            
            if not path_found:
                print(f"CRITICAL: Car_{i} could not find a valid path after 10 attempts.")

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
        def add_line(start, end, direction):
            curr = list(start)
            while True:
                node_curr = tuple(curr)
                next_x = curr[0] + direction[0]
                next_y = curr[1] + direction[1]
                node_next = (next_x, next_y)
                self.graph.add_node(node_curr)
                self.graph.add_node(node_next)
                self.graph.add_edge(node_curr, node_next)
                if node_curr == end: break
                curr[0], curr[1] = next_x, next_y

        # --- 1. LINES (Straight Roads) ---
        add_line((22, 1), (1, 1), (-1, 0))   # Top 
        add_line((1, 1), (1, 22), (0, 1))    # Left 
        add_line((1, 22), (22, 22), (1, 0))  # Bottom
        add_line((22, 22), (22, 1), (0, -1)) # Right
        add_line((4, 5), (1, 5), (-1, 0))     # Row 6 Left
        add_line((13, 5), (21, 5), (1, 0))    # Row 6 Right
        add_line((1, 11), (9, 11), (1, 0))    # Row 12 Left
        add_line((14, 11), (22, 11), (1, 0))  # Row 12 Right
        add_line((1, 16), (8, 16), (1, 0))    # Row 17 Left
        add_line((21, 16), (14, 16), (-1, 0)) # Row 17 Right
        add_line((8, 1), (8, 9), (0, 1))      # Col 9 Top
        add_line((8, 13), (8, 22), (0, 1))    # Col 9 Bottom
        add_line((10, 9), (10, 3), (0, -1))   # Col 11 Top (Up)
        add_line((12, 20), (12, 13), (0, -1)) # Col 13 Bottom (Up)
        add_line((14, 22), (14, 13), (0, -1)) # Col 15 Bottom (Up)
        add_line((14, 3), (14, 10), (0, 1))   # Col 15 Top (Down)

        # --- 2. ROUNDABOUT ---
        ra_nodes = [(10,10), (13,10), (13,12), (10,12)]
        for i in range(len(ra_nodes)):
            u, v = ra_nodes[i], ra_nodes[(i+1)%len(ra_nodes)]
            self.graph.add_edge(u, v)

        # --- 3. CONNECTIONS (Stitching the lines) ---
        
        # Outer Ring Corners
        self.graph.add_edge((1,1), (1,2))     # Top-Left Corner Turn
        self.graph.add_edge((1,22), (2,22))   # Bottom-Left Corner Turn
        self.graph.add_edge((22,22), (22,21)) # Bottom-Right Corner Turn
        self.graph.add_edge((22,1), (21,1))   # Top-Right Corner Turn

        # Connecting Inner Roads to Roundabout
        self.graph.add_edge((8,9), (10,10))   # Col 9 Top -> Roundabout Top-Left
        self.graph.add_edge((9,11), (10,12))  # Row 12 Left -> Roundabout Bottom-Left
        self.graph.add_edge((12,13), (13,12)) # Col 13 Bottom -> Roundabout Bottom-Right
        self.graph.add_edge((14,10), (13,10)) # Col 15 Top -> Roundabout Top-Right

        # Connecting Roundabout to Exits
        self.graph.add_edge((10,10), (10,9))  # Roundabout -> Col 11 Up (Wait, Col 11 goes UP away?)
        self.graph.add_edge((13,12), (14,11)) # Roundabout -> Row 12 Right
        # Note: Directions must match image arrows perfectly. 
        
        # Crossing Connections (Where lines meet perpendicularly)
        # Row 6 Left intersects Col 9? (4,5) to (1,5). Col 9 is x=8. No intersection.
        # Row 6 Left meets Left Wall (1,5). Can turn Down?
        self.graph.add_edge((1,5), (1,6))     # Merge into Outer Ring Left
        
        # Row 12 Left meets Outer Ring Left? (1,11). Can turn Down?
        self.graph.add_edge((1,11), (1,12))   # Merge... Wait, Outer Ring goes DOWN at x=1.
        # So Incoming Row 12 is (1,11). It flows RIGHT. It STARTS at (1,11).
        # It needs to be fed BY the Outer Ring.
        self.graph.add_edge((1,10), (1,11))   # Outer Ring feeds into Row 12 Left

        # Verify other feeds
        self.graph.add_edge((8,1), (9,1))     # Outer Ring Top feeds Col 9 Top? (Maybe)
        self.graph.add_edge((22,11), (22,10)) # Row 12 Right feeds Outer Ring Right (Up)

        # --- 4. PARKING SPOTS & DRIVEWAYS ---
        self.parking_spots = {
            1: (12, 19), 2: (13, 4), 3: (15, 14), 4: (14, 21),
            5: (14, 7), 10: (21, 3), 13: (3, 4), 17: (7, 7)
        }
        road_nodes = list(self.graph.nodes)
        for pid, pos in self.parking_spots.items():
            self.graph.add_node(pos)
            nearest = min(road_nodes, key=lambda n: (n[0]-pos[0])**2 + (n[1]-pos[1])**2)
            self.graph.add_edge(pos, nearest)
            self.graph.add_edge(nearest, pos)