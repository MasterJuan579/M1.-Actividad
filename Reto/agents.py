from mesa import Agent
import numpy as np
import networkx as nx

PARKING = 3
INTERSECTION_ENTRY = 4

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
    Agente vehículo con Cambio de Carril Inteligente y Stop con Memoria
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
        
        # --- SISTEMA DE PACIENCIA ---
        self.max_patience = 5
        self.patience = self.max_patience

        # --- NUEVO: MEMORIA DE STOP ---
        # Guarda la coordenada (x, y) donde ya hicimos el alto total para no repetirlo
        self.memory_stop = None 

    def try_change_lane(self):
        """
        Intenta buscar un nodo adyacente (carril lateral) que esté libre
        """
        current_node = self.get_current_grid_pos()
        if current_node not in self.model.graph: return

        neighbors = list(self.model.graph.neighbors(current_node))
        original_next_step = self.path[0] if self.path else None

        for neighbor in neighbors:
            if neighbor == original_next_step: continue
            
            # Verificar espacio físico
            cell_contents = self.model.space.get_neighbors(neighbor, radius=0.2, include_center=True)
            is_free = not any(isinstance(obj, VehicleAgent) for obj in cell_contents)
            
            if is_free:
                try:
                    new_path = nx.shortest_path(self.model.graph, neighbor, self.destination, weight='weight')
                    self.path = [(x + 0.5, y + 0.5) for x, y in new_path]
                    self.patience = self.max_patience
                    self.speed = 0.1 
                    return
                except nx.NetworkXNoPath: continue

    def get_current_grid_pos(self):
        return (int(round(self.pos[0]-0.5)), int(round(self.pos[1]-0.5)))
    
    def is_in_roundabout(self):
        """Verifica si el vehículo está dentro de la rotonda"""
        grid_pos = self.get_current_grid_pos()
        return grid_pos in self.model.roundabout_ring

    def count_vehicles_in_roundabout(self):
        """Cuenta vehículos actualmente en la rotonda"""
        count = 0
        for agent in self.model.agents_list:
            if isinstance(agent, VehicleAgent) and agent is not self:
                if agent.state != "ARRIVED" and agent.is_in_roundabout():
                    count += 1
        return count

    def should_yield_at_roundabout(self):
        """
        Determina si debe ceder el paso antes de entrar a la rotonda.
        Retorna True si debe esperar.
        """
        grid_pos = self.get_current_grid_pos()
        
        # ¿Estoy en un punto de entrada?
        if grid_pos not in self.model.roundabout_entries:
            return False
        
        # Regla 1: Capacidad máxima alcanzada
        if self.count_vehicles_in_roundabout() >= self.model.roundabout_capacity:
            return True
        
        # Regla 2: Ceder a vehículos circulando dentro
        my_pos = np.array(self.pos)
        
        for agent in self.model.agents_list:
            if agent is self or not isinstance(agent, VehicleAgent):
                continue
            if agent.state == "ARRIVED":
                continue
            
            # Si el otro está en la rotonda y moviéndose
            if agent.is_in_roundabout() and agent.speed > 0.05:
                other_pos = np.array(agent.pos)
                distance = np.linalg.norm(other_pos - my_pos)
                
                # Si está cerca de mi entrada, cedo el paso
                if distance < 2.5:
                    return True
        
        return False

    def step(self):
        if self.state == "ARRIVED": return

        # --- 1. PACIENCIA ---
        if self.speed < 0.1: self.patience -= 1
        else: self.patience = self.max_patience
        if self.patience <= 0: self.try_change_lane()

        # --- 2. VECTORES PROPIOS ---
        current_pos = np.array(self.pos)
        next_pos = self.path[0] if self.path else None
        if next_pos is None: return

        my_dx = next_pos[0] - current_pos[0]
        my_dy = next_pos[1] - current_pos[1]
        norm = np.linalg.norm([my_dx, my_dy])
        # Vector unitario de mi dirección (hacia dónde miro)
        dir_vector = np.array([my_dx, my_dy]) / (norm if norm > 0 else 1)
        my_is_horiz = abs(my_dx) > abs(my_dy)

        # --- 3. CONTEXTO ---
        cx, cy = int(self.pos[0]), int(self.pos[1])
        
        is_in_parking = False
        if 0 <= cx < len(self.model.city_layout) and 0 <= cy < len(self.model.city_layout[0]):
            if self.model.city_layout[cx][cy] == PARKING: is_in_parking = True
            
        is_at_intersection_entry = False
        if hasattr(self.model, 'stop_lines') and (cx, cy) in self.model.stop_lines:
            is_at_intersection_entry = True
        else:
            self.memory_stop = None

        # --- 4. STOP (FASE 1) ---
        if is_at_intersection_entry:
            if self.memory_stop != (cx, cy):
                if self.speed > 0:
                    self.speed = 0
                    self.memory_stop = (cx, cy)
                    return
        # --- 4.5 YIELD EN ROTONDA ---
        if self.should_yield_at_roundabout():
            self.speed = 0
            return

        # --- 5. ESCANEO DE VECINOS ---
        neighbors = self.model.space.get_neighbors(self.pos, radius=4.0, include_center=False)
        
        obstacle_ahead = False
        emergency_brake = False
        traffic_light = None
        blocking_car_distance = 999.9

        for agent in neighbors:
            if isinstance(agent, VehicleAgent):
                if agent.state == "ARRIVED": continue
                other_pos = np.array(agent.pos)
                vec_to_other = other_pos - current_pos
                dist = np.linalg.norm(vec_to_other)

                # CÁLCULO DE ÁNGULO (¿Está enfrente de mí?) 
                # > 0: Enfrente (90° a -90°)
                # > 0.5: En mi cono de visión frontal (60°)
                # > 0.7: Justo enfrente (45°)
                angle_match = np.dot(dir_vector, vec_to_other / (dist + 0.0001))

                # >>> REGLA A: ANTI-CHOQUE (BURBUJA DIRECCIONAL) <<<
                # 1. Si está LITERALMENTE encima (< 0.5), paramos siempre (choque físico)
                if dist < 0.2:
                    self.speed = 0; obstacle_ahead = True; emergency_brake = True; continue

                # 2. Si está CERCA (< 0.8) y ENFRENTE (> 0.5), paramos.
                # CORRECCIÓN: Si está al lado (angle_match < 0.5), lo ignoramos.
                if dist < 0.5 and angle_match > 0.5:
                    self.speed = 0
                    obstacle_ahead = True
                    emergency_brake = True
                    continue 

                # >>> REGLA B: CRUCE DE STOP <<<
                if is_at_intersection_entry:
                    other_next = agent.path[0] if agent.path else None
                    if other_next:
                        o_dx = other_next[0] - other_pos[0]
                        o_dy = other_next[1] - other_pos[1]
                        other_is_horiz = abs(o_dx) > abs(o_dy)
                        if my_is_horiz != other_is_horiz:
                            dist_to_conflict = np.linalg.norm(other_pos - np.array(next_pos))
                            if dist_to_conflict < 1.5:
                                obstacle_ahead = True; emergency_brake = True

                # >>> REGLA C: SALIDA DE PARKING <<<
                elif is_in_parking:
                    ox, oy = int(agent.pos[0]), int(agent.pos[1])
                    is_neighbor_on_road = False
                    if 0 <= ox < len(self.model.city_layout) and 0 <= oy < len(self.model.city_layout[0]):
                        if self.model.city_layout[ox][oy] != PARKING:
                            is_neighbor_on_road = True
                    if is_neighbor_on_road:
                        dist_to_merge = np.linalg.norm(other_pos - np.array(next_pos))
                        if dist_to_merge < 3.0:
                            obstacle_ahead = True; emergency_brake = True

                # >>> REGLA D: SEGUIMIENTO (CAR FOLLOWING) <<<
                else:
                    if self.is_in_roundabout():
                        other_grid = (int(round(agent.pos[0]-0.5)), int(round(agent.pos[1]-0.5)))
                        if other_grid in self.model.roundabout_entries:
                            continue  # Ignoro a este coche, yo tengo prioridad
                    
                    # Usamos el angle_match que calculamos arriba
                    if angle_match > 0.7: 
                        braking_dist = (self.speed ** 2) / (2 * self.acceleration)
                        safety_margin = 1.5 
                        if dist < (braking_dist + safety_margin):
                            obstacle_ahead = True
                            if dist < safety_margin: emergency_brake = True
                            else: self.state = "BRAKING"

            elif isinstance(agent, TrafficLightAgent):
                dist_light = self.model.space.get_distance(agent.pos, next_pos)
                if dist_light < 0.1: traffic_light = agent

        # --- 6. ACTUADORES ---
        target_speed = self.max_speed
        light_is_red = False
        
        if traffic_light:
            if traffic_light.state == "RED":
                target_speed = 0; light_is_red = True; self.speed = 0
            elif traffic_light.state == "YELLOW": target_speed = self.max_speed * 0.5

        if obstacle_ahead:
            target_speed = 0; self.state = "BRAKING"
            if emergency_brake: self.speed = 0
        
        # --- 7. KICKSTART ---
        if self.speed < 0.01 and not light_is_red and not obstacle_ahead:
            if is_at_intersection_entry:
                target_speed = self.max_speed; self.speed = 0.1
            elif blocking_car_distance > 1.5: 
                target_speed = self.max_speed; self.speed = 0.1 

        # --- 8. FÍSICA ---
        if target_speed > self.speed: self.speed += self.acceleration
        elif target_speed < self.speed: self.speed -= self.acceleration
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