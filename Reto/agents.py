from mesa import Agent
import numpy as np
import networkx as nx

PARKING = 3

class TrafficManagerAgent(Agent):
    """Agente Cerebro (Sin cambios)"""
    def __init__(self, unique_id, model, green_time=20, yellow_time=4):
        super().__init__(model)
        self.unique_id = unique_id
        self.green_time = green_time
        self.yellow_time = yellow_time
        self.state = "RED"
        self.time_remaining = 0
        self.next_manager = None 

    def set_next(self, manager_agent):
        self.next_manager = manager_agent

    def activate(self):
        self.state = "GREEN"
        self.time_remaining = self.green_time

    def step(self):
        if self.state == "GREEN":
            self.time_remaining -= 1
            if self.time_remaining <= 0:
                self.state = "YELLOW"
                self.time_remaining = self.yellow_time
        elif self.state == "YELLOW":
            self.time_remaining -= 1
            if self.time_remaining <= 0:
                self.state = "RED"
                if self.next_manager:
                    self.next_manager.activate()

class TrafficLightAgent(Agent):
    """Agente Cuerpo Físico (Sin cambios)"""
    def __init__(self, unique_id, model, manager):
        super().__init__(model)
        self.unique_id = unique_id
        self.manager = manager

    @property
    def state(self):
        return self.manager.state
    
    @state.setter
    def state(self, value):
        pass

    def step(self):
        pass

    def receive_eta(self, vehicle_id, eta):
        pass

class VehicleAgent(Agent):
    """
    Agente vehículo con Cambio de Carril Inteligente (Paciencia)
    """
    def __init__(self, unique_id, model, start_node, destination_node):
        super().__init__(model)
        self.unique_id = unique_id
        self.start = start_node
        self.destination = destination_node
        self.velocity = np.array([0.0, 0.0])
        self.speed = 0.0
        self.max_speed = 0.5
        self.acceleration = 0.05
        self.path = []
        self.state = "DRIVING"
        
        # --- NUEVO: SISTEMA DE PACIENCIA ---
        # Si la paciencia llega a 0, intenta cambiar de carril
        self.max_patience = 5  # Pasos de tolerancia antes de desesperarse
        self.patience = self.max_patience

    def try_change_lane(self):
        """
        Intenta buscar un nodo adyacente (carril lateral) que esté libre
        y que permita llegar al destino.
        """
        current_node = self.get_current_grid_pos()
        if current_node not in self.model.graph:
            return

        # Obtenemos los vecinos conectados en el grafo (posibles movimientos legales)
        # Nota: Esto incluye el nodo de adelante y los de los lados si hay conexión
        neighbors = list(self.model.graph.neighbors(current_node))
        
        # El nodo al que íbamos originalmente
        original_next_step = self.path[0] if self.path else None

        for neighbor in neighbors:
            # 1. No queremos ir al mismo lugar donde estamos bloqueados
            if neighbor == original_next_step:
                continue
            
            # 2. Verificar si el carril de al lado está físicamente libre
            # Usamos un radio pequeño para ver si la celda lateral está vacía
            cell_contents = self.model.space.get_neighbors(neighbor, radius=0.2, include_center=True)
            is_free = True
            for obj in cell_contents:
                if isinstance(obj, VehicleAgent):
                    is_free = False
                    break
            
            if is_free:
                # 3. ¿Ese carril me lleva a mi destino? (Recálculo de ruta)
                try:
                    # Calculamos nueva ruta desde el vecino
                    new_path = nx.shortest_path(self.model.graph, neighbor, self.destination, weight='weight')
                    
                    # 4. ÉXITO: Cambiamos de plan
                    self.path = [(x + 0.5, y + 0.5) for x, y in new_path]
                    # Reiniciamos paciencia
                    self.patience = self.max_patience
                    # Pequeña penalización de velocidad al cambiar de carril
                    self.speed = 0.1 
                    return # Ya cambiamos, salimos de la función
                    
                except nx.NetworkXNoPath:
                    continue

    def get_current_grid_pos(self):
        """Devuelve la posición entera (nodo del grafo) más cercana"""
        return (int(round(self.pos[0]-0.5)), int(round(self.pos[1]-0.5)))

    def step(self):
        if self.state == "ARRIVED": return

        # --- GESTIÓN DE PACIENCIA ---
        if self.speed < 0.1:
            self.patience -= 1
        else:
            self.patience = self.max_patience

        # Si se acabó la paciencia, intentamos cambiar de carril
        if self.patience <= 0:
            self.try_change_lane()

        # --- DATOS DE NAVEGACIÓN ---
        current_pos = np.array(self.pos)
        next_pos = self.path[0] if self.path else None
        
        if next_pos is None: return

        # Vector de dirección
        my_dx = next_pos[0] - current_pos[0]
        my_dy = next_pos[1] - current_pos[1]
        
        norm = np.linalg.norm([my_dx, my_dy])
        dir_vector = np.array([my_dx, my_dy]) / (norm if norm > 0 else 1)

        # --- CONTEXTO ---
        cx, cy = int(self.pos[0]), int(self.pos[1])
        is_in_parking = False
        if 0 <= cx < len(self.model.city_layout) and 0 <= cy < len(self.model.city_layout[0]):
            if self.model.city_layout[cx][cy] == PARKING:
                is_in_parking = True

        # Escaneo
        neighbors = self.model.space.get_neighbors(self.pos, radius=3.5, include_center=False)
        
        obstacle_ahead = False
        emergency_brake = False
        traffic_light = None
        
        blocking_car_distance = 999.9

        for agent in neighbors:
            # --- COCHES ---
            if isinstance(agent, VehicleAgent):
                if agent.state == "ARRIVED": continue

                other_pos = np.array(agent.pos)
                vec_to_other = other_pos - current_pos
                dist = np.linalg.norm(vec_to_other)

                # FILTRO DE ÁNGULO
                angle_match = np.dot(dir_vector, vec_to_other / (dist + 0.0001))
                
                if angle_match > 0.7:
                    if dist < blocking_car_distance:
                        blocking_car_distance = dist
                    
                    if dist < 0.9: 
                        emergency_brake = True
                        obstacle_ahead = True
                    elif dist < 1.8: 
                        obstacle_ahead = True

                # CASO ESPECIAL: SALIDA DE PARKING
                if is_in_parking:
                    dist_to_target = np.linalg.norm(other_pos - np.array(next_pos))
                    if dist_to_target < 1.5: 
                        obstacle_ahead = True
                        emergency_brake = True

            # --- SEMÁFOROS ---
            elif isinstance(agent, TrafficLightAgent):
                dist_light = self.model.space.get_distance(agent.pos, next_pos)
                if dist_light < 0.1:
                    traffic_light = agent

        # --- DECISIÓN ---
        target_speed = self.max_speed
        
        light_is_red = False
        if traffic_light:
            if traffic_light.state == "RED":
                target_speed = 0
                light_is_red = True
                self.speed = 0
            elif traffic_light.state == "YELLOW":
                target_speed = self.max_speed * 0.5

        if obstacle_ahead:
            target_speed = 0
            self.state = "BRAKING"
            if emergency_brake:
                self.speed = 0
        
        # --- KICKSTART (Anti-bloqueo) ---
        if self.speed < 0.01 and not light_is_red:
            if blocking_car_distance > 1.2:
                target_speed = self.max_speed 
                self.speed = 0.1 

        # --- FÍSICA ---
        if target_speed > self.speed:
            self.speed += self.acceleration
        elif target_speed < self.speed:
            self.speed -= self.acceleration
            
        if self.speed < 0: self.speed = 0

    def advance(self):
        if self.state == "ARRIVED": return

        if self.speed > 0 and self.path:
            target = self.path[0]
            current = np.array(self.pos)
            
            vec_to_target = np.array(target) - current
            dist_to_target = np.linalg.norm(vec_to_target)
            
            if dist_to_target < self.speed:
                new_pos = target
                self.path.pop(0)
                self.model.space.move_agent(self, tuple(new_pos))
                if not self.path:
                    self.state = "ARRIVED"
                    self.model.space.remove_agent(self)
            else:
                norm_dir = vec_to_target / dist_to_target
                new_pos = current + norm_dir * self.speed
                self.model.space.move_agent(self, tuple(new_pos))