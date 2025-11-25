from mesa import Agent
import numpy as np

class TrafficLightAgent(Agent):
    def __init__(self, unique_id, model, controller, group_id):
        super().__init__(model)
        self.unique_id = unique_id
        
        # Referencia al cerebro de la intersección
        self.controller = controller 
        # ID del grupo (ej: 0 para Norte/Sur, 1 para Este/Oeste)
        self.group_id = group_id 

    @property
    def state(self):
        # Le pregunta al controlador: "¿Cómo está mi grupo ahora?"
        return self.controller.get_state(self.group_id)
    
    # Para compatibilidad con la visualización, necesitamos que 'state' sea asignable
    # aunque en realidad no lo usaremos para cambiar lógica interna, sino para el dibujo
    @state.setter
    def state(self, value):
        pass # El estado es controlado externamente, ignoramos asignaciones directas

    def step(self):
        # El agente semáforo ya no piensa.
        # El modelo se encarga de avanzar el tiempo del controlador globalmente.
        pass 

    def advance(self):
        pass

    def receive_eta(self, vehicle_id, eta):
        # Enviamos la señal al controlador para que decida si acelera el cambio
        self.controller.register_car_arrival(self.group_id, eta)


class VehicleAgent(Agent):
    # ... (El código del Vehículo se mantiene IGUAL que antes)
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
        neighbors = self.model.space.get_neighbors(self.pos, radius=2, include_center=False)
        obstacle_ahead = False
        traffic_light = None
        
        for agent in neighbors:
            if isinstance(agent, VehicleAgent):
                if self.model.space.get_distance(self.pos, agent.pos) < 1.0:
                    obstacle_ahead = True
            elif isinstance(agent, TrafficLightAgent):
                traffic_light = agent

        target_speed = self.max_speed
        if traffic_light:
            dist = self.model.space.get_distance(self.pos, traffic_light.pos)
            
            # Avisamos al semáforo (que avisará al controlador)
            if self.speed > 0:
                traffic_light.receive_eta(self.unique_id, dist / self.speed)
            
            # Leemos el estado (que viene del controlador)
            if traffic_light.state == "RED": target_speed = 0
            elif traffic_light.state == "YELLOW": target_speed = self.max_speed * 0.5
        
        if obstacle_ahead:
            target_speed = 0
            self.state = "BRAKING"
        
        if self.speed < target_speed: self.speed += self.acceleration
        elif self.speed > target_speed: self.speed -= self.acceleration
        if self.speed < 0: self.speed = 0

    def advance(self):
        if self.speed > 0 and self.path:
            target = self.path[0]
            current = np.array(self.pos)
            direction = np.array(target) - current
            dist = np.linalg.norm(direction)
            
            if dist < self.speed:
                new_pos = target
                self.path.pop(0)
            else:
                new_pos = current + (direction / dist) * self.speed
            
            self.model.space.move_agent(self, tuple(new_pos))