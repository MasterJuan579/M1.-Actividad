from mesa import Agent
import numpy as np

class TrafficLightAgent(Agent):
    def __init__(self, unique_id, model, direction):
        # MESA 3.0 FIX: Only pass 'model' to the parent constructor
        super().__init__(model) 
        # Set unique_id explicitly
        self.unique_id = unique_id
        
        self.direction = direction
        self.state = "YELLOW"
        self.time_remaining = 0

    def step(self):
        # (Same logic: Manage timers)
        if self.state == "GREEN":
            self.time_remaining -= 1
            if self.time_remaining <= 0:
                self.state = "YELLOW"
                self.time_remaining = 3
        elif self.state == "YELLOW":
            if self.time_remaining > 0:
                self.time_remaining -= 1
                if self.time_remaining <= 0:
                    self.state = "RED"
                    self.time_remaining = 30
        elif self.state == "RED":
            self.time_remaining -= 1
            if self.time_remaining <= 0:
                self.state = "YELLOW"
                self.time_remaining = 0
    
    def advance(self):
        pass

    def receive_eta(self, vehicle_id, eta):
        if self.state == "YELLOW" and self.time_remaining == 0:
            if eta < 10:
                print(f"Light {self.unique_id}: Green triggered by Vehicle {vehicle_id}")
                self.state = "GREEN"
                self.time_remaining = 30

class VehicleAgent(Agent):
    def __init__(self, unique_id, model, start_node, destination_node):
        # MESA 3.0 FIX: Only pass 'model' to the parent constructor
        super().__init__(model)
        # Set unique_id explicitly
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
            if self.speed > 0:
                traffic_light.receive_eta(self.unique_id, dist / self.speed)
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