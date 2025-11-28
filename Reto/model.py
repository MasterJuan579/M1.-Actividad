import mesa
from mesa import Model
from mesa.space import ContinuousSpace
from mesa.datacollection import DataCollector
import networkx as nx
from agents import VehicleAgent, TrafficLightAgent, TrafficManagerAgent

# --- CONSTANTES DE TIPOS DE CELDA ---
BUILDING = 0
ROAD = 1
ROUNDABOUT = 2
PARKING = 3

class TrafficModel(Model):
    def __init__(self, num_vehicles=100): 
        super().__init__()
        self.num_vehicles = num_vehicles 
        self.vehicles_spawned = 0        
        self.step_count = 0
        
        # --- CONFIGURACIÓN DE COOLDOWN (ESPERA) ---
        # 30 pasos = 3 segundos reales aprox. (si speed=0.1)
        self.spawn_cooldown = 30 
        self.parking_schedule = {} 
        
        # --- ESPACIO Y AGENTES ---
        self.space = ContinuousSpace(x_max=25, y_max=25, torus=False)
        self.agents_list = [] 
        self.city_layout = [[BUILDING for y in range(25)] for x in range(25)]
        self.graph = nx.DiGraph()
        self.parking_spots = {} 
        self.traffic_lights = [] 
        
        # Construimos el mapa (calles y conexiones)
        self.build_city_graph()
        
        # ===================================================
        #       1. GESTORES DE TRÁFICO (CEREBROS)
        # ===================================================
        
        # --- GRUPO 1: Intersección Izquierda/Arriba ---
        m1_1 = TrafficManagerAgent("Manager1.1", self, green_time=20)
        m1_2 = TrafficManagerAgent("Manager1.2", self, green_time=20)
        m1_1.set_next(m1_2); m1_2.set_next(m1_1);
        m1_1.activate()
        
        # --- GRUPO 2: Intersección Abajo/Derecha ---
        m2_1 = TrafficManagerAgent("Manager2.1", self, green_time=20)
        m2_2 = TrafficManagerAgent("Manager2.2", self, green_time=20)
        m2_1.set_next(m2_2); m2_2.set_next(m2_1)
        m2_1.activate()
        
        # --- GRUPO 3: Intersección Arriba/Derecha ---
        m3_1 = TrafficManagerAgent("Manager3.1", self, green_time=20)
        m3_2 = TrafficManagerAgent("Manager3.2", self, green_time=20)
        m3_1.set_next(m3_2); m3_2.set_next(m3_1)
        m3_1.activate()
        
        # --- GRUPO 4: Intersección Central/Compleja ---
        m4_1 = TrafficManagerAgent("Manager4.1", self, green_time=20)
        m4_2 = TrafficManagerAgent("Manager4.2", self, green_time=20)
        m4_1.set_next(m4_2); m4_2.set_next(m4_1);
        m4_1.activate()
        
        # Registrar todos los managers para que corra su reloj interno
        self.agents_list.extend([m1_1, m1_2, m2_1, m2_2, m3_1, m3_2, m4_1, m4_2])
        
        # ===================================================
        #       2. SEMÁFOROS FÍSICOS (LUCES)
        # ===================================================
        light_position = [
            # Grupo 1
            (0, 3, m1_1), (1, 3, m1_1), (2, 4, m1_2), (2, 5, m1_2), (2, 8, m1_2), (2, 9, m1_2),
            # Grupo 2
            (7, 23, m2_1), (7, 24, m2_1), (8, 22, m2_2), (9, 22, m2_2),
            (16, 23, m2_1), (16, 24, m2_1), (17, 22, m2_2), (18, 22, m2_2),
            # Grupo 3
            (11, 2, m3_1), (12, 2, m3_1), (13, 0, m3_2), (13, 1, m3_2),
            # Grupo 4
            (22, 4, m4_1), (22, 5, m4_1), (22, 11, m4_1), (22, 12, m4_1),
            (23, 6, m4_2), (24, 6, m4_2), (23, 13, m4_2), (24, 13, m4_2),
        ]
        
        for (x, y, manager) in light_position:
            pos = (x + 0.5, y + 0.5)
            tl_agent = TrafficLightAgent(f"TL_{x}_{y}", self, manager)
            self.space.place_agent(tl_agent, pos)
            self.agents_list.append(tl_agent)
            self.traffic_lights.append(tl_agent)

        # ===================================================
        #       3. ESTACIONAMIENTOS (PARKINGS)
        # ===================================================
        self.parking_spots = {
             1: (21, 2), 2: (22, 16), 3: (15, 22), 4: (4, 22),   
             5: (21, 22), 6: (13, 19), 7: (20, 13), 8: (3, 13),
             9: (3, 3), 10: (7, 6), 11: (14, 3), 12: (15, 6), 13: (20, 7),
             14: (6, 15), 15: (6, 18), 16: (15, 15), 17: (19, 20)
        }
        
        # Inicializamos historial de uso
        for pid in self.parking_spots:
            self.parking_schedule[pid] = -self.spawn_cooldown
        
        # ===================================================
        #       4. RECOLECCIÓN DE DATOS
        # ===================================================
        self.datacollector = DataCollector(
            model_reporters={
                "Stopped_Cars": lambda m: sum(1 for a in m.agents_list if isinstance(a, VehicleAgent) and a.speed < 0.01),
                "Average_Speed": lambda m: self.get_avg_speed()
            }
        )
        
        # Generación inicial de vehículos
        self.spawn_vehicles()

    # --- MÉTODOS AUXILIARES ---
    def get_avg_speed(self):
        speeds = [a.speed for a in self.agents_list if isinstance(a, VehicleAgent)]
        return sum(speeds) / len(speeds) if speeds else 0
    
    def get_nearest_node(self, pos):
        return min(self.graph.nodes, key=lambda n: (n[0]-pos[0])**2 + (n[1]-pos[1])**2)

    def spawn_vehicles(self):
        """ Genera coches nuevos respetando cooldown y espacio disponible. """
        if self.vehicles_spawned >= self.num_vehicles:
            return

        parking_ids = list(self.parking_spots.keys())
        free_spots = []
        
        for pid in parking_ids:
            # Verificar Cooldown
            last_used_step = self.parking_schedule.get(pid, -999)
            if (self.step_count - last_used_step) < self.spawn_cooldown:
                continue 

            # Verificar Espacio Físico
            pos = self.parking_spots[pid]
            cell_contents = self.space.get_neighbors(pos, radius=0.4, include_center=True)
            is_free = not any(isinstance(agent, VehicleAgent) for agent in cell_contents)
            
            if is_free:
                free_spots.append(pid)

        self.random.shuffle(free_spots) 
        
        for start_id in free_spots:
            if self.vehicles_spawned >= self.num_vehicles:
                break
                
            dest_id = self.random.choice([pid for pid in parking_ids if pid != start_id])
            start_pos = self.parking_spots[start_id]
            dest_pos = self.parking_spots[dest_id]
            start_node = self.get_nearest_node(start_pos)
            dest_node = self.get_nearest_node(dest_pos)
            
            try:
                path_nodes = nx.shortest_path(self.graph, start_node, dest_node, weight='weight')
                vehicle = VehicleAgent(f"Car_{self.vehicles_spawned}", self, start_node, dest_node)
                vehicle.path = [(x + 0.5, y + 0.5) for x, y in path_nodes]
                
                spawn_pos = (start_pos[0] + 0.5, start_pos[1] + 0.5)
                self.space.place_agent(vehicle, spawn_pos)
                self.agents_list.append(vehicle)
                
                self.vehicles_spawned += 1
                self.parking_schedule[start_id] = self.step_count
                
            except nx.NetworkXNoPath:
                continue

    def step(self):
        self.spawn_vehicles()
        
        # Limpieza de agentes que ya llegaron
        self.agents_list = [a for a in self.agents_list if getattr(a, "state", "") != "ARRIVED"]

        self.datacollector.collect(self)
        self.random.shuffle(self.agents_list)
        
        for agent in self.agents_list:
            agent.step()
        for agent in self.agents_list:
            if hasattr(agent, "advance"):
                agent.advance()     
        self.step_count += 1

    # =======================================================
    #               CONSTRUCCIÓN DEL GRAFO VIAL
    # =======================================================
    def build_city_graph(self):
        def add_line(start, end, direction, weight=1):
            curr = list(start)
            while curr != list(end):
                node_curr = tuple(curr)
                next_x = curr[0] + direction[0]
                next_y = curr[1] + direction[1]
                node_next = (next_x, next_y)
                if not (0 <= next_x < 25 and 0 <= next_y < 25): break
                self.graph.add_node(node_curr)
                self.graph.add_node(node_next)
                self.graph.add_edge(node_curr, node_next, weight=weight)
                self.city_layout[curr[0]][curr[1]] = ROAD
                self.city_layout[next_x][next_y] = ROAD
                curr[0], curr[1] = next_x, next_y

        # ---------------------------------------------------
        # 1. PERÍMETRO (Ring Exterior)
        # ---------------------------------------------------
        # Geometría
        add_line((24, 0), (0, 0), (-1, 0))
        add_line((23, 1), (1, 1), (-1, 0))
        add_line((0, 0), (0, 24), (0, 1))
        add_line((1, 1), (1, 23), (0, 1))
        add_line((0, 24), (24, 24), (1, 0))
        add_line((1, 23), (23, 23), (1, 0))
        add_line((24, 24), (24, 0), (0, -1))
        add_line((23, 23), (23, 1), (0, -1))

        # Conexiones de Perímetro
        self.graph.add_edge((12, 0), (11, 1), weight=3)
        self.graph.add_edge((12, 1), (11, 0), weight=3)
        self.graph.add_edge((0, 12), (1, 13), weight=3)
        self.graph.add_edge((1, 12), (0, 13), weight=3)
        self.graph.add_edge((12, 24), (13, 23), weight=3)
        self.graph.add_edge((12, 23), (13, 24), weight=3)
        self.graph.add_edge((24, 12), (23, 11), weight=3)
        self.graph.add_edge((23, 12), (24, 11), weight=3)

        # Giros en esquinas
        self.graph.add_edge((24, 0), (23, 0), weight=1)
        self.graph.add_edge((23, 0), (23, 1), weight=1)
        self.graph.add_edge((1, 1), (1, 2), weight=1)
        self.graph.add_edge((1, 23), (2, 23), weight=1)
        self.graph.add_edge((23, 23), (23, 22), weight=1)

        # ---------------------------------------------------
        # 2. ROTONDA CENTRAL (Hub)
        # ---------------------------------------------------
        add_line((12,8),(8,8),(-1,0))
        add_line((8,8),(8,12),(0,1))
        add_line((8,12),(12,12),(1,0))
        add_line((12,12),(12,8),(0,-1))
        
        self.graph.add_edge((8,8),(8,9))
        self.graph.add_edge((8,12),(9,12))
        self.graph.add_edge((12,12),(12,11))
        self.graph.add_edge((12,8),(11,8))
        
        # --- CORRECCIÓN VISUAL: Solo el centro es ROUNDABOUT (Café) ---
        # Los bordes (calles) se mantienen como ROAD (Gris)
        for x in range(9, 12):
            for y in range(9, 12):
                self.city_layout[x][y] = ROUNDABOUT


        # ---------------------------------------------------
        # 3. CARRETERAS VERTICALES (Norte-Sur)
        # ---------------------------------------------------
        # A. Top Road Right Side (Hacia Arriba - Salida)
        add_line((11, 8), (11, 1), (0, -1)) 
        add_line((12, 8), (12, 1), (0, -1)) 
        
        self.graph.add_edge((12, 7), (11, 6), weight=3)
        self.graph.add_edge((11, 7), (12, 6), weight=3)
        self.graph.add_edge((13, 1), (12, 1), weight=1)
        self.graph.add_edge((12, 1), (11, 1), weight=1)
        self.graph.add_edge((11, 8), (11, 7), weight=1)
        self.graph.add_edge((12, 8), (12, 7), weight=1)

        # B. Top Road Left Side (Hacia Abajo - Entrada)
        add_line((8, 1), (8, 8), (0, 1)) 
        add_line((9, 1), (9, 8), (0, 1)) 
        
        self.graph.add_edge((8, 7), (9, 6), weight=3)
        self.graph.add_edge((9, 7), (8, 6), weight=3)
        self.graph.add_edge((10, 1), (9, 1), weight=1)
        self.graph.add_edge((9, 1), (8, 1), weight=1)
        self.graph.add_edge((8, 8), (9, 8), weight=1)
        self.graph.add_edge((9, 8), (10, 8), weight=1)

        # C. Bottom Road Right Side (Hacia Abajo - Entrada)
        add_line((11, 23), (11, 12), (0, -1)) 
        add_line((12, 23), (12, 12), (0, -1)) 
        
        self.graph.add_edge((11, 20), (12, 19), weight=3)
        self.graph.add_edge((12, 20), (11, 19), weight=3)
        self.graph.add_edge((12, 12), (11, 12), weight=1)
        self.graph.add_edge((11, 12), (10, 12), weight=1) 
        self.graph.add_edge((11, 23), (12, 23), weight=1)
        self.graph.add_edge((12, 23), (13, 23), weight=1)

        # D. Bottom Road Left Side (Hacia Abajo - Salida)
        add_line((8, 12), (8, 23), (0, 1)) 
        add_line((9, 12), (9, 23), (0, 1)) 
        
        self.graph.add_edge((8, 14), (9, 15), weight=3)
        self.graph.add_edge((9, 14), (8, 15), weight=3)
        self.graph.add_edge((8, 12), (8, 13), weight=1)
        self.graph.add_edge((9, 12), (9, 13), weight=1)
        self.graph.add_edge((7, 23), (8, 23), weight=1)
        self.graph.add_edge((8, 23), (9, 23), weight=1)
        
        # E. 
        
        add_line((4, 1), (4, 4), (0,1))
        add_line((5, 1), (5, 4), (0,1))
        
        self.graph.add_edge((4, 2), (5, 3), weight=3)
        self.graph.add_edge((5, 2), (4, 3), weight=3)
        
        self.graph.add_edge((6, 1), (5, 1), weight=1)
        self.graph.add_edge((5, 1), (4, 1), weight=1)
        self.graph.add_edge((5, 4), (4, 4), weight=1)
        self.graph.add_edge((4, 4), (3, 4), weight=1)
        self.graph.add_edge((4, 4), (4, 5), weight=1)
        self.graph.add_edge((5, 4), (5, 5), weight=1)
        
        # F. 
        
        add_line((4, 6), (4, 8), (0,1))
        add_line((5, 6), (5, 8), (0,1))
        
        self.graph.add_edge((4, 6), (5, 7), weight=3)
        self.graph.add_edge((5, 6), (4, 7), weight=3)
        
        self.graph.add_edge((6, 5), (5, 5), weight=1)
        self.graph.add_edge((5, 5), (4, 5), weight=1)
        self.graph.add_edge((5, 5), (5, 6), weight=1)
        self.graph.add_edge((4, 5), (4, 6), weight=1)
        self.graph.add_edge((5, 8), (4, 8), weight=1)
        self.graph.add_edge((4, 8), (3, 8), weight=1)
        
        
        # G. 
        
        add_line((4, 17), (4, 12), (0, -1))
        add_line((5, 17), (5, 12), (0, -1))
        
        self.graph.add_edge((4, 15), (5, 14), weight=3)
        self.graph.add_edge((5, 15), (4, 14), weight=3)
        
        self.graph.add_edge((6, 12), (5, 12), weight=1)
        self.graph.add_edge((5, 12), (4, 12), weight=1)
        self.graph.add_edge((4, 17), (5, 17), weight=1)
        self.graph.add_edge((5, 17), (6, 17), weight=1)
        
        # G. 
        
        add_line((17, 12), (17, 23), (0, 1))
        add_line((18, 12), (18, 23), (0, 1))
        
        self.graph.add_edge((17, 14), (18, 15), weight=3)
        self.graph.add_edge((18, 14), (17, 15), weight=3)
        
        self.graph.add_edge((17, 19), (18, 20), weight=3)
        self.graph.add_edge((18, 19), (17, 20), weight=3)
        
        self.graph.add_edge((16, 12), (17, 12), weight=1)
        self.graph.add_edge((17, 12), (18, 12), weight=1)
        self.graph.add_edge((4, 17), (5, 17), weight=1)
        self.graph.add_edge((5, 17), (6, 17), weight=1)
        
        

        # ---------------------------------------------------
        # 4. CARRETERAS HORIZONTALES (Este-Oeste)
        # ---------------------------------------------------
        # A. Left Road (Hacia la Derecha - Entrada)
        add_line((1, 11), (8, 11), (1, 0)) 
        add_line((1, 12), (8, 12), (1, 0)) 
        
        self.graph.add_edge((4, 11), (5, 12), weight=3)
        self.graph.add_edge((4, 12), (5, 11), weight=3)
        self.graph.add_edge((1, 10), (1, 11), weight=1)
        self.graph.add_edge((1, 11), (1, 12), weight=1)
        self.graph.add_edge((8, 11), (8, 12), weight=1)
        self.graph.add_edge((8, 12), (8, 13), weight=1)

        # B. Right Road (Hacia la Derecha - Salida)
        add_line((12, 11), (23, 11), (1, 0)) 
        add_line((12, 12), (23, 12), (1, 0)) 
        
        self.graph.add_edge((16, 11), (17, 12), weight=3)
        self.graph.add_edge((16, 12), (17, 11), weight=3)
        self.graph.add_edge((12, 12), (13, 12), weight=1)
        self.graph.add_edge((12, 11), (13, 11), weight=1)
        self.graph.add_edge((23, 12), (23, 11), weight=1)
        self.graph.add_edge((23, 11), (23, 10), weight=1)
        
        # C. East Road (Inbound from right to center)
        add_line((23, 4), (12, 4), (-1, 0)) 
        add_line((23, 5), (12, 5), (-1, 0))
        
        self.graph.add_edge((18, 5), (17, 4), weight=3)
        self.graph.add_edge((18, 4), (17, 5), weight=3)
        self.graph.add_edge((12, 5), (12, 4), weight=1)
        self.graph.add_edge((12, 4), (12, 3), weight=1)
        self.graph.add_edge((23, 4), (22, 4), weight=1)
        self.graph.add_edge((23, 5), (22, 5), weight=1)
        
        # D. New West Roads (Outbound from center to left)
        # Top Block
        add_line((8, 4), (1, 4), (-1, 0)) 
        add_line((8, 5), (1, 5), (-1, 0)) 
        self.graph.add_edge((8, 4), (7, 4), weight=2)
        self.graph.add_edge((8, 5), (7, 5), weight=2)
        self.graph.add_edge((2, 4), (1, 4), weight=1)
        self.graph.add_edge((2, 5), (1, 5), weight=1)

        # Middle Block
        add_line((8, 8), (1, 8), (-1, 0))
        add_line((8, 9), (1, 9), (-1, 0)) 
        self.graph.add_edge((8, 8), (7, 8), weight=2)
        self.graph.add_edge((8, 9), (7, 9), weight=2)
        self.graph.add_edge((2, 8), (1, 8), weight=1)
        self.graph.add_edge((2, 9), (1, 9), weight=1)
        
        # E. East Road (Outbound from right to center - Lower)
        add_line((23, 8), (12, 8), (-1, 0)) 
        add_line((23, 9), (12, 9), (-1, 0)) 
        
        self.graph.add_edge((21, 9), (20, 8), weight=3)
        self.graph.add_edge((21, 8), (20, 9), weight=3)
        self.graph.add_edge((12, 8), (12, 9), weight=1)
        self.graph.add_edge((12, 9), (12, 10), weight=1) 
        self.graph.add_edge((23, 8), (22, 8), weight=1)
        self.graph.add_edge((23, 9), (22, 9), weight=1)
        
        # F. 
        add_line((1, 16), (8, 16), (1, 0)) 
        add_line((1, 17), (8, 17), (1, 0)) 
        
        self.graph.add_edge((4, 16), (5, 17), weight=3)
        self.graph.add_edge((4, 17), (5, 16), weight=3)
        self.graph.add_edge((1, 15), (1, 16), weight=1)
        self.graph.add_edge((1, 16), (1, 17), weight=1) 
        self.graph.add_edge((8, 16), (8, 17), weight=1)
        self.graph.add_edge((8, 17), (8, 18), weight=1)
        
        # G.
        add_line((17, 16), (12, 16), (-1, 0)) 
        add_line((18, 17), (12, 17), (-1, 0)) 
        
        self.graph.add_edge((16, 16), (15, 17), weight=3)
        self.graph.add_edge((16, 17), (15, 16), weight=3)
        self.graph.add_edge((17, 15), (17, 16), weight=1)
        self.graph.add_edge((17, 16), (17, 17), weight=1)
        self.graph.add_edge((12, 17), (12, 16), weight=1)
        self.graph.add_edge((12, 16), (12, 15), weight=1)

        # ---------------------------------------------------
        # 5. CONEXIÓN DE ESTACIONAMIENTOS
        # ---------------------------------------------------
        road_nodes = list(self.graph.nodes)
        for pid, pos in self.parking_spots.items():
            self.graph.add_node(pos)
            self.city_layout[pos[0]][pos[1]] = PARKING
            nearest = min(road_nodes, key=lambda n: (n[0]-pos[0])**2 + (n[1]-pos[1])**2)
            self.graph.add_edge(pos, nearest, weight=1)
            self.graph.add_edge(nearest, pos, weight=1)