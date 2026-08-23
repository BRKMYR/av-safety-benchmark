"""Fixed-timestep kinematic simulator (spec section 5.3, 4)."""

from avsb.engine.observation import (
    Action,
    ActorObs,
    EgoObs,
    Observation,
    build_observation,
)
from avsb.engine.occlusion import segment_intersects_rect, visible_actors
from avsb.engine.scripted import ScriptedActor
from avsb.engine.simulator import (
    A_MAX,
    A_MIN,
    EGO_WHEELBASE,
    STEER_MAX,
    run_scenario,
    run_suite,
)

__all__ = [
    "A_MAX",
    "A_MIN",
    "Action",
    "ActorObs",
    "EGO_WHEELBASE",
    "EgoObs",
    "Observation",
    "STEER_MAX",
    "ScriptedActor",
    "build_observation",
    "run_scenario",
    "run_suite",
    "segment_intersects_rect",
    "visible_actors",
]
