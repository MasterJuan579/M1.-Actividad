from mesa import Agent
import numpy as np

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
    Agente vehículo con Visión de Largo Alcance y Frenado Progresivo
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

    def step(self):
        if self.state == "ARRIVED":
            return

        # 1. Percepción: Aumentamos el radio a 2.5 para ver hasta 2 celdas adelante
        neighbors = self.model.space.get_neighbors(self.pos, radius=2.5, include_center=False)
        
        obstacle_ahead = False      # Para frenado suave (lejos)
        emergency_brake = False     # Para frenado seco (cerca)
        traffic_light = None
        
        next_step_pos = self.path[0] if self.path else None
        current_pos = np.array(self.pos)
        
        for agent in neighbors:
            # --- DETECCIÓN DE COCHES ---
            if isinstance(agent, VehicleAgent):
                if agent.state == "ARRIVED": continue

                other_pos = np.array(agent.pos)
                dist = np.linalg.norm(other_pos - current_pos)
                
                # Verificamos si el coche está REALMENTE enfrente (Dirección)
                is_in_front = False
                if next_step_pos is not None:
                    my_direction = np.array(next_step_pos) - current_pos
                    vector_to_other = other_pos - current_pos
                    if np.dot(my_direction, vector_to_other) > 0:
                        is_in_front = True

                if is_in_front:
                    # ETAPA 1: Coche muy cerca (< 0.9) -> Frenado de Emergencia
                    if dist < 0.9:
                        emergency_brake = True
                        obstacle_ahead = True # También cuenta como obstáculo
                    
                    # ETAPA 2: Coche a distancia media (< 1.9) -> Frenado Suave
                    elif dist < 1.9:
                        obstacle_ahead = True
            
            # --- DETECCIÓN DE SEMÁFOROS ---
            elif isinstance(agent, TrafficLightAgent):
                if next_step_pos is not None:
                    dist_to_light = self.model.space.get_distance(agent.pos, next_step_pos)
                    if dist_to_light < 0.1:
                        traffic_light = agent

        # --- LÓGICA DE MOVIMIENTO ---
        target_speed = self.max_speed
        
        # 1. Semáforos
        if traffic_light:
            if traffic_light.state == "RED":
                target_speed = 0
                self.speed = 0  # Semáforo rojo siempre es parada total
            elif traffic_light.state == "YELLOW":
                target_speed = self.max_speed * 0.5
        
        # 2. Obstáculos (Coches)
        if obstacle_ahead:
            target_speed = 0
            self.state = "BRAKING"
            # Si hay emergencia (muy cerca), paramos en seco.
            # Si solo es obstáculo lejano, dejamos que la física frene suavemente.
            if emergency_brake:
                self.speed = 0 
        
        # 3. Aceleración / Desaceleración Física
        if target_speed > self.speed:
            self.speed += self.acceleration
        elif target_speed < self.speed:
            self.speed -= self.acceleration
            
        if self.speed < 0: 
            self.speed = 0

    def advance(self):
        if self.state == "ARRIVED":
            return

        if self.speed > 0 and self.path:
            target = self.path[0]
            current = np.array(self.pos)
            direction = np.array(target) - current
            dist = np.linalg.norm(direction)
            
            if dist < self.speed:
                new_pos = target
                self.path.pop(0)
                self.model.space.move_agent(self, tuple(new_pos))

                if not self.path:
                    self.state = "ARRIVED"
                    self.model.space.remove_agent(self)
            else:
                new_pos = current + (direction / dist) * self.speed
                self.model.space.move_agent(self, tuple(new_pos))