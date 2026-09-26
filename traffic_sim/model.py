"""Human-only baseline for the discrete circular-road traffic model.

All vehicles read the same pre-step state, then move simultaneously. The
random-slowing rule is a model assumption, not a claim about actual drivers.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from random import Random
from statistics import fmean, pstdev
from typing import Mapping


@dataclass(frozen=True)
class SimulationConfig:
    road_length: int = 200
    num_vehicles: int = 40
    max_speed: int = 5
    human_slow_probability: float = 0.2
    av_share: float = 0.0
    seed: int = 1

    def __post_init__(self) -> None:
        if self.road_length < 2:
            raise ValueError("road_length must be at least 2")
        if not 1 <= self.num_vehicles <= self.road_length:
            raise ValueError("num_vehicles must be between 1 and road_length")
        if self.max_speed < 0:
            raise ValueError("max_speed must be non-negative")
        if not 0 <= self.human_slow_probability <= 1:
            raise ValueError("human_slow_probability must be between 0 and 1")
        if not 0 <= self.av_share <= 1:
            raise ValueError("av_share must be between 0 and 1")


@dataclass(frozen=True)
class BrakingDisturbance:
    """Temporarily cap one vehicle's speed during the measurement period."""

    vehicle_id: int = 0
    start_step: int = 100
    duration: int = 8
    speed_cap: int = 0

    def __post_init__(self) -> None:
        if self.vehicle_id < 0:
            raise ValueError("vehicle_id must be non-negative")
        if self.start_step < 1:
            raise ValueError("start_step must be at least 1")
        if self.duration < 1:
            raise ValueError("duration must be at least 1")
        if self.speed_cap < 0:
            raise ValueError("speed_cap must be non-negative")

    @property
    def end_step(self) -> int:
        """Last measurement step on which the speed cap is active."""

        return self.start_step + self.duration - 1

    def is_active(self, measurement_step: int) -> bool:
        return self.start_step <= measurement_step <= self.end_step


@dataclass(frozen=True)
class Vehicle:
    vehicle_id: int
    position: int
    speed: int
    vehicle_type: str = "human"


class TrafficModel:
    """Stateful model with reproducible random initial placement and slowing."""

    def __init__(self, config: SimulationConfig):
        self.config = config
        self.rng = Random(config.seed)
        
        # Sort positions ONCE to establish a fixed spatial ring order
        positions = sorted(self.rng.sample(range(config.road_length), config.num_vehicles))
        
        # Generate vehicle type distributions
        num_av = round(config.num_vehicles * config.av_share)
        vehicle_types = ["av"] * num_av + ["human"] * (config.num_vehicles - num_av)
        self.rng.shuffle(vehicle_types)
        
        # Instantiate vehicles in spatial sequence
        self.vehicles = [
            Vehicle(i, position, 0, vehicle_types[i]) 
            for i, position in enumerate(positions)
        ]
        self._check_state()

    def _check_state(self) -> None:
        if len(self.vehicles) != self.config.num_vehicles:
            raise AssertionError("vehicle count changed")
        positions = [vehicle.position for vehicle in self.vehicles]
        if len(set(positions)) != len(positions):
            raise AssertionError("two vehicles occupy the same cell")
        for vehicle in self.vehicles:
            if not 0 <= vehicle.position < self.config.road_length:
                raise AssertionError("position outside the road")
            if not 0 <= vehicle.speed <= self.config.max_speed:
                raise AssertionError("speed outside the permitted range")

    def step(
        self, speed_caps: Mapping[int, int] | None = None
    ) -> tuple[Vehicle, ...]:
        """Apply acceleration, safe braking, random slowing, then movement."""
        speed_caps = speed_caps or {}
        valid_ids = {vehicle.vehicle_id for vehicle in self.vehicles}
        if not set(speed_caps).issubset(valid_ids):
            raise ValueError("speed cap refers to an unknown vehicle")
        if any(cap < 0 or cap > self.config.max_speed for cap in speed_caps.values()):
            raise ValueError("speed caps must be between 0 and max_speed")

        # CRITICAL FIX: Do NOT sort by position here. 
        # Using the natural array index guarantees cars maintain spatial order.
        updated = []
        num_cars = len(self.vehicles)
        
        for index, vehicle in enumerate(self.vehicles):
            ahead = self.vehicles[(index + 1) % num_cars]
            gap = (ahead.position - vehicle.position - 1) % self.config.road_length
            
            # Base velocity calculation
            speed = min(vehicle.speed + 1, self.config.max_speed, gap)
            
            # Apply random slowing ONLY to human drivers
            if (
                vehicle.vehicle_type == "human"
                and speed > 0 
                and self.rng.random() < self.config.human_slow_probability
            ):
                speed -= 1

            if vehicle.vehicle_id in speed_caps:
                speed = min(speed, speed_caps[vehicle.vehicle_id])
                
            updated.append(
                Vehicle(
                    vehicle.vehicle_id,
                    (vehicle.position + speed) % self.config.road_length,
                    speed,
                    vehicle.vehicle_type
                )
            )
            
        self.vehicles = updated
        self._check_state()
        return tuple(self.vehicles)

    def av_share(self) -> float:
        return sum(v.vehicle_type == "av" for v in self.vehicles) / len(self.vehicles)
    

def run_simulation(
    config: SimulationConfig,
    *,
    steps: int = 800,
    warmup: int = 200,
    disturbance: BrakingDisturbance | None = None,
) -> dict:
    """Return per-step metrics and a summary after the warm-up period."""

    if steps < 1 or warmup < 0:
        raise ValueError("steps must be positive and warmup must be non-negative")
    if disturbance is not None:
        if disturbance.vehicle_id >= config.num_vehicles:
            raise ValueError("disturbance vehicle_id must identify an existing vehicle")
        if disturbance.speed_cap > config.max_speed:
            raise ValueError("disturbance speed_cap cannot exceed max_speed")
        if disturbance.end_step > steps:
            raise ValueError("disturbance must finish within the measurement period")
        
    model = TrafficModel(config)
    realised = model.av_share()  # Capture baseline allocation instantly
    
    for _ in range(warmup):
        model.step()

    rows = []
    all_speeds = []
    for measurement_step in range(1, steps + 1):
        disturbance_active = (
            disturbance is not None and disturbance.is_active(measurement_step)
        )
        speed_caps = (
            {disturbance.vehicle_id: disturbance.speed_cap}
            if disturbance_active and disturbance is not None
            else None
        )
        vehicles = model.step(speed_caps=speed_caps)
        speeds = [vehicle.speed for vehicle in vehicles]
        all_speeds.extend(speeds)
        disturbed_vehicle_speed = (
            next(
                vehicle.speed
                for vehicle in vehicles
                if vehicle.vehicle_id == disturbance.vehicle_id
            )
            if disturbance is not None
            else None
        )
        rows.append(
            {
                "step": measurement_step,
                "mean_speed": fmean(speeds),
                "stopped_fraction": speeds.count(0) / len(speeds),
                "speed_std": pstdev(speeds),
                "requested_av_share": config.av_share,
                "realised_av_share": realised,
                "disturbance_active": disturbance_active,
                "disturbed_vehicle_speed": disturbed_vehicle_speed,
            }
        )

    return {
        "config": asdict(config),
        "warmup": warmup,
        "steps": steps,
        "disturbance": asdict(disturbance) if disturbance is not None else None,
        "requested_av_share": config.av_share,
        "realised_av_share": realised,
        "summary": {
            "mean_speed": fmean(all_speeds),
            "stopped_fraction": all_speeds.count(0) / len(all_speeds),
            "speed_std": pstdev(all_speeds),
        },
        "per_step": rows,
    }
