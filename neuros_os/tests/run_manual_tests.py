"""NEUROS OS - Manual Test Scripts from Test Suite HTML"""
import time, sys, tracemalloc

results = {}

# ─── TEST: Robot Decorator API (@robot.every) ───
def test_robot_decorator_api():
    from neuros import Robot
    robot = Robot(name='blinker', board='simulator')
    robot.start()
    robot.pin('LED', pin=13, mode='output')
    count = [0]

    @robot.every(hz=10, name='blink')
    def blink():
        robot.toggle('LED')
        count[0] += 1

    time.sleep(0.5)
    robot.stop()
    ok = count[0] >= 4
    print(f"  Robot Decorator API: {count[0]} ticks in 500ms -> {'PASS' if ok else 'FAIL'}")
    return ok

# ─── TEST: E-stop chain propagation ───
def test_estop_chain():
    from neuros import Robot
    from neuros.safety import SafetySupervisor
    robot = Robot(board='simulator', kernel_hz=1000)
    robot.add_node(SafetySupervisor(battery_crit_v=3.0))
    robot.start()
    t0 = time.monotonic()
    robot.publish('cmd/estop', {'reason': 'industrial test'})
    time.sleep(0.05)
    t1 = time.monotonic()
    status = robot.status()
    lat_ms = (t1 - t0) * 1000
    state = status.get('state', '?')
    robot.stop()
    ok = state == 'EMERGENCY'
    print(f"  E-stop chain: {lat_ms:.1f}ms, state={state} -> {'PASS' if ok else 'FAIL (state not EMERGENCY, got '+state+')'}")
    return ok

# ─── TEST: NeuralBus high throughput ───
def test_bus_throughput():
    from neuros import NeuralBus, Message
    bus = NeuralBus()
    rx = [0]
    bus.subscribe('#', lambda m: rx.__setitem__(0, rx[0]+1))
    TX = 10000
    t0 = time.monotonic()
    for i in range(TX):
        bus.publish(Message(topic=f'/test/{i%10}', data={'i': i}))
    elapsed = time.monotonic() - t0
    rate = TX / elapsed
    ok = rx[0] == TX
    print(f"  Bus Throughput: TX={TX} RX={rx[0]} rate={rate:.0f} msg/s -> {'PASS' if ok else 'FAIL'}")
    return ok

# ─── TEST: Memory leak check ───
def test_memory_leak():
    from neuros import Robot
    tracemalloc.start()
    s1 = tracemalloc.take_snapshot()
    for i in range(20):
        r = Robot(board='simulator', kernel_hz=100)
        r.start()
        time.sleep(0.05)
        r.stop()
    s2 = tracemalloc.take_snapshot()
    top = s2.compare_to(s1, 'lineno')
    total = sum(s.size_diff for s in top)
    ok = total < 1024 * 1024  # < 1MB
    print(f"  Memory Leak: {total/1024:.1f}KB growth over 20 cycles -> {'PASS' if ok else 'FAIL'}")
    tracemalloc.stop()
    return ok

# ─── TEST: LLM stub parsing ───
def test_llm_stub():
    from neuros.ai import LLMOrchestrator
    llm = LLMOrchestrator()
    tests = [
        ("blink the led at 2 hz", "blink", {"hz": 2.0}),
        ("move forward at 0.3 m/s", "move_forward", {"speed": 0.3}),
        ("patrol the room", "patrol", {}),
        ("emergency stop now", "emergency_stop", {}),
        ("totally random nonsense xyz", "unknown", {}),
    ]
    all_ok = True
    for text, exp_action, _ in tests:
        i = llm.parse(text)
        ok = i.action == exp_action
        if not ok:
            all_ok = False
            print(f"    FAIL: '{text[:30]}' -> {i.action} (expected {exp_action})")
    print(f"  LLM Stub Parsing: 5/5 rules -> {'PASS' if all_ok else 'FAIL'}")
    return all_ok

# ─── TEST: Scheduler tick rate ───
def test_scheduler_tick():
    from neuros.kernel.scheduler import Scheduler
    s = Scheduler()
    c = [0]
    s.add('t', lambda: c.__setitem__(0, c[0]+1), hz=1000)
    s.start()
    time.sleep(0.1)
    s.stop()
    ok = c[0] > 80
    print(f"  Scheduler Tick: {c[0]} ticks in 100ms -> {'PASS' if ok else 'FAIL'}")
    return ok

# ─── TEST: Fault injection / node crash recovery ───
def test_fault_injection():
    from neuros import Robot, Node
    class CrashyNode(Node):
        def __init__(self):
            super().__init__('crashy', hz=10)
            self.tick_count = 0
        def tick(self):
            self.tick_count += 1
            if self.tick_count == 5:
                raise RuntimeError('simulated crash')
    robot = Robot(board='simulator')
    node = CrashyNode()
    robot.add_node(node)
    robot.start()
    time.sleep(3.0)
    status = robot.status()
    robot.stop()
    # Check if robot survived the crash
    ok = status.get('state') in ('RUNNING', 'EMERGENCY')
    print(f"  Fault Injection: Robot state={status.get('state')} after node crash -> {'PASS' if ok else 'FAIL'}")
    return ok

if __name__ == '__main__':
    import logging
    logging.disable(logging.CRITICAL)  # Suppress noisy logs

    print("=" * 60)
    print("NEUROS OS — Manual Test Suite Execution")
    print("=" * 60)

    test_funcs = [
        ("Robot Decorator API", test_robot_decorator_api),
        ("E-stop Chain", test_estop_chain),
        ("NeuralBus Throughput", test_bus_throughput),
        ("Memory Leak Check", test_memory_leak),
        ("LLM Stub Parsing", test_llm_stub),
        ("Scheduler Tick Rate", test_scheduler_tick),
        ("Fault Injection", test_fault_injection),
    ]

    passed = 0
    failed = 0
    for name, fn in test_funcs:
        try:
            ok = fn()
            if ok:
                passed += 1
                results[name] = "PASS"
            else:
                failed += 1
                results[name] = "FAIL"
        except Exception as e:
            failed += 1
            results[name] = f"ERROR: {e}"
            print(f"  {name}: ERROR - {e}")

    print("\n" + "=" * 60)
    print(f"RESULTS: {passed} PASSED, {failed} FAILED out of {len(test_funcs)}")
    print("=" * 60)
    for name, result in results.items():
        symbol = "✓" if result == "PASS" else "✗"
        print(f"  {symbol} {name}: {result}")
    print("=" * 60)
