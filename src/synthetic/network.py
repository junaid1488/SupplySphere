from dataclasses import dataclass

@dataclass(frozen=True)
class City:
    name: str
    latitude: float
    longitude: float

INDIA_NETWORK = (
    City("Delhi", 28.6139, 77.2090),
    City("Mumbai", 19.0760, 72.8777),
    City("Bengaluru", 12.9716, 77.5946),
    City("Hyderabad", 17.3850, 78.4867),
    City("Chennai", 13.0827, 80.2707),
    City("Kolkata", 22.5726, 88.3639),
    City("Lucknow", 26.8467, 80.9462),
    City("Jaipur", 26.9124, 75.7873),
    City("Pune", 18.5204, 73.8567),
    City("Ahmedabad", 23.0225, 72.5714),
    City("Patna", 25.5941, 85.1376),
    City("Guwahati", 26.1445, 91.7362),
)
