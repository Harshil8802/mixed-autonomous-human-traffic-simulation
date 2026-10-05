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
    av_policy: str = "reactive"
    lanes: int = 1  # 1 = Single Lane (Default), 2 = Parallel Highways

    def __post_init__(self) -> None:
        if self.road_length < 2:
            raise ValueError("road_length must be at least 2")
        if not 1 <= self.num_vehicles <= (self.road_length * self.lanes):
            raise ValueError("num_vehicles must fit within total road cells")
        if self.max_speed < 0:
            raise ValueError("max_speed must be non-negative")
        if not 0 <= self.human_slow_probability <= 1:
            raise ValueError("human_slow_probability must be between 0 and 1")
        if not 0 <= self.av_share <= 1:
            raise ValueError("av_share must be between 0 and 1")
        if self.av_policy not in ("reactive", "anticipatory"):
            raise ValueError("av_policy must be 'reactive' or 'anticipatory'")
        if self.lanes not in (1, 2):
            raise ValueError("lanes must be 1 or 2")


@dataclass(frozen=True)
class BrakingDisturbance:
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
        return self.start_step + self.duration - 1

    def is_active(self, measurement_step: int) -> bool:
        return self.start_step <= measurement_step <= self.end_step


@dataclass(frozen=True)
class Vehicle:
    vehicle_id: int
    position: int
    speed: int
    vehicle_type: str = "human"
    lane: int = 0  # 0 = Slow Lane, 1 = Fast Lane


class TrafficModel:
    def __init__(self, config: SimulationConfig):
        self.config = config
        self.rng = Random(config.seed)
        
        # Build coordinates cleanly across 1 or 2 lanes
        all_cells = [(l, p) for l in range(config.lanes) for p in range(config.road_length)]
        
        # FIX A: Clean up the sorting key lambda from (x, x) to sort by lane/position values directly
        chosen_cells = sorted(self.rng.sample(all_cells, config.num_vehicles), key=lambda c: (c[0], c[1]))
        
        num_av = round(config.num_vehicles * config.av_share)
        vehicle_types = ["av"] * num_av + ["human"] * (config.num_vehicles - num_av)
        self.rng.shuffle(vehicle_types)
        
        # FIX B: Explicitly unpack cell[1] (position) and cell[0] (lane) instead of feeding the tuple raw
        self.vehicles = [
            Vehicle(i, cell[1], 0, vehicle_types[i], cell[0]) 
            for i, cell in enumerate(chosen_cells)
        ]
        self._check_state()


    def _check_state(self) -> None:
        if len(self.vehicles) != self.config.num_vehicles:
            raise AssertionError("vehicle count changed")
        coordinates = [(v.lane, v.position) for v in self.vehicles]
        if len(set(coordinates)) != len(coordinates):
            raise AssertionError("two vehicles occupy the same cell")
        for vehicle in self.vehicles:
            if not 0 <= vehicle.position < self.config.road_length:
                raise AssertionError("position outside the road")
            if not 0 <= vehicle.speed <= self.config.max_speed:
                raise AssertionError("speed outside permitted range")
            if not 0 <= vehicle.lane < self.config.lanes:
                raise AssertionError("lane index outside permitted range")

    def step(self, speed_caps: Mapping[int, int] | None = None) -> tuple[Vehicle, ...]:
        speed_caps = speed_caps or {}
        valid_ids = {vehicle.vehicle_id for vehicle in self.vehicles}
        if not set(speed_caps).issubset(valid_ids):
            raise ValueError("speed cap refers to an unknown vehicle")
        if any(cap < 0 or cap > self.config.max_speed for cap in speed_caps.values()):
            raise ValueError("speed caps must be between 0 and max_speed")
        L = self.config.road_length
        
        def get_vehicle_at(l: int, p: int) -> Vehicle | None:
            for v in self.vehicles:
                if v.lane == l and v.position == p:
                    return v
            return None

        # --- STEP A: LANE CHANGES (Symmetric passing options) ---
        post_lane_change = []
        if self.config.lanes == 2:
            for v in self.vehicles:
                target_lane = 1 - v.lane
                pos = v.position
                
                # Check 1: Block switch if target cell is occupied
                if get_vehicle_at(target_lane, pos) is not None:
                    post_lane_change.append(v)
                    continue
                    
                # Check 2: Evaluate forward clearance gaps
                curr_gap = 0
                for d in range(1, self.config.max_speed + 1):
                    if get_vehicle_at(v.lane, (pos + d) % L) is not None:
                        break
                    curr_gap += 1
                    
                target_gap = 0
                for d in range(1, self.config.max_speed + 1):
                    if get_vehicle_at(target_lane, (pos + d) % L) is not None:
                        break
                    target_gap += 1
                
                # Check 3: Look-back safety margin to prevent collisions
                look_back_safe = True
                for d in range(1, self.config.max_speed + 1):
                    back_car = get_vehicle_at(target_lane, (pos - d) % L)
                    if back_car is not None and back_car.speed >= d:
                        look_back_safe = False
                        break
                
                # Switch if target lane is clearer and back spacing is safe
                if target_gap > curr_gap and look_back_safe:
                    post_lane_change.append(Vehicle(v.vehicle_id, pos, v.speed, v.vehicle_type, target_lane))
                else:
                    post_lane_change.append(v)
            self.vehicles = post_lane_change
        
        # --- STEP B: FORWARD UPDATE MOVEMENTS ---
        updated = []
        for vehicle in self.vehicles:
            same_lane = sorted([v for v in self.vehicles if v.lane == vehicle.lane], key=lambda x: x.position)
            
            if len(same_lane) == 1:
                gap = L - 1
                ahead_speed = self.config.max_speed
            else:
                l_idx = same_lane.index(vehicle)
                ahead = same_lane[(l_idx + 1) % len(same_lane)]
                gap = (ahead.position - vehicle.position - 1) % L
                ahead_speed = ahead.speed
            
            if vehicle.vehicle_type == "human":
                speed = min(vehicle.speed + 1, self.config.max_speed, gap)
                if speed > 0 and self.rng.random() < self.config.human_slow_probability:
                    speed -= 1
            else:
                if self.config.av_policy == "reactive":
                    speed = min(vehicle.speed + 1, self.config.max_speed, gap)
                else:
                    safety_buffer = 2
                    if gap <= safety_buffer:
                        speed = min(vehicle.speed + 1, self.config.max_speed, gap, ahead_speed)
                    else:
                        speed = min(vehicle.speed + 1, self.config.max_speed, gap, ahead_speed + (gap - safety_buffer))

            if vehicle.vehicle_id in speed_caps:
                speed = min(speed, speed_caps[vehicle.vehicle_id])
                
            updated.append(Vehicle(vehicle.vehicle_id, (vehicle.position + speed) % L, speed, vehicle.vehicle_type, vehicle.lane))
            
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
    record_trajectories: bool = False,
) -> dict:
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
    realised = model.av_share()
    
    for _ in range(warmup):
        model.step()

    rows = []
    trajectories = []
    all_speeds = []
    for measurement_step in range(1, steps + 1):
        disturbance_active = (disturbance is not None and disturbance.is_active(measurement_step))
        speed_caps = ({disturbance.vehicle_id: disturbance.speed_cap} if disturbance_active and disturbance is not None else None)
        
        vehicles = model.step(speed_caps=speed_caps)
        speeds = [vehicle.speed for vehicle in vehicles]
        all_speeds.extend(speeds)
        disturbed_vehicle_speed = (
            next(vehicle.speed for vehicle in vehicles if vehicle.vehicle_id == disturbance.vehicle_id)
            if disturbance is not None else None
        )
        rows.append(
            {
                "step": measurement_step,
                "mean_speed": fmean(speeds),
                "stopped_fraction": speeds.count(0) / len(speeds),
                "speed_std": pstdev(speeds),
                "requested_av_share": config.av_share,
                "realised_av_share": realised,
                "av_policy": config.av_policy,
                "disturbance_active": disturbance_active,
                "disturbed_vehicle_speed": disturbed_vehicle_speed,
            }
        )
        if record_trajectories:
            trajectories.extend(
                {
                    "step": measurement_step,
                    "vehicle_id": vehicle.vehicle_id,
                    "position": vehicle.position,
                    "lane": vehicle.lane,
                    "speed": vehicle.speed,
                    "vehicle_type": vehicle.vehicle_type,
                    "disturbance_active": disturbance_active,
                }
                for vehicle in vehicles
            )

    return {
        "config": asdict(config),
        "warmup": warmup,
        "steps": steps,
        "realised_av_share": realised,
        "summary": {
            "mean_speed": fmean(all_speeds) if all_speeds else 0.0,
            "stopped_fraction": all_speeds.count(0) / len(all_speeds) if all_speeds else 0.0,
            "speed_std": pstdev(all_speeds) if all_speeds else 0.0,
        },
        "per_step": rows,
        "trajectories": trajectories,
    }
