"""Observation / Action dataclasses and observation builder (spec 5.3)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from avsb.engine.occlusion import visible_actors


PED_RADIUS_M = 0.3


@dataclass(frozen=True)
class ActorObs:
    actor_id: str
    kind: str  # "vehicle" | "pedestrian"
    x: float
    y: float
    yaw: float
    vx: float
    vy: float
    length: float
    width: float
    radius: float


@dataclass(frozen=True)
class EgoObs:
    x: float
    y: float
    yaw: float
    speed: float
    accel_prev: float


@dataclass(frozen=True)
class Observation:
    t: float
    dt: float
    ego: EgoObs
    actors: tuple[ActorObs, ...]
    lane_width: float
    n_lanes: int
    ego_lane_center_y: float
    speed_limit: float
    target_speed: float
    visibility_m: float
    friction: float


@dataclass(frozen=True)
class Action:
    accel: float
    steer: float


def actor_radius(kind: str, length_m: float) -> float:
    """Disc radius per spec 5.0: vehicles length/2, pedestrians 0.3."""
    if kind == "pedestrian":
        return PED_RADIUS_M
    return length_m / 2.0


def build_observation(
    *,
    t: float,
    dt: float,
    ego_state: tuple[float, float, float, float, float],  # x, y, yaw, speed, accel_prev
    actor_records: Sequence[
        tuple[str, str, float, float, float, float, float, float, float]
    ],  # actor_id, kind, x, y, yaw, vx, vy, length, width
    static_rects: Sequence[tuple[float, float, float, float]],  # cx, cy, half_l, half_w
    lane_width: float,
    n_lanes: int,
    ego_lane_center_y: float,
    speed_limit: float,
    target_speed: float,
    visibility_m: float,
    friction: float,
) -> Observation:
    """Assemble an Observation, applying the visibility filter to non-static actors."""
    ex, ey, eyaw, espd, ea_prev = ego_state
    ego = EgoObs(x=ex, y=ey, yaw=eyaw, speed=espd, accel_prev=ea_prev)

    packed = [
        (a[0], a[1], a[2], a[3], a[7] / 2.0, a[8] / 2.0)
        for a in actor_records
    ]
    idxs = visible_actors((ex, ey), packed, static_rects, visibility_m)
    obs_actors: list[ActorObs] = []
    for i in idxs:
        aid, kind, x, y, yaw, vx, vy, length, width = actor_records[i]
        obs_actors.append(
            ActorObs(
                actor_id=aid,
                kind=kind,
                x=x,
                y=y,
                yaw=yaw,
                vx=vx,
                vy=vy,
                length=length,
                width=width,
                radius=actor_radius(kind, length),
            )
        )
    return Observation(
        t=t,
        dt=dt,
        ego=ego,
        actors=tuple(obs_actors),
        lane_width=lane_width,
        n_lanes=n_lanes,
        ego_lane_center_y=ego_lane_center_y,
        speed_limit=speed_limit,
        target_speed=target_speed,
        visibility_m=visibility_m,
        friction=friction,
    )
