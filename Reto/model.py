import mesa
from mesa import Model
from mesa.space import ContinuousSpace
from mesa.datacollection import DataCollector
import networkx as nx
from agents import VehicleAgent, TrafficLightAgent, TrafficManagerAgent

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
        
        self.space = ContinuousSpace(x_max=25, y_max=25, torus=False)
        self.agents_list = [] 
        self.city_layout = [[BUILDING for y in range(25)] for x in range(25)]
        self.graph = nx.DiGraph()
        self.parking_spots = {} 
        self.traffic_lights = [] 
        
        self.build_city_graph()
        
        # ==========================================
        # 1. Grupo 1 Semaforo 
        # ==========================================

        m1_1 = TrafficManagerAgent("Manager1.1", self, green_time=20)
        m1_2 = TrafficManagerAgent("Manager1.2", self, green_time=20)
        m1_3 = TrafficManagerAgent("Manager1.3", self, green_time=20)
        
        m1_1.set_next(m1_2)
        m1_2.set_next(m1_3)
        m1_3.set_next(m1_1)
        
        m1_1.activate()
        
        # ==========================================
        # 1. Grupo 2 Semaforo 
        # ==========================================

        m2_1 = TrafficManagerAgent("Manager2.1", self, green_time=20)
        m2_2 = TrafficManagerAgent("Manager2.2", self, green_time=20)
        
        m2_1.set_next(m2_2)
        m2_2.set_next(m2_1)
        
        m2_1.activate()
        
        # ==========================================
        # 1. Grupo 3 Semaforo 
        # ==========================================

        m3_1 = TrafficManagerAgent("Manager3.1", self, green_time=20)
        m3_2 = TrafficManagerAgent("Manager3.2", self, green_time=20)
        
        m3_1.set_next(m3_2)
        m3_2.set_next(m3_1)
        
        m3_1.activate()
        
        # ==========================================
        # COLOCACIÓN DE LAS LUCES FÍSICAS
        # ==========================================
        self.agents_list.extend([m1_1, m1_2, m1_3, m2_1, m2_2, m3_1, m3_2])
        
        light_position = [
            (0, 3, m1_1), (1, 3, m1_1),
            (2, 4, m1_2), (2, 5, m1_2),
            (2, 8, m1_3), (2, 9, m1_3),
            (7, 23, m2_1), (7, 24, m2_1),
            (8, 22, m2_2), (9, 22, m2_2),
            (11, 2, m3_1), (12, 2, m3_1),
            (13, 0, m3_2), (13, 1, m3_2),
        ]
        
        for (x, y, manager) in light_position:
            pos = (x + 0.5, y + 0.5)
            # Crear el agente físico
            tl_agent = TrafficLightAgent(f"TL_{x}_{y}", self, manager)
            
            # Ponerlo en el mapa
            self.space.place_agent(tl_agent, pos)
            
            # Agregarlo a las listas para que exista en la simulación
            self.agents_list.append(tl_agent)
            self.traffic_lights.append(tl_agent)

        # ==========================================
        # 3. PARKING Y VEHÍCULOS (Tu código original)
        # ==========================================
        self.parking_spots = {
             1: (21, 2), 2: (22, 16), 3: (15, 22), 4: (4, 22),   
             5: (21, 22), 6: (13, 19), 7: (20, 13), 8: (3, 13),
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
        # NOTA: Ya no llamamos a self.main_intersection.step()
        # Los TrafficManagerAgent se actualizan automáticamente en el bucle de abajo
        # porque los añadimos a self.agents_list
        
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

        # ================= PERIMETER =================
        add_line((24, 0), (0, 0), (-1, 0))
        add_line((23, 1), (1, 1), (-1, 0))
        add_line((0, 0), (0, 24), (0, 1))
        add_line((1, 1), (1, 23), (0, 1))
        add_line((0, 24), (24, 24), (1, 0))
        add_line((1, 23), (23, 23), (1, 0))
        add_line((24, 24), (24, 0), (0, -1))
        add_line((23, 23), (23, 1), (0, -1))

        self.graph.add_edge((12, 0), (11, 1), weight=3)
        self.graph.add_edge((12, 1), (11, 0), weight=3)
        self.graph.add_edge((0, 12), (1, 13), weight=3)
        self.graph.add_edge((1, 12), (0, 13), weight=3)
        self.graph.add_edge((12, 24), (13, 23), weight=3)
        self.graph.add_edge((12, 23), (13, 24), weight=3)
        self.graph.add_edge((24, 12), (23, 11), weight=3)
        self.graph.add_edge((23, 12), (24, 11), weight=3)

        self.graph.add_edge((24, 0), (23, 0), weight=1)
        self.graph.add_edge((23, 0), (23, 1), weight=1)
        self.graph.add_edge((1, 1), (1, 2), weight=1)
        self.graph.add_edge((1, 23), (2, 23), weight=1)
        self.graph.add_edge((23, 23), (23, 22), weight=1)


        # ================= ROUNDABOUT (Corridor) =================
        add_line((12, 8), (8, 8), (-1, 0)) 
        add_line((8, 8), (8, 12), (0, 1))  
        add_line((8, 12), (12, 12), (1, 0)) 
        add_line((12, 12), (12, 8), (0, -1)) 
        
        self.graph.add_edge((8, 8), (8, 9), weight=1)   
        self.graph.add_edge((8, 12), (9, 12), weight=1) 
        self.graph.add_edge((12, 12), (12, 11), weight=1) 
        self.graph.add_edge((12, 8), (11, 8), weight=1)   

        for x in range(9, 12):
            for y in range(9, 12):
                self.city_layout[x][y] = ROUNDABOUT


        # ================= 1. TOP ROAD (Flows DOWN into city) =================
        add_line((11, 8), (11, 1), (0, -1)) 
        add_line((12, 8), (12, 1), (0, -1)) 
        
        self.graph.add_edge((12, 7), (11, 6), weight=3)
        self.graph.add_edge((11, 7), (12, 6), weight=3)
        
        self.graph.add_edge((13, 1), (12, 1), weight=1)
        self.graph.add_edge((12, 1), (11, 1), weight=1)
        self.graph.add_edge((11, 8), (11, 7), weight=1)
        self.graph.add_edge((12, 8), (12, 7), weight=1)


        # ================= 2. BOTTOM ROAD (Flows DOWN out of city) =================
        add_line((11, 23), (11, 12), (0, -1)) 
        add_line((12, 23), (12, 12), (0, -1)) 
        
        self.graph.add_edge((11, 20), (12, 19), weight=3)
        self.graph.add_edge((12, 20), (11, 19), weight=3)
        
        self.graph.add_edge((12, 12), (11, 12), weight=1)
        self.graph.add_edge((11, 12), (10, 12), weight=1) 
        self.graph.add_edge((11, 23), (12, 23), weight=1)
        self.graph.add_edge((12, 23), (13, 23), weight=1)


        # ================= 1.2 TOP ROAD (Flows DOWN into city) =================
        add_line((8, 1), (8, 8), (0, 1)) 
        add_line((9, 1), (9, 8), (0, 1)) 
        
        self.graph.add_edge((8, 7), (9, 6), weight=3)
        self.graph.add_edge((9, 7), (8, 6), weight=3)
        
        self.graph.add_edge((10, 1), (9, 1), weight=1)
        self.graph.add_edge((9, 1), (8, 1), weight=1)
        self.graph.add_edge((8, 8), (9, 8), weight=1)
        self.graph.add_edge((9, 8), (10, 8), weight=1)


        # ================= 2.2 BOTTOM ROAD (Flows DOWN out of city) =================
        add_line((8, 12), (8, 23), (0, 1)) 
        add_line((9, 12), (9, 23), (0, 1)) 
        
        self.graph.add_edge((8, 14), (9, 15), weight=3)
        self.graph.add_edge((9, 14), (8, 15), weight=3)
        
        self.graph.add_edge((8, 12), (8, 13), weight=1)
        self.graph.add_edge((9, 12), (9, 13), weight=1)
        self.graph.add_edge((7, 23), (8, 23), weight=1)
        self.graph.add_edge((8, 23), (9, 23), weight=1)


        # ================= 3. LEFT ROAD (Flows RIGHT into city) =================
        add_line((1, 11), (8, 11), (1, 0)) 
        add_line((1, 12), (8, 12), (1, 0)) 
        
        self.graph.add_edge((4, 11), (5, 12), weight=3)
        self.graph.add_edge((4, 12), (5, 11), weight=3)
        
        self.graph.add_edge((1, 10), (1, 11), weight=1)
        self.graph.add_edge((1, 11), (1, 12), weight=1)
        self.graph.add_edge((8, 11), (8, 12), weight=1)
        self.graph.add_edge((8, 12), (8, 13), weight=1)


        # ================= 4. RIGHT ROAD (Flows RIGHT out of city) =================
        add_line((12, 11), (23, 11), (1, 0)) 
        add_line((12, 12), (23, 12), (1, 0)) 
        
        self.graph.add_edge((16, 11), (17, 12), weight=3)
        self.graph.add_edge((16, 12), (17, 11), weight=3)
        
        self.graph.add_edge((12, 12), (13, 12), weight=1)
        self.graph.add_edge((12, 11), (13, 11), weight=1)
        
        self.graph.add_edge((23, 12), (23, 11), weight=1)
        self.graph.add_edge((23, 11), (23, 10), weight=1)


        # ================= PARKING SPOTS =================
        road_nodes = list(self.graph.nodes)
        for pid, pos in self.parking_spots.items():
            self.graph.add_node(pos)
            self.city_layout[pos[0]][pos[1]] = PARKING
            nearest = min(road_nodes, key=lambda n: (n[0]-pos[0])**2 + (n[1]-pos[1])**2)
            self.graph.add_edge(pos, nearest, weight=1)
            self.graph.add_edge(nearest, pos, weight=1)