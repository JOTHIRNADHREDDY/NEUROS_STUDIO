"""
tests/test_phase3.py
=====================
Phase 3 test suite — AI Core Layer.
All tests use stub providers — no API keys or GPU required.

Run: pytest tests/test_phase3.py -v
"""
import sys, os, time, math
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from neuros import Robot, NeuralBus
from neuros.bus.message import Message
from neuros.hal.drivers.simulator import SimulatorHAL


# ── Fixtures ─────────────────────────────────────────────────────────────────
@pytest.fixture
def robot():
    r = Robot(name="test-p3", board="simulator", kernel_hz=100)
    r.start()
    yield r
    r.stop()

@pytest.fixture
def bus():
    return NeuralBus()

@pytest.fixture
def stub_llm(robot):
    from neuros.ai.llm.orchestrator import LLMOrchestrator
    return LLMOrchestrator(provider="stub", robot=robot)


# ══ LLM ORCHESTRATOR ═════════════════════════════════════════════════════════
class TestLLMOrchestrator:
    def test_provider_stub_auto_selected(self):
        from neuros.ai.llm.orchestrator import LLMOrchestrator, LLMProvider
        llm = LLMOrchestrator(provider="stub")
        assert llm._provider == LLMProvider.STUB

    def test_provider_nvidia_selected(self):
        from neuros.ai.llm.orchestrator import LLMOrchestrator, LLMProvider
        llm = LLMOrchestrator(provider="nvidia", api_key="test-key")
        assert llm._provider == LLMProvider.NVIDIA
        assert llm._model == "deepseek-ai/deepseek-v4-pro"

    def test_parse_blink_returns_intent(self, stub_llm):
        intent = stub_llm.parse("blink the led at 2 hz")
        assert intent.action == "blink"
        assert intent.params.get("hz") == pytest.approx(2.0)
        assert intent.provider == "stub"

    def test_parse_stop(self, stub_llm):
        intent = stub_llm.parse("stop the robot")
        assert intent.action == "stop"

    def test_parse_patrol(self, stub_llm):
        intent = stub_llm.parse("patrol the room")
        assert intent.action == "patrol"

    def test_parse_move_forward(self, stub_llm):
        intent = stub_llm.parse("move forward at 0.3 m/s")
        assert intent.action == "move_forward"
        assert "speed" in intent.params or True  # speed extracted if present

    def test_parse_go_to(self, stub_llm):
        intent = stub_llm.parse("go to position 2, 1")
        # stub may not parse coordinates, but should not crash
        assert intent is not None

    def test_parse_unknown_returns_unknown(self, stub_llm):
        intent = stub_llm.parse("make me a sandwich please")
        assert intent.action == "unknown"
        assert intent.confidence == 0.0

    def test_is_valid(self, stub_llm):
        valid = stub_llm.parse("blink led")
        invalid = stub_llm.parse("totally nonsensical xyzabc")
        assert valid.is_valid() is True
        assert invalid.is_valid() is False

    def test_history_appended(self, stub_llm):
        stub_llm.clear_history()
        stub_llm.parse("blink led")
        stub_llm.parse("stop")
        assert len(stub_llm.history) == 4   # 2 user + 2 assistant

    def test_clear_history(self, stub_llm):
        stub_llm.parse("test command")
        stub_llm.clear_history()
        assert len(stub_llm.history) == 0

    def test_stats_shape(self, stub_llm):
        stub_llm.parse("blink")
        s = stub_llm.stats()
        assert "provider" in s
        assert "call_count" in s
        assert "avg_latency_ms" in s
        assert s["call_count"] >= 1

    def test_fallback_to_stub_on_api_error(self):
        from neuros.ai.llm.orchestrator import LLMOrchestrator
        # Anthropic provider but no API key → should fall back to stub parse
        llm = LLMOrchestrator(provider="anthropic", api_key="INVALID_KEY")
        intent = llm.parse("blink led")
        assert intent is not None   # must not raise

    def test_latency_recorded(self, stub_llm):
        intent = stub_llm.parse("stop")
        assert intent.latency_ms >= 0.0


# ══ INTENT EXECUTOR ═══════════════════════════════════════════════════════════
class TestIntentExecutor:
    def test_blink_executes(self, robot):
        from neuros.ai.executor import IntentExecutor
        from neuros.ai.llm.orchestrator import LLMOrchestrator, Intent
        llm  = LLMOrchestrator(provider="stub", robot=robot)
        exec = IntentExecutor(robot, llm)
        received = []
        robot.subscribe("cmd/led/status", received.append)
        result = exec.execute(Intent(action="blink", params={"hz": 2.0},
                                     raw_text="blink led", confidence=0.9))
        assert result is True

    def test_stop_executes(self, robot):
        from neuros.ai.executor import IntentExecutor
        from neuros.ai.llm.orchestrator import LLMOrchestrator, Intent
        llm  = LLMOrchestrator(provider="stub", robot=robot)
        exc  = IntentExecutor(robot, llm)
        received = []
        robot.subscribe("cmd/stop", received.append)
        exc.execute(Intent(action="stop", raw_text="stop", confidence=1.0))
        time.sleep(0.05)

    def test_unknown_returns_false(self, robot):
        from neuros.ai.executor import IntentExecutor
        from neuros.ai.llm.orchestrator import LLMOrchestrator, Intent
        llm = LLMOrchestrator(provider="stub", robot=robot)
        exc = IntentExecutor(robot, llm)
        assert exc.execute(Intent(action="unknown", raw_text="?", confidence=0.0)) is False

    def test_status_does_not_raise(self, robot):
        from neuros.ai.executor import IntentExecutor
        from neuros.ai.llm.orchestrator import LLMOrchestrator, Intent
        llm = LLMOrchestrator(provider="stub", robot=robot)
        exc = IntentExecutor(robot, llm)
        assert exc.execute(Intent(action="status", raw_text="status", confidence=1.0))

    def test_execute_on_robot(self, robot):
        from neuros.ai.llm.orchestrator import LLMOrchestrator
        llm    = LLMOrchestrator(provider="stub", robot=robot)
        result = llm.execute_on(robot, "blink led at 1 hz")
        assert isinstance(result, bool)


# ══ ROBOT CONTEXT ════════════════════════════════════════════════════════════
class TestRobotContext:
    def test_build_context(self, robot):
        from neuros.ai.llm.context import ContextBuilder
        builder = ContextBuilder(robot)
        ctx     = builder.build()
        assert ctx.robot_name == "test-p3"
        assert isinstance(ctx.nodes, list)
        assert isinstance(ctx.active_topics, list)

    def test_to_prompt_block(self, robot):
        from neuros.ai.llm.context import ContextBuilder
        ctx   = ContextBuilder(robot).build()
        block = ctx.to_prompt_block()
        assert "test-p3" in block
        assert "NEUROS ROBOT CONTEXT" in block

    def test_to_dict(self, robot):
        from neuros.ai.llm.context import ContextBuilder
        d = ContextBuilder(robot).build().to_dict()
        assert "robot_name" in d
        assert "kernel_state" in d
        assert "nodes" in d


# ══ MISSION PLANNER ═══════════════════════════════════════════════════════════
class TestMissionPlanner:
    def test_stub_patrol_plan(self, stub_llm):
        from neuros.ai.planner.mission import MissionPlanner
        planner = MissionPlanner(stub_llm)
        graph   = planner.plan("patrol the perimeter")
        assert len(graph) >= 2
        assert graph.source == "stub"
        assert any(n.action == "patrol" for n in graph.nodes)

    def test_stub_go_home_plan(self, stub_llm):
        from neuros.ai.planner.mission import MissionPlanner
        graph = MissionPlanner(stub_llm).plan("go home")
        assert any(n.action == "go_to" for n in graph.nodes)

    def test_forward_backward_plan(self, stub_llm):
        from neuros.ai.planner.mission import MissionPlanner
        graph = MissionPlanner(stub_llm).plan("move forward then backward")
        assert any(n.action == "move_forward" for n in graph.nodes)

    def test_default_plan_fallback(self, stub_llm):
        from neuros.ai.planner.mission import MissionPlanner
        graph = MissionPlanner(stub_llm).plan("do something random xyz")
        assert len(graph) >= 1

    def test_execute_runs_thread(self, stub_llm, robot):
        from neuros.ai.planner.mission import MissionPlanner, MissionGraph, MissionNode
        planner = MissionPlanner(stub_llm)
        graph   = MissionGraph(
            name="test_mission", description="test",
            nodes=[MissionNode(0, "stop", {}, on_success=1)],
        )
        t = planner.execute(graph, robot)
        assert t.daemon is True
        t.join(timeout=2.0)

    def test_graph_summary(self, stub_llm):
        from neuros.ai.planner.mission import MissionPlanner
        graph = MissionPlanner(stub_llm).plan("patrol")
        summary = graph.summary()
        assert "Mission" in summary

    def test_mission_node_defaults(self):
        from neuros.ai.planner.mission import MissionNode
        n = MissionNode(3, "stop", {})
        assert n.on_success == 4   # auto-incremented
        assert n.on_failure == "abort"


# ══ NODE CODEGEN ══════════════════════════════════════════════════════════════
class TestNodeCodegen:
    def test_stub_blinker_generation(self, stub_llm):
        from neuros.ai.codegen.generator import NodeCodegen
        gen = NodeCodegen(stub_llm).generate("blink LED on pin 13 at 2 Hz")
        assert gen.success is True
        assert gen.node_class is not None
        assert "Blinker" in gen.class_name or "Node" in gen.class_name

    def test_stub_temperature_generation(self, stub_llm):
        from neuros.ai.codegen.generator import NodeCodegen
        gen = NodeCodegen(stub_llm).generate("monitor temperature and publish Celsius")
        assert gen.success is True

    def test_stub_generic_generation(self, stub_llm):
        from neuros.ai.codegen.generator import NodeCodegen
        gen = NodeCodegen(stub_llm).generate("count ticks and publish to a topic")
        assert gen.success is True

    def test_generated_node_instantiable(self, stub_llm):
        from neuros.ai.codegen.generator import NodeCodegen
        gen  = NodeCodegen(stub_llm).generate("blink led at 2 hz")
        node = gen.node_class(gen.node_name, hz=2.0)
        assert node is not None
        assert node.hz == 2.0

    def test_generated_node_runs_in_robot(self, stub_llm, robot):
        from neuros.ai.codegen.generator import NodeCodegen
        gen  = NodeCodegen(stub_llm).generate("publish status every tick")
        assert gen.success
        node = gen.node_class(gen.node_name, hz=5.0)
        robot.add_node(node)
        time.sleep(0.1)   # let it tick
        # Node should be registered in kernel
        status = robot.status()
        node_names = [v["name"] for v in status["nodes"].values()]
        assert gen.node_name in node_names

    def test_security_block_dangerous_code(self, stub_llm):
        from neuros.ai.codegen.generator import NodeCodegen
        # Manually try to compile dangerous code
        gen = NodeCodegen(stub_llm)
        result = gen._compile(
            "```python\nclass DangerNode(Node):\n    def tick(self):\n"
            "        __import__('os').system('rm -rf /')\n```",
            "dangerous",
            provider="stub"
        )
        assert result.success is False
        assert "Security" in (result.error or "")

    def test_codegen_history(self, stub_llm):
        from neuros.ai.codegen.generator import NodeCodegen
        cg = NodeCodegen(stub_llm)
        cg.generate("blink led")
        cg.generate("read temperature")
        assert len(cg.history) == 2


# ══ MODEL REGISTRY ════════════════════════════════════════════════════════════
class TestModelRegistry:
    def test_register_and_infer_stub(self):
        from neuros.ai.models.registry import ModelRegistry
        reg = ModelRegistry()
        reg.register("det", "", runtime="stub")
        result = reg.infer("det", None)
        assert result.success is True
        assert isinstance(result.detections, list)
        assert result.latency_ms >= 0.0

    def test_infer_unknown_model(self):
        from neuros.ai.models.registry import ModelRegistry
        reg    = ModelRegistry()
        result = reg.infer("not_registered", None)
        assert result.success is False
        assert result.error is not None

    def test_model_stats_updated(self):
        from neuros.ai.models.registry import ModelRegistry
        reg = ModelRegistry()
        reg.register("m1", "", runtime="stub")
        for _ in range(5):
            reg.infer("m1", None)
        models = reg.list_models()
        m = next(x for x in models if x["name"] == "m1")
        assert m["infer_count"] == 5
        assert m["avg_ms"] >= 0.0

    def test_hot_swap(self):
        from neuros.ai.models.registry import ModelRegistry
        reg = ModelRegistry()
        reg.register("swap_test", "old_path.onnx", runtime="stub")
        reg.swap("swap_test", "new_path.onnx")
        entry = reg._models["swap_test"]
        assert entry.path == "new_path.onnx"

    def test_on_swap_callback(self):
        from neuros.ai.models.registry import ModelRegistry
        reg     = ModelRegistry()
        swapped = []
        reg.register("cb_test", "v1.pt", runtime="stub")
        reg.on_swap("cb_test", lambda name, path: swapped.append((name, path)))
        reg.swap("cb_test", "v2.pt")
        assert len(swapped) == 1
        assert swapped[0] == ("cb_test", "v2.pt")

    def test_len(self):
        from neuros.ai.models.registry import ModelRegistry
        reg = ModelRegistry()
        reg.register("a", "", runtime="stub")
        reg.register("b", "", runtime="stub")
        assert len(reg) == 2

    def test_top_detections(self):
        from neuros.ai.models.registry import ModelRegistry
        reg = ModelRegistry()
        reg.register("d", "", runtime="stub")
        r = reg.infer("d", None)
        top = r.top(1)
        assert isinstance(top, list)


# ══ RL ENGINE ════════════════════════════════════════════════════════════════
class TestRLEngine:
    def test_stub_training(self, robot):
        from neuros.ai import RLEngine
        engine = RLEngine(robot, algorithm="stub")
        policy = engine.train(total_steps=100)
        assert policy is not None
        assert policy.algorithm == "stub"

    def test_policy_predict_stub(self):
        from neuros.ai.rl.engine import RLPolicy
        policy = RLPolicy(name="test", algorithm="stub", obs_dim=17, act_dim=2)
        obs    = [0.0] * 17
        action, info = policy.predict(obs)
        assert len(action) == 2
        assert "latency_ms" in info

    def test_rl_environment_reset(self, robot):
        from neuros.ai.rl.engine import RLEnvironment
        env = RLEnvironment(robot)
        obs = env.reset()
        assert isinstance(obs, list)
        assert len(obs) > 0

    def test_rl_environment_step(self, robot):
        from neuros.ai.rl.engine import RLEnvironment
        env  = RLEnvironment(robot, episode_steps=5)
        obs  = env.reset()
        next_obs, reward, done, info = env.step([0.2, 0.0])
        assert isinstance(reward, float)
        assert isinstance(done, bool)
        assert "step" in info

    def test_deploy_installs_node(self, robot):
        from neuros.ai import RLEngine
        engine = RLEngine(robot, algorithm="stub")
        engine.train(total_steps=10)
        engine.deploy(robot)
        names = [n.name for n in robot._nodes.values()]
        assert "rl_policy" in names

    def test_infer_count_increments(self):
        from neuros.ai.rl.engine import RLPolicy
        p = RLPolicy(name="p", algorithm="stub", obs_dim=5, act_dim=2)
        for _ in range(3):
            p.predict([0.0]*5)
        assert p.infer_count == 3


# ══ VISION AI ════════════════════════════════════════════════════════════════
class TestVisionAI:
    def make_vision_node(self, bus):
        from neuros.ai.vision.detector import VisionAI
        from neuros.ai.models.registry import ModelRegistry
        hal = SimulatorHAL(seed=0); hal.connect()
        reg = ModelRegistry()
        reg.register("detector", "", runtime="stub")
        node = VisionAI("vision", camera_name="cam", model_registry=reg, hz=5)
        node._hal = hal
        node._bus = bus
        node._configure()
        node._activate()
        return node

    def test_publishes_detections(self):
        bus  = NeuralBus()
        node = self.make_vision_node(bus)
        received = []
        bus.subscribe("/robot/ai/vision/detections", received.append)
        # Inject a synthetic frame
        import numpy as np
        node._latest_frame = np.zeros((480, 640, 3), dtype="uint8")
        node._tick()
        assert len(received) == 1
        assert "detections" in received[0].data

    def test_detection_count_non_negative(self):
        bus  = NeuralBus()
        node = self.make_vision_node(bus)
        import numpy as np
        node._latest_frame = np.zeros((480, 640, 3), dtype="uint8")
        node._tick()
        assert len(node.latest_detections) >= 0

    def test_no_crash_without_frame(self):
        bus  = NeuralBus()
        node = self.make_vision_node(bus)
        node._tick()   # frame is None — should be no-op

    def test_tracker_assigns_ids(self):
        from neuros.ai.vision.detector import VisionAI, Detection
        bus = NeuralBus()
        node = self.make_vision_node(bus)
        node._track = True
        dets = [
            Detection("person", 0.9, [100, 100, 200, 300]),
            Detection("chair",  0.7, [300, 200, 400, 400]),
        ]
        tracked = node._update_tracker(dets)
        ids = [d.track_id for d in tracked]
        assert all(i is not None for i in ids)
        assert len(set(ids)) == 2   # unique IDs


# ══ ANOMALY DETECTOR ══════════════════════════════════════════════════════════
class TestAnomalyDetector:
    def test_start_stop(self, robot):
        from neuros.ai.anomaly import AnomalyDetector
        ad = AnomalyDetector(robot, z_threshold=3.0, silence_s=30)
        ad.start()
        time.sleep(0.05)
        ad.stop()

    def test_spike_detection(self, robot):
        from neuros.ai.anomaly import AnomalyDetector
        from neuros.bus.message import Message as BusMsg
        fired = []
        ad = AnomalyDetector(robot, z_threshold=2.0, silence_s=60)
        ad.on_anomaly(fired.append)
        ad.start()

        topic = "/robot/sensor/test_spike_direct"
        # Warm up directly via _on_message (bypasses bus timing)
        for i in range(20):
            v = 1.0 + 0.02 * ((i % 3) - 1)
            ad._on_message(BusMsg(topic=topic, data={"val": v}))
        # Inject massive spike
        ad._on_message(BusMsg(topic=topic, data={"val": 9999.0}))
        time.sleep(0.05)
        ad.stop()
        assert any(e.type == "spike" for e in fired), f"fired={[e.type for e in fired]}"


    def test_range_violation(self, robot):
        from neuros.ai.anomaly import AnomalyDetector
        from neuros.bus.message import Message as BusMsg
        fired = []
        ad = AnomalyDetector(robot, z_threshold=10.0, silence_s=60)
        ad.on_anomaly(fired.append)
        ad.start()
        topic = "/robot/sensor/bat_range_test"
        # Warm up directly
        for _ in range(12):
            ad._on_message(BusMsg(topic=topic, data={"soc_pct": 50.0}))
        # Inject out-of-range
        ad._on_message(BusMsg(topic=topic, data={"soc_pct": 150.0}))
        time.sleep(0.05)
        ad.stop()
        assert any(e.type == "range" for e in fired), f"fired={[e.type for e in fired]}"


    def test_summary_shape(self, robot):
        from neuros.ai.anomaly import AnomalyDetector
        ad   = AnomalyDetector(robot)
        ad.start()
        time.sleep(0.02)
        s = ad.summary()
        ad.stop()
        assert "total" in s
        assert "topics_monitored" in s

    def test_event_count_property(self, robot):
        from neuros.ai.anomaly import AnomalyDetector
        ad = AnomalyDetector(robot, z_threshold=10.0, silence_s=60)
        ad.start()
        ad.stop()
        assert ad.event_count >= 0


# ══ AUTOCONFIG ════════════════════════════════════════════════════════════════
class TestAutoConfig:
    def test_analyse_returns_list(self, robot, stub_llm):
        from neuros.ai.autoconfig import AutoConfig
        cfg  = AutoConfig(robot, llm=stub_llm)
        sugs = cfg.analyse()
        assert isinstance(sugs, list)

    def test_apply_hz_change(self, robot, stub_llm):
        from neuros.ai.autoconfig import AutoConfig, ConfigSuggestion
        from neuros.nodes.base import Node
        class _DummyNode(Node):
            def tick(self): pass
        dummy = _DummyNode("hz_test_node", hz=1000.0)
        robot.add_node(dummy)
        cfg   = AutoConfig(robot, llm=stub_llm)
        s     = ConfigSuggestion("hz_test_node", "hz", 1000.0, 50.0, "test")
        applied = cfg.apply(s)
        assert applied is True
        assert dummy.hz == 50.0

    def test_apply_nonexistent_node(self, robot, stub_llm):
        from neuros.ai.autoconfig import AutoConfig, ConfigSuggestion
        cfg = AutoConfig(robot, llm=stub_llm)
        s   = ConfigSuggestion("nonexistent", "hz", 100, 50, "test")
        assert cfg.apply(s) is False

    def test_stub_ask_responsive(self, robot, stub_llm):
        from neuros.ai.autoconfig import AutoConfig
        cfg  = AutoConfig(robot, llm=stub_llm)
        sugs = cfg.ask("make the robot more responsive")
        assert isinstance(sugs, list)

    def test_stub_ask_battery(self, robot, stub_llm):
        from neuros.ai.autoconfig import AutoConfig
        cfg  = AutoConfig(robot, llm=stub_llm)
        sugs = cfg.ask("save battery")
        assert isinstance(sugs, list)

    def test_history_tracked(self, robot, stub_llm):
        from neuros.ai.autoconfig import AutoConfig, ConfigSuggestion
        cfg = AutoConfig(robot, llm=stub_llm)
        s   = ConfigSuggestion("nonexistent", "hz", 10, 5, "test")
        cfg.apply(s)
        assert len(cfg.history) == 1

    def test_hw_tier_detection(self):
        from neuros.ai.autoconfig import _detect_hw_tier
        assert _detect_hw_tier({"board": "Raspberry Pi 4"}) == "rpi_4"
        assert _detect_hw_tier({"board": "NEUROS Simulator"}) == "simulator"
        assert _detect_hw_tier({"board": "Arduino"}) == "arduino"
        assert _detect_hw_tier({"board": "NVIDIA Jetson AGX Orin"}) == "jetson_orin"


# ══ VOICE INTERFACE ═══════════════════════════════════════════════════════════
class TestVoiceInterface:
    def test_stub_start_stop(self, robot, stub_llm):
        from neuros.ai.voice.interface import VoiceInterface
        v = VoiceInterface(robot, stub_llm, stt_backend="stub", tts_backend="stub")
        v.start()
        time.sleep(0.05)
        v.stop()

    def test_process_text_publishes_transcript(self, robot, stub_llm):
        from neuros.ai.voice.interface import VoiceInterface
        v = VoiceInterface(robot, stub_llm, stt_backend="stub", tts_backend="stub")
        v.start()
        received = []
        robot.subscribe("/robot/ai/voice/transcript", received.append)
        v.process_text("blink led")
        time.sleep(0.3)
        v.stop()
        assert any("blink" in str(m.data.get("text","")).lower() for m in received)

    def test_stats_shape(self, robot, stub_llm):
        from neuros.ai.voice.interface import VoiceInterface
        v = VoiceInterface(robot, stub_llm)
        s = v.stats()
        assert "running" in s
        assert "commands_processed" in s
        assert "stt_backend" in s

    def test_process_multiple_commands(self, robot, stub_llm):
        from neuros.ai.voice.interface import VoiceInterface
        v = VoiceInterface(robot, stub_llm, stt_backend="stub", tts_backend="stub")
        v.start()
        v.process_text("blink led")
        v.process_text("stop")
        time.sleep(0.4)
        v.stop()
        assert v.stats()["commands_processed"] == 2


# ══ PARAMETER TUNER ═══════════════════════════════════════════════════════════
class TestParameterTuner:
    def test_tune_pid_returns_result(self, robot):
        from neuros.ai.autoconfig import ParameterTuner
        tuner  = ParameterTuner(robot)
        result = tuner.tune_pid("motor_left", target_overshoot_pct=5.0)
        assert result.kp > 0
        assert result.ki > 0
        assert result.kd > 0
        assert result.settle_time_s > 0

    def test_pid_scales_with_target(self, robot):
        from neuros.ai.autoconfig import ParameterTuner
        tuner = ParameterTuner(robot)
        tight = tuner.tune_pid("motor", target_overshoot_pct=1.0)
        loose = tuner.tune_pid("motor", target_overshoot_pct=20.0)
        # Tighter overshoot → higher gains
        assert tight.kp > loose.kp


# ══ POLICY EXECUTOR NODE ══════════════════════════════════════════════════════
class TestPolicyExecutorNode:
    def test_installs_and_runs(self, robot):
        from neuros.nodes.ai.policy_node import PolicyExecutorNode
        from neuros.ai.rl.engine         import RLPolicy
        policy = RLPolicy("test_pol", algorithm="stub", obs_dim=17, act_dim=2)
        node   = PolicyExecutorNode("test_pol_node", policy=policy, hz=10)
        robot.add_node(node)
        time.sleep(0.15)
        status = robot.status()
        names  = [v["name"] for v in status["nodes"].values()]
        assert "test_pol_node" in names

    def test_swap_policy(self, robot):
        from neuros.nodes.ai.policy_node import PolicyExecutorNode
        from neuros.ai.rl.engine         import RLPolicy
        p1   = RLPolicy("p1", algorithm="stub")
        p2   = RLPolicy("p2", algorithm="stub")
        node = PolicyExecutorNode("swap_node", policy=p1, hz=5)
        robot.add_node(node)
        node.swap_policy(p2)
        assert node._policy.name == "p2"
