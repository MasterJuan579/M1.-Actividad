from model import TrafficModel
from agents import VehicleAgent, TrafficLightAgent

def run_simulation(steps=100):
    print("--- Initializing Traffic Jam Model (Mesa 3.0 Compatible) ---")
    traffic_model = TrafficModel(num_vehicles=5)
    
    # Pick a light to monitor
    monitored_light = None
    for agent in traffic_model.agents_list:
        if isinstance(agent, TrafficLightAgent) and agent.state == "RED":
            monitored_light = agent
            break
            
    if monitored_light:
        print(f"Monitoring Traffic Light: {monitored_light.unique_id} (Start: {monitored_light.state})")

    # Simulation Loop
    for i in range(steps):
        traffic_model.step()
        
        if i % 10 == 0:
            print(f"\n--- Step {i} ---")
            
            # 1. Global Stats
            # Note: We access vars directly from datacollector dataframe or just print manual check
            # Stopped cars logic:
            stopped = sum(1 for a in traffic_model.agents_list if isinstance(a, VehicleAgent) and a.speed < 0.01)
            print(f"Global Stats: Stopped Cars: {stopped}")

            # 2. Track Car_0
            car_0 = next((a for a in traffic_model.agents_list if a.unique_id == "Car_0"), None)
            if car_0:
                print(f"Car_0 Status: Pos {car_0.pos} | Speed {car_0.speed:.2f}")
            
            # 3. Track Light
            if monitored_light:
                 print(f"Light {monitored_light.unique_id} State: {monitored_light.state} | Timer: {monitored_light.time_remaining}")

    print("\n--- Simulation Finished ---")

if __name__ == "__main__":
    run_simulation()