"""
neuros.ai.rl.engine
====================
Reinforcement Learning Engine — Phase 3.

Provides a training pipeline and deployment runtime for RL policies
on NEUROS robots. Designed for sim-to-real transfer:
  1. Train in SimulatorHAL (fast, no hardware risk)
  2. Validate latency/safety in Phase 2 RT Monitor
  3. Deploy to real robot via policy hot-swap

Supported algorithms (Phase 3)
--------------------------------
  PPO   : Proximal Policy Optimisation  (continuous + discrete actions)
  SAC   : Soft Actor-Critic             (continuous actions, off-policy)
  DQN   : Deep Q-Network                (discrete actions)
  STUB  : Random policy (always available, no ML library needed)

Architecture
------------
  RLEnvironment  — wraps a NEUROS Robot as an RL environment (Gym-compatible)
  RLPolicy       — holds a trained policy, runs inference at control frequency
  RLEngine       — orchestrates training loop, checkpointing, deployment

Observation space
-----------------
  Auto-built from subscribed Neural Bus topics:
    /robot/sensor/imu/full     → [ax, ay, az, gx, gy, gz]
    /robot/nav/odom/pose       → [x, y, theta, vx, omega]
    /robot/sensor/lidar/sectors→ [8 sector distances]
    /robot/sensor/battery      → [voltage, soc]

Action space (differential drive default)
------------------------------------------
  Continuous 2D: [linear_speed, angular_speed]
  Mapped to:     /robot/cmd/velocity

Install
-------
  pip install stable-baselines3 gymnasium
  (optional: pip install torch)
"""

from __future__ import annotations

import json
import logging
import os
import time
import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from neuros.api.robot import Robot

logger = logging.getLogger("neuros.ai.rl")


# ── Policy ────────────────────────────────────────────────────────────────
@dataclass
class RLPolicy:
    """A trained RL policy ready for deployment."""
    name:         str
    algorithm:    str                     # "ppo","sac","dqn","stub"
    obs_dim:      int                     = 16
    act_dim:      int                     = 2
    model_path:   Optional[str]           = None
    _model:       Any                     = field(default=None, repr=False)
    infer_count:  int                     = 0
    avg_ms:       float                   = 0.0

    def predict(self, obs: List[float]) -> Tuple[List[float], dict]:
        """
        Run policy inference.

        Returns
        -------
        action : list of floats (e.g. [linear, angular])
        info   : dict with policy metadata
        """
        t0 = time.monotonic()

        if self._model is not None and self.algorithm != "stub":
            try:
                import numpy as np
                action, _state = self._model.predict(
                    np.array(obs, dtype="float32"), deterministic=True
                )
                act = action.tolist() if hasattr(action, "tolist") else list(action)
            except Exception as e:
                logger.warning("[RL] predict failed: %s — using stub", e)
                act = self._stub_action(obs)
        else:
            act = self._stub_action(obs)

        lat_ms = (time.monotonic() - t0) * 1000
        self.infer_count += 1
        self.avg_ms       = (self.avg_ms * (self.infer_count - 1) + lat_ms) / self.infer_count

        return act, {"latency_ms": round(lat_ms, 2), "algorithm": self.algorithm}

    def _stub_action(self, obs: List[float]) -> List[float]:
        """Random bounded action — safe exploration for stub mode."""
        import random
        rng = random.Random(hash(tuple(obs[:4])) % 2**32)
        return [
            rng.uniform(-0.3, 0.5),   # linear: mostly forward
            rng.uniform(-0.5, 0.5),   # angular
        ]

    def save(self, path: str) -> None:
        if self._model and hasattr(self._model, "save"):
            self._model.save(path)
            self.model_path = path
            logger.info("[RL] policy '%s' saved to %s", self.name, path)

    def load(self, path: str) -> bool:
        try:
            if self.algorithm == "ppo":
                from stable_baselines3 import PPO
                self._model = PPO.load(path)
            elif self.algorithm == "sac":
                from stable_baselines3 import SAC
                self._model = SAC.load(path)
            elif self.algorithm == "dqn":
                from stable_baselines3 import DQN
                self._model = DQN.load(path)
            self.model_path = path
            logger.info("[RL] loaded policy '%s' from %s", self.name, path)
            return True
        except ImportError:
            logger.warning("[RL] stable-baselines3 not installed — stub policy")
            return False
        except Exception as e:
            logger.error("[RL] load failed: %s", e)
            return False


# ── Environment ────────────────────────────────────────────────────────────
class RLEnvironment:
    """
    Wraps a NEUROS Robot as a Gym-compatible RL environment.

    Parameters
    ----------
    robot          : NEUROS Robot instance (usually with SimulatorHAL)
    reward_fn      : callable(obs, action, next_obs) → float
    episode_steps  : max steps per episode (default 500)
    obs_topics     : list of Neural Bus topics to include in observation

    Gym compatibility
    -----------------
    This class exposes reset() and step() matching the Gym API so
    stable-baselines3 / RLlib / custom trainers can use it directly.

    Step reward shaping guide
    -------------------------
    Pass a reward_fn:
        def my_reward(obs, action, next_obs):
            forward_speed = action[0]
            collision_dist = obs[-8]  # first LiDAR sector
            reward = forward_speed * 1.0
            if collision_dist < 0.3:
                reward -= 10.0
            return reward
    """

    OBS_TOPICS = [
        "/robot/nav/odom/pose",
        "/robot/sensor/imu/full",
        "/robot/sensor/lidar/lidar/sectors",
        "/robot/sensor/battery",
    ]

    def __init__(
        self,
        robot: "Robot",
        *,
        reward_fn: Optional[Callable] = None,
        episode_steps: int  = 500,
        obs_topics: Optional[List[str]] = None,
    ) -> None:
        self._robot        = robot
        self._reward_fn    = reward_fn or self._default_reward
        self._max_steps    = episode_steps
        self._obs_topics   = obs_topics or self.OBS_TOPICS

        self._obs_buffer: Dict[str, Any] = {}
        self._step_count  = 0
        self._episode     = 0
        self._total_reward = 0.0

        # Subscribe to observation topics
        for topic in self._obs_topics:
            robot._bus.subscribe(topic, self._on_obs)

    def _on_obs(self, msg) -> None:
        self._obs_buffer[msg.topic] = msg.data

    def reset(self) -> List[float]:
        """Reset the environment. Returns initial observation."""
        self._step_count   = 0
        self._episode     += 1
        self._total_reward = 0.0
        # Stop robot
        self._robot.publish("cmd/stop", {})
        time.sleep(0.05)
        return self._get_obs()

    def step(
        self,
        action: List[float],
    ) -> Tuple[List[float], float, bool, dict]:
        """
        Apply action and return (next_obs, reward, done, info).

        Parameters
        ----------
        action : [linear_speed, angular_speed]

        Returns
        -------
        obs    : next observation
        reward : float
        done   : episode terminated?
        info   : metadata dict
        """
        obs_before = self._get_obs()

        # Apply action → motor commands
        linear  = float(action[0]) if len(action) > 0 else 0.0
        angular = float(action[1]) if len(action) > 1 else 0.0
        self._robot.publish("/robot/cmd/velocity", {
            "linear":  linear,
            "angular": angular,
        })

        # Wait one control step
        time.sleep(1.0 / 20.0)   # 20 Hz control
        self._step_count += 1

        obs_next = self._get_obs()
        reward   = self._reward_fn(obs_before, action, obs_next)
        self._total_reward += reward

        # Episode termination conditions
        done = (
            self._step_count >= self._max_steps
            or self._check_collision(obs_next)
            or not self._robot._kernel.state.value == "RUNNING"
        )

        if done:
            self._robot.publish("cmd/stop", {})

        return obs_next, reward, done, {
            "step":          self._step_count,
            "episode":       self._episode,
            "total_reward":  round(self._total_reward, 3),
        }

    def _get_obs(self) -> List[float]:
        """Build flat observation vector from buffered topic data."""
        obs = []
        # Pose [x, y, theta, vx, omega]
        pose = self._obs_buffer.get("/robot/nav/odom/pose", {})
        obs += [
            float(pose.get("x",     0.0)),
            float(pose.get("y",     0.0)),
            float(pose.get("theta", 0.0)),
            float(pose.get("vx",    0.0)),
            float(pose.get("omega", 0.0)),
        ]
        # IMU [ax, ay, az]
        imu = self._obs_buffer.get("/robot/sensor/imu/full", {})
        obs += [
            float(imu.get("ax", 0.0)),
            float(imu.get("ay", 0.0)),
            float(imu.get("az", 9.81)),
        ]
        # LiDAR sectors [N, NE, E, SE, S, SW, W, NW]
        sectors = self._obs_buffer.get(
            "/robot/sensor/lidar/lidar/sectors", {}
        ).get("sectors", {})
        for s in ["N","NE","E","SE","S","SW","W","NW"]:
            obs.append(float(sectors.get(s, 12.0)))
        # Battery [soc_pct]
        batt = self._obs_buffer.get("/robot/sensor/battery", {})
        obs.append(float(batt.get("soc_pct", 100.0)))
        return obs

    def _check_collision(self, obs: List[float]) -> bool:
        """Check if any LiDAR sector < 0.2m (collision)."""
        lidar_start = 8   # sectors start at index 8 in obs vector
        for i in range(lidar_start, lidar_start + 8):
            if i < len(obs) and obs[i] < 0.2:
                return True
        return False

    @staticmethod
    def _default_reward(obs_before: List[float], action: List[float],
                        obs_after: List[float]) -> float:
        """Default reward: forward progress − collision penalty."""
        linear  = float(action[0]) if action else 0.0
        reward  = linear * 0.5   # reward forward motion

        # Penalty for being close to obstacles
        lidar_start = 8
        min_dist = min((obs_after[i] for i in range(lidar_start, lidar_start + 8)
                        if i < len(obs_after)), default=12.0)
        if min_dist < 0.5:
            reward -= (0.5 - min_dist) * 5.0

        return float(reward)


# ── Engine ────────────────────────────────────────────────────────────────
class RLEngine:
    """
    RL training and deployment engine.

    Parameters
    ----------
    robot       : NEUROS Robot (SimulatorHAL recommended for training)
    algorithm   : "ppo" | "sac" | "dqn" | "stub"
    policy_name : identifier for the policy

    Usage
    -----
        # Training
        engine = RLEngine(sim_robot, algorithm="ppo")
        engine.train(total_steps=100_000, save_path="my_policy.zip")

        # Deployment (hot-swap policy into running robot)
        engine.deploy(real_robot)
    """

    def __init__(
        self,
        robot:       "Robot",
        *,
        algorithm:   str = "stub",
        policy_name: str = "neuros_policy",
        reward_fn:   Optional[Callable] = None,
    ) -> None:
        self._robot      = robot
        self._algorithm  = algorithm
        self._policy     = RLPolicy(name=policy_name, algorithm=algorithm)
        self._env        = RLEnvironment(robot, reward_fn=reward_fn)
        self._sb3_model  = None
        self._running    = False
        self._thread:    Optional[threading.Thread] = None

    def train(
        self,
        total_steps: int  = 50_000,
        *,
        save_path:   str  = "",
        log_interval: int = 1000,
    ) -> RLPolicy:
        """Train the policy. Returns the trained policy."""
        logger.info("[RL] starting training | algo=%s steps=%d",
                    self._algorithm, total_steps)

        try:
            return self._sb3_train(total_steps, save_path, log_interval)
        except ImportError:
            logger.warning("[RL] stable-baselines3 not installed — stub training")
            return self._stub_train(total_steps)

    def _sb3_train(self, steps, save_path, log_interval) -> RLPolicy:
        import numpy as np
        try:
            import gymnasium as gym
        except ImportError:
            import gym

        # Wrap our environment for SB3
        class _GymWrapper(gym.Env):
            def __init__(self_, env):
                self_.env  = env
                obs_len    = len(env._get_obs())
                self_.observation_space = gym.spaces.Box(
                    low=-100, high=100, shape=(obs_len,), dtype=np.float32
                )
                self_.action_space = gym.spaces.Box(
                    low=np.array([-0.5, -1.0]),
                    high=np.array([0.5,  1.0]),
                    dtype=np.float32,
                )
            def reset(self_, **kw):
                obs = self_.env.reset()
                return np.array(obs, dtype=np.float32), {}
            def step(self_, action):
                obs, rew, done, info = self_.env.step(action.tolist())
                return np.array(obs, dtype=np.float32), rew, done, False, info

        wrapped = _GymWrapper(self._env)

        if self._algorithm == "ppo":
            from stable_baselines3 import PPO
            self._sb3_model = PPO("MlpPolicy", wrapped,
                                  verbose=1, n_steps=256)
        elif self._algorithm == "sac":
            from stable_baselines3 import SAC
            self._sb3_model = SAC("MlpPolicy", wrapped, verbose=1)
        elif self._algorithm == "dqn":
            from stable_baselines3 import DQN
            self._sb3_model = DQN("MlpPolicy", wrapped, verbose=1)
        else:
            return self._stub_train(steps)

        self._sb3_model.learn(total_timesteps=steps, log_interval=log_interval)

        if save_path:
            self._sb3_model.save(save_path)
            self._policy.model_path = save_path

        self._policy._model    = self._sb3_model
        self._policy.algorithm = self._algorithm
        logger.info("[RL] training complete")
        return self._policy

    def _stub_train(self, steps: int) -> RLPolicy:
        """Simulate training progress without ML library."""
        logger.info("[RL] stub training for %d steps", steps)
        for i in range(0, steps, max(1, steps // 10)):
            time.sleep(0.01)
            logger.debug("[RL] stub step %d/%d", i, steps)
        self._policy.algorithm = "stub"
        return self._policy

    def deploy(self, robot: "Robot") -> None:
        """
        Deploy the trained policy to a (possibly different) robot.
        Creates a PolicyExecutorNode and adds it to the robot.
        """
        from neuros.nodes.ai.policy_node import PolicyExecutorNode
        node = PolicyExecutorNode(
            "rl_policy",
            policy=self._policy,
            hz=20.0,
        )
        robot.add_node(node)
        logger.info("[RL] policy '%s' deployed to robot '%s'",
                    self._policy.name, robot.name)

    @property
    def policy(self) -> RLPolicy:
        return self._policy
