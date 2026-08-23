"""Scripted actor: phase-script execution with latched triggers (spec 5.1)."""

from __future__ import annotations

import math

from avsb.schema.scenario import ActorSpec, Phase


class ScriptedActor:
    """Executes an ActorSpec: latched-trigger phase selection + kinematic update.

    Phase semantics (normative, spec 5.1):
      - Phases are checked in list order each step.
      - Once a trigger fires, it stays fired for the rest of the run.
      - The *last-listed* phase whose trigger has fired is the active one.
      - Static actors have no phases and never move.
    """

    def __init__(self, spec: ActorSpec) -> None:
        self.spec = spec
        self.actor_id = spec.actor_id
        self.kind = spec.kind
        self.length = spec.length_m
        self.width = spec.width_m
        self.mass = spec.mass_kg
        # Mutable state.
        self.x = float(spec.initial.x_m)
        self.y = float(spec.initial.y_m)
        self.yaw = float(spec.initial.yaw_rad)
        self.speed = float(spec.initial.speed_mps)
        self.vx = self.speed * math.cos(self.yaw)
        self.vy = self.speed * math.sin(self.yaw)
        self._fired: list[bool] = [False] * len(spec.phases)

    # ---- Trigger check ----
    def _trigger_ready(self, phase: Phase, t: float, ego_x: float) -> bool:
        trig = phase.trigger
        if trig.type == "time":
            return t + 1e-12 >= float(trig.at_time_s)
        if trig.type == "ego_gap":
            # (self.x - ego.x) <= gap_m
            return (self.x - ego_x) <= float(trig.gap_m) + 1e-12
        if trig.type == "ego_x":
            return ego_x + 1e-12 >= float(trig.ego_x_m)
        return False

    def _active_phase(self) -> Phase | None:
        """Return the last-listed fired phase, or None."""
        for i in range(len(self._fired) - 1, -1, -1):
            if self._fired[i]:
                return self.spec.phases[i]
        return None

    def step(self, dt: float, t: float, ego_x: float) -> None:
        """Advance this actor by one dt. Static actors are frozen."""
        if self.kind == "static" or not self.spec.phases:
            self.vx = 0.0
            self.vy = 0.0
            return

        # Latch triggers (in list order) for phases that just fired.
        for i, phase in enumerate(self.spec.phases):
            if not self._fired[i] and self._trigger_ready(phase, t, ego_x):
                self._fired[i] = True

        active = self._active_phase()
        if active is None:
            # No phase active yet: freeze speeds; keep pose.
            self.vx = 0.0
            self.vy = 0.0
            return

        # Longitudinal integration.
        target = active.target_speed_mps
        prev_speed = self.speed
        new_speed = prev_speed + active.accel_mps2 * dt
        if target is not None:
            if active.accel_mps2 > 0.0:
                new_speed = min(new_speed, target)
            elif active.accel_mps2 < 0.0:
                new_speed = max(new_speed, target)
            # accel == 0 with target set: no-op (speed keeps its previous value).
        new_speed = max(0.0, new_speed)
        self.speed = new_speed

        # Position update. For pedestrians, heading is +pi/2 while crossing.
        prev_x, prev_y = self.x, self.y
        if self.kind == "pedestrian":
            # Pedestrians in this benchmark are pure lateral crossers: no
            # longitudinal motion, only movement toward target_y_m.
            # self.x is intentionally unchanged.
            if active.target_y_m is not None and active.lateral_speed_mps > 0.0:
                dy_wanted = active.target_y_m - self.y
                step_y = math.copysign(
                    min(abs(dy_wanted), active.lateral_speed_mps * dt),
                    dy_wanted or 1.0,
                )
                self.y = self.y + step_y
                # Keep yaw at +/- pi/2 while crossing.
                self.yaw = math.copysign(math.pi / 2.0, step_y or 1.0)
        else:
            # Vehicles: advance along heading, then bleed lateral toward target.
            self.x = prev_x + new_speed * math.cos(self.yaw) * dt
            self.y = prev_y + new_speed * math.sin(self.yaw) * dt
            if active.target_y_m is not None and active.lateral_speed_mps > 0.0:
                dy_wanted = active.target_y_m - self.y
                step_y = math.copysign(
                    min(abs(dy_wanted), active.lateral_speed_mps * dt),
                    dy_wanted or 1.0,
                )
                self.y = self.y + step_y

            # Log-time heading: atan2(dy, dx) of actual displacement.
            dxs = self.x - prev_x
            dys = self.y - prev_y
            if abs(dxs) > 1e-9 or abs(dys) > 1e-9:
                self.yaw = math.atan2(dys, dxs)

        # World-frame velocity components (for the trajectory log).
        self.vx = (self.x - prev_x) / dt if dt > 0.0 else 0.0
        self.vy = (self.y - prev_y) / dt if dt > 0.0 else 0.0
