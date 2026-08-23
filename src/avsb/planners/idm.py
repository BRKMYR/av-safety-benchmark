"""IDM longitudinal + P-controller lateral + MOBIL-style leader adoption (spec 5.10)."""

from __future__ import annotations

import math

from avsb.engine.observation import Action, ActorObs, Observation
from avsb.schema.scenario import ScenarioDefinition


EGO_RADIUS_M = 4.5 / 2.0  # matches spec 5.0: radius = length/2 (vehicle)


def select_leader(obs: Observation) -> ActorObs | None:
    """MOBIL-style leader selection.

    A visible actor is a leader if it is ahead (relative x > 0 in ego body frame)
    AND EITHER (i) its lateral offset from the ego lane center is within
    ``lane_width * 0.75`` OR (ii) it is laterally converging on the ego lane band
    with |vy| > 0.3. Pedestrians in the ego corridor count with speed = vx.

    Returns the nearest such actor by longitudinal (body-frame) distance, or None.
    """
    ex = obs.ego.x
    ey = obs.ego.y
    lane_c = obs.ego_lane_center_y
    lane_w = obs.lane_width
    corridor = lane_w * 0.75

    # Ego body frame: rotate world (dx, dy) by -yaw.
    cy = math.cos(-obs.ego.yaw)
    sy = math.sin(-obs.ego.yaw)

    best: tuple[float, ActorObs] | None = None
    for a in obs.actors:
        dx = a.x - ex
        dy = a.y - ey
        bx = dx * cy - dy * sy  # body-frame forward
        # by = dx * sy + dy * cy  # body-frame lateral (unused)
        if bx <= 0.0:
            continue
        offset = abs(a.y - lane_c)
        in_corridor = offset < corridor
        converging = False
        if not in_corridor and abs(a.vy) > 0.3:
            future_offset = abs((a.y + a.vy * 1.0) - lane_c)
            if future_offset < corridor:
                converging = True
        if not (in_corridor or converging):
            continue
        if best is None or bx < best[0]:
            best = (bx, a)
    return None if best is None else best[1]


class IdmPlanner:
    """IDM longitudinal + P-controller lateral (both `idm` variants share this class)."""

    def __init__(
        self,
        *,
        name: str,
        T: float,
        s0: float,
        a: float,
        b: float,
        v0_factor: float,
    ) -> None:
        self.name = name
        self.T = float(T)
        self.s0 = float(s0)
        self.a = float(a)
        self.b = float(b)
        self.v0_factor = float(v0_factor)

    def reset(self, scenario: ScenarioDefinition) -> None:
        return None

    def _v0(self, obs: Observation) -> float:
        return min(obs.target_speed, obs.speed_limit) * self.v0_factor

    def step(self, obs: Observation) -> Action:
        v = max(0.0, obs.ego.speed)
        v0 = max(0.1, self._v0(obs))

        leader = select_leader(obs)
        if leader is None:
            # Free-flow: no leader term.
            accel = self.a * (1.0 - (v / v0) ** 4)
        else:
            # Bumper gap = center gap - R_combined.
            dx = leader.x - obs.ego.x
            dy = leader.y - obs.ego.y
            center_gap = math.hypot(dx, dy)
            R = EGO_RADIUS_M + leader.radius
            s = max(0.1, center_gap - R)
            # Ego world velocity from scalar body-frame speed + yaw.
            evx = v * math.cos(obs.ego.yaw)
            evy = v * math.sin(obs.ego.yaw)
            los = math.hypot(dx, dy)
            if los < 1e-6:
                delta_v = 0.0
            else:
                rel_x = evx - leader.vx
                rel_y = evy - leader.vy
                # Positive when ego is approaching the leader along the LoS.
                delta_v = (rel_x * dx + rel_y * dy) / los
            s_star = self.s0 + v * self.T + (v * delta_v) / (2.0 * math.sqrt(self.a * self.b))
            s_star = max(0.0, s_star)
            accel = self.a * (1.0 - (v / v0) ** 4 - (s_star / s) ** 2)

        # P-controller lateral. Reject NaN from tan(steer) at pi/2 by clamping later.
        y_err = obs.ego_lane_center_y - obs.ego.y
        steer = 0.15 * y_err - 1.2 * obs.ego.yaw
        # Clamp is done in the engine, but keep sane values.
        if steer > 0.5:
            steer = 0.5
        elif steer < -0.5:
            steer = -0.5

        return Action(accel=float(accel), steer=float(steer))
