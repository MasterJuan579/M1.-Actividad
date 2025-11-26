import mesa
from mesa import Model
from mesa.space import ContinuousSpace
from mesa.datacollection import DataCollector
import networkx as nx
# Importamos los agentes necesarios
from agents import VehicleAgent, TrafficLightAgent, TrafficManagerAgent

# Tipos de Celda
BUILDING = 0
ROAD = 1
ROUNDABOUT = 2
PARKING = 3

class TrafficModel(Model):
    def __init__(self, num_vehicles=50): # Puedes poner aquí 30, 50, 100...
        super().__init__()
        self.num_vehicles = num_vehicles # Objetivo total de coches
        self.vehicles_spawned = 0        # Contador de coches ya generados
        self.step_count = 0
        
        self.space = ContinuousSpace(x_max=25, y_max=25, torus=False)
        self.agents_list = [] 
        self.city_layout = [[BUILDING for y in range(25)] for x in range(25)]
        self.graph = nx.DiGraph()
        self.parking_spots = {} 
        self.traffic_lights = [] 
        
        # Construimos el mapa (calles y conexiones)
        self.build_city_graph()
        
        # ==========================================
        # 1. CREACIÓN DE CEREBROS (MANAGERS)
        # ==========================================
        # GRUPO 1
        m1_1 = TrafficManagerAgent("Manager1.1", self, green_time=20)
        m1_2 = TrafficManagerAgent("Manager1.2", self, green_time=20)
        m1_3 = TrafficManagerAgent("Manager1.3", self, green_time=20)
        m1_1.set_next(m1_2); m1_2.set_next(m1_3); m1_3.set_next(m1_1)
        m1_1.activate()
        
        # GRUPO 2
        m2_1 = TrafficManagerAgent("Manager2.1", self, green_time=20)
        m2_2 = TrafficManagerAgent("Manager2.2", self, green_time=20)
        m2_1.set_next(m2_2); m2_2.set_next(m2_1)
        m2_1.activate()
        
        # GRUPO 3
        m3_1 = TrafficManagerAgent("Manager3.1", self, green_time=20)
        m3_2 = TrafficManagerAgent("Manager3.2", self, green_time=20)
        m3_1.set_next(m3_2); m3_2.set_next(m3_1)
        m3_1.activate()
        
        # GRUPO 4
        m4_1 = TrafficManagerAgent("Manager4.1", self, green_time=40)
        m4_2 = TrafficManagerAgent("Manager4.2", self, green_time=40)
        m4_3 = TrafficManagerAgent("Manager4.3", self, green_time=40)
        m4_1.set_next(m4_2); m4_2.set_next(m4_3); m4_3.set_next(m4_1)
        m4_1.activate()
        
        self.agents_list.extend([m1_1, m1_2, m1_3, m2_1, m2_2, m3_1, m3_2, m4_1, m4_2, m4_3])
        
        # ==========================================
        # 2. COLOCACIÓN DE LAS LUCES FÍSICAS
        # ==========================================
        light_position = [
            # Grupo 1
            (0, 3, m1_1), (1, 3, m1_1), (2, 4, m1_2), (2, 5, m1_2), (2, 8, m1_3), (2, 9, m1_3),
            # Grupo 2
            (7, 23, m2_1), (7, 24, m2_1), (8, 22, m2_2), (9, 22, m2_2),
            # Grupo 3
            (11, 2, m3_1), (12, 2, m3_1), (13, 0, m3_2), (13, 1, m3_2),
            # Grupo 4
            (8, 7, m4_1), (9, 7, m4_1), (13, 8, m4_2), (13, 9, m4_2), (11, 13, m4_3), (12, 13, m4_3),
        ]
        
        for (x, y, manager) in light_position:
            pos = (x + 0.5, y + 0.5)
            tl_agent = TrafficLightAgent(f"TL_{x}_{y}", self, manager)
            self.space.place_agent(tl_agent, pos)
            self.agents_list.append(tl_agent)
            self.traffic_lights.append(tl_agent)

        # ==========================================
        # 3. PARKING
        # ==========================================
        self.parking_spots = {
             1: (21, 2), 2: (22, 16), 3: (15, 22), 4: (4, 22),   
             5: (21, 22), 6: (13, 19), 7: (20, 13), 8: (3, 13),
             9: (3, 3), 10: (7, 6), 11: (14, 3), 12: (15, 6), 13:(20, 7) 
        }
        
        # NOTA: Eliminamos el bucle "for i in range(num_vehicles)" de aquí.
        # Ahora se maneja dinámicamente en spawn_vehicles()
        
        self.datacollector = DataCollector(
            model_reporters={
                "Stopped_Cars": lambda m: sum(1 for a in m.agents_list if isinstance(a, VehicleAgent) and a.speed < 0.01),
                "Average_Speed": lambda m: self.get_avg_speed()
            }
        )
        
        # Intentamos generar los primeros coches al iniciar
        self.spawn_vehicles()

    def get_avg_speed(self):
        speeds = [a.speed for a in self.agents_list if isinstance(a, VehicleAgent)]
        return sum(speeds) / len(speeds) if speeds else 0
    
    def get_nearest_node(self, pos):
        return min(self.graph.nodes, key=lambda n: (n[0]-pos[0])**2 + (n[1]-pos[1])**2)

    def spawn_vehicles(self):
        """
        Genera coches nuevos si hay espacio en los parkings y no hemos 
        alcanzado el límite total de coches.
        """
        # Si ya generamos todos los coches requeridos, no hacemos nada
        if self.vehicles_spawned >= self.num_vehicles:
            return

        # 1. Identificar estacionamientos LIBRES
        parking_ids = list(self.parking_spots.keys())
        free_spots = []
        
        for pid in parking_ids:
            pos = self.parking_spots[pid]
            # Buscamos agentes en esa celda exacta
            cell_contents = self.space.get_neighbors(pos, radius=0.4, include_center=True)
            
            is_free = True
            for agent in cell_contents:
                if isinstance(agent, VehicleAgent):
                    is_free = False
                    break
            
            if is_free:
                free_spots.append(pid)

        # 2. Generar coches en los espacios libres
        self.random.shuffle(free_spots) # Mezclar para variedad
        
        for start_id in free_spots:
            # Doble verificación por si llenamos el cupo en este mismo bucle
            if self.vehicles_spawned >= self.num_vehicles:
                break
                
            dest_id = self.random.choice([pid for pid in parking_ids if pid != start_id])
            
            start_pos = self.parking_spots[start_id]
            dest_pos = self.parking_spots[dest_id]
            
            start_node = self.get_nearest_node(start_pos)
            dest_node = self.get_nearest_node(dest_pos)
            
            try:
                path_nodes = nx.shortest_path(self.graph, start_node, dest_node, weight='weight')
                
                # Crear vehículo
                vehicle = VehicleAgent(f"Car_{self.vehicles_spawned}", self, start_node, dest_node)
                vehicle.path = [(x + 0.5, y + 0.5) for x, y in path_nodes]
                
                # Colocarlo
                spawn_pos = (start_pos[0] + 0.5, start_pos[1] + 0.5)
                self.space.place_agent(vehicle, spawn_pos)
                self.agents_list.append(vehicle)
                
                self.vehicles_spawned += 1
                # print(f"Spawned Car_{self.vehicles_spawned} at Parking {start_id}")
                
            except nx.NetworkXNoPath:
                continue

    def step(self):
        # 1. Intentar generar nuevos coches si hay hueco
        self.spawn_vehicles()
        
        # 2. Limpieza: Eliminar agentes que ya llegaron (ARRIVED) de la lista de memoria
        # Esto es importante para que el simulador no se vuelva lento
        self.agents_list = [a for a in self.agents_list if getattr(a, "state", "") != "ARRIVED"]

        # 3. Ejecución normal
        self.datacollector.collect(self)
        self.random.shuffle(self.agents_list)
        for agent in self.agents_list:
            agent.step()
        for agent in self.agents_list:
            if hasattr(agent, "advance"):
                agent.advance()     
        self.step_count += 1

    def build_city_graph(self):
        # ... (Aquí va todo tu código de grafos, sin cambios) ...
        # Asegúrate de incluir todo el contenido de build_city_graph que ya tenías
        # incluyendo la corrección de la calle derecha y las nuevas calles oeste.
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

        # [PEGAR AQUÍ TODO EL RESTO DE TU build_city_graph QUE YA FUNCIONABA]
        # ...
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
        
        # ================= 5. EAST ROAD (Flows RIGHT out of city) =================
        add_line((12, 4), (23, 4), (1, 0)) 
        add_line((12, 5), (23, 5), (1, 0)) 
        
        self.graph.add_edge((13, 5), (14, 4), weight=3)
        self.graph.add_edge((13, 4), (14, 5), weight=3)
        
        self.graph.add_edge((23, 5), (23, 4), weight=1)
        self.graph.add_edge((23, 4), (23, 3), weight=1) 
        
        self.graph.add_edge((12, 4), (13, 4), weight=1)
        self.graph.add_edge((12, 5), (13, 5), weight=1)
        
        
        # ================= 6. NUEVAS CALLES OESTE (Salida al Perímetro) =================
        # Estas calles conectan la vía vertical interna (x=8) con el perímetro (x=1)
        # viajando hacia el OESTE (-1, 0).
        
        # --- BLOQUE SUPERIOR (Para los semáforos en y=4, y=5) ---
        # 1. Crear la geometría de la calle (Nodos y Asfalto)
        add_line((8, 4), (1, 4), (-1, 0)) # Carril superior
        add_line((8, 5), (1, 5), (-1, 0)) # Carril inferior
        
        # 2. Conectar ENTRADA: Permitir que los coches en x=8 giren a estas calles
        # (Asumimos que pueden girar desde la columna 8 hacia la 7)
        self.graph.add_edge((8, 4), (7, 4), weight=2)
        self.graph.add_edge((8, 5), (7, 5), weight=2)
        
        # 3. Conectar SALIDA: Del semáforo (x=2) al perímetro (x=1)
        self.graph.add_edge((2, 4), (1, 4), weight=1)
        self.graph.add_edge((2, 5), (1, 5), weight=1)

        # --- BLOQUE CENTRAL (Para los semáforos en y=8, y=9) ---
        # 1. Crear la geometría
        add_line((8, 8), (1, 8), (-1, 0))
        add_line((8, 9), (1, 9), (-1, 0))
        
        # 2. Conectar ENTRADA
        self.graph.add_edge((8, 8), (7, 8), weight=2)
        self.graph.add_edge((8, 9), (7, 9), weight=2)
        
        # 3. Conectar SALIDA al perímetro
        self.graph.add_edge((2, 8), (1, 8), weight=1)
        self.graph.add_edge((2, 9), (1, 9), weight=1)
        
        # ================= 6. EAST ROAD (Flows RIGHT out of city) =================
        add_line((23, 8), (12, 8), (-1, 0)) 
        add_line((23, 9), (12, 9), (-1, 0)) 
        
        self.graph.add_edge((21, 9), (20, 8), weight=3)
        self.graph.add_edge((21, 8), (20, 9), weight=3)
        
        self.graph.add_edge((12, 8), (12, 9), weight=1)
        self.graph.add_edge((12, 9), (12, 10), weight=1) 
        
        self.graph.add_edge((23, 8), (22, 8), weight=1)
        self.graph.add_edge((23, 9), (22, 9), weight=1)


        # ================= PARKING SPOTS =================
        road_nodes = list(self.graph.nodes)
        for pid, pos in self.parking_spots.items():
            self.graph.add_node(pos)
            self.city_layout[pos[0]][pos[1]] = PARKING
            nearest = min(road_nodes, key=lambda n: (n[0]-pos[0])**2 + (n[1]-pos[1])**2)
            self.graph.add_edge(pos, nearest, weight=1)
            self.graph.add_edge(nearest, pos, weight=1)