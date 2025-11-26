from mesa import Agent
import numpy as np

class TrafficManagerAgent(Agent):
    """
    Agente 'Cerebro' que controla un grupo de semáforos lógicos.
    No tiene posición física en el mapa, solo gestiona el tiempo y la lógica de relevos.
    """
    def __init__(self, unique_id, model, green_time=20, yellow_time=4):
        super().__init__(model)
        self.unique_id = unique_id
        
        # Configuración de tiempos
        self.green_time = green_time
        self.yellow_time = yellow_time
        
        # Estado inicial
        self.state = "RED"
        self.time_remaining = 0
        
        # Referencia al siguiente manager en la cadena
        self.next_manager = None 

    def set_next(self, manager_agent):
        """Conecta este gestor con el siguiente en la cadena de relevos"""
        self.next_manager = manager_agent

    def activate(self):
        """Inicia el ciclo de verde para este gestor"""
        self.state = "GREEN"
        self.time_remaining = self.green_time

    def step(self):
        # Máquina de estados finitos basada en tiempo
        if self.state == "GREEN":
            self.time_remaining -= 1
            if self.time_remaining <= 0:
                self.state = "YELLOW"
                self.time_remaining = self.yellow_time
                
        elif self.state == "YELLOW":
            self.time_remaining -= 1
            if self.time_remaining <= 0:
                self.state = "RED"
                # Terminó mi turno, activo al siguiente en la cadena
                if self.next_manager:
                    self.next_manager.activate()
        
        # Si está en RED, espera pasivamente a ser activado por el anterior

class TrafficLightAgent(Agent):
    """
    Agente físico que representa una celda de semáforo en el grid.
    No piensa, solo refleja el estado de su TrafficManagerAgent asignado.
    """
    def __init__(self, unique_id, model, manager):
        super().__init__(model)
        self.unique_id = unique_id
        self.manager = manager # Referencia al agente gestor (cerebro)

    @property
    def state(self):
        # Refleja dinámicamente el estado del manager
        return self.manager.state
    
    @state.setter
    def state(self, value):
        # Ignoramos intentos externos de cambiar el estado directamente
        pass

    def step(self):
        # No hace nada, la lógica está en el Manager
        pass

    def receive_eta(self, vehicle_id, eta):
        # Método para compatibilidad con el vehículo. 
        # En este modelo de relevos fijos por tiempo, no usamos el ETA, 
        # pero el método debe existir para que el coche no falle al llamarlo.
        pass

class VehicleAgent(Agent):
    """
    Agente vehículo que se mueve por el grid siguiendo una ruta.
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
        # 1. Percepción: Buscar vecinos (coches o semáforos)
        neighbors = self.model.space.get_neighbors(self.pos, radius=2, include_center=False)
        obstacle_ahead = False
        traffic_light = None
        
        for agent in neighbors:
            if isinstance(agent, VehicleAgent):
                # Distancia de seguridad con otros coches
                if self.model.space.get_distance(self.pos, agent.pos) < 1.0:
                    obstacle_ahead = True
            elif isinstance(agent, TrafficLightAgent):
                traffic_light = agent

        # 2. Decisión: Calcular velocidad objetivo
        target_speed = self.max_speed
        
        # Reglas de semáforos
        if traffic_light:
            # Enviamos ETA (aunque el semáforo actual lo ignore, es buena práctica mantenerlo)
            dist = self.model.space.get_distance(self.pos, traffic_light.pos)
            if self.speed > 0:
                traffic_light.receive_eta(self.unique_id, dist / self.speed)
            
            # Reaccionar al color que dicta el Manager a través del agente
            if traffic_light.state == "RED": 
                target_speed = 0
            elif traffic_light.state == "YELLOW": 
                target_speed = self.max_speed * 0.5
        
        # Reglas de colisión
        if obstacle_ahead:
            target_speed = 0
            self.state = "BRAKING"
        
        # 3. Acción: Actualizar física (Aceleración/Frenado suave)
        if self.speed < target_speed: 
            self.speed += self.acceleration
        elif self.speed > target_speed: 
            self.speed -= self.acceleration
            
        if self.speed < 0: 
            self.speed = 0

    def advance(self):
        # Movimiento físico siguiendo la ruta (path)
        if self.speed > 0 and self.path:
            target = self.path[0]
            current = np.array(self.pos)
            direction = np.array(target) - current
            dist = np.linalg.norm(direction)
            
            # Si estamos muy cerca del nodo objetivo, "saltamos" a él y pasamos al siguiente
            if dist < self.speed:
                new_pos = target
                self.path.pop(0)
            else:
                # Movimiento normal por vector
                new_pos = current + (direction / dist) * self.speed
            
            self.model.space.move_agent(self, tuple(new_pos))