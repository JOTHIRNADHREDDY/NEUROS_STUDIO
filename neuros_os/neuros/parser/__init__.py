"""
neuros.parser
=============
Plain English Rule Parser — Phase 1, Component #6.

Converts natural-language robot commands into NEUROS API calls
using a regex-based rule engine. No LLM required.

Architecture
------------
Phase 1: Regex + rule-based pattern matching
Phase 3: LLM orchestration (upgrades, not replaces, this)

The parser works in 3 stages:
  1. Tokenize  — split into words, normalize synonyms
  2. Match     — find the best rule pattern
  3. Generate  — produce NEUROS API code or execute directly

Supported commands (Phase 1)
-----------------------------
  "blink LED every 500ms"
  "blink the LED every 2 seconds"
  "if distance is less than 20cm, stop motors"
  "move forward at half speed"
  "turn left 90 degrees"
  "set servo to 45 degrees"
  "read temperature sensor"
  "stop all motors"
  "when button is pressed, toggle LED"
  "follow the line"
  "avoid obstacles"
  "set LED brightness to 50%"

Usage
-----
    from neuros.parser import PlainEnglishParser

    parser = PlainEnglishParser()
    result = parser.parse("blink LED every 500ms")
    print(result.code)       # generated Python code
    print(result.confidence) # 0.0 - 1.0

    # Or execute directly on a robot
    parser.execute("move forward at half speed", robot=my_robot)
"""

from neuros.parser.engine import PlainEnglishParser, ParseResult, ParsedAction

__all__ = ["PlainEnglishParser", "ParseResult", "ParsedAction"]
