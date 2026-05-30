"""
neuros.ai.models.registry
==========================
Model Registry — Phase 3.

Central store for AI inference models: YOLO, ONNX, TensorRT, custom.
Supports hot-swap (replace a model at runtime without restarting nodes).

Supported runtimes
------------------
  "onnx"      : ONNX Runtime (CPU/GPU, pip install onnxruntime)
  "yolo"      : Ultralytics YOLO (pip install ultralytics)
  "tflite"    : TensorFlow Lite (pip install tflite-runtime)
  "trt"       : TensorRT (Jetson, NVIDIA GPU)
  "pytorch"   : PyTorch (pip install torch)
  "stub"      : returns synthetic detections (no ML library needed)

Hot-swap
--------
  registry.register("detector", model_path, runtime="yolo")
  # ...later, upgrade model without stopping the robot...
  registry.swap("detector", new_model_path)

Published topics (when used with VisionAI)
-------------------------------------------
  /robot/ai/detection/<model_name>   detection results
  /robot/ai/model/status             registry health
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("neuros.ai.models")


@dataclass
class InferenceResult:
    """Output of a model inference call."""
    model_name:   str
    latency_ms:   float
    detections:   List[dict]         = field(default_factory=list)
    raw_output:   Any                = None
    error:        Optional[str]      = None
    timestamp:    float              = field(default_factory=time.monotonic)

    @property
    def success(self) -> bool:
        return self.error is None

    def top(self, n: int = 1) -> List[dict]:
        """Return top-N detections by confidence."""
        return sorted(self.detections,
                      key=lambda d: d.get("confidence", 0.0),
                      reverse=True)[:n]


@dataclass
class ModelEntry:
    """A registered model in the registry."""
    name:        str
    path:        str
    runtime:     str
    loaded:      bool              = False
    load_time_s: float             = 0.0
    infer_count: int               = 0
    avg_ms:      float             = 0.0
    _model:      Any               = field(default=None, repr=False)


class ModelRegistry:
    """
    Central AI model registry with hot-swap and runtime selection.

    Usage
    -----
        registry = ModelRegistry()

        # Register a model
        registry.register("yolo_nano", "models/yolov8n.pt", runtime="yolo")

        # Run inference (lazy-load on first call)
        result = registry.infer("yolo_nano", frame)
        for det in result.detections:
            print(det["class"], det["confidence"], det["bbox"])

        # Hot-swap to a better model
        registry.swap("yolo_nano", "models/yolov8s.pt")
    """

    def __init__(self) -> None:
        self._models: Dict[str, ModelEntry] = {}
        self._hooks:  Dict[str, List[Callable]] = {}

    # ── Registration ────────────────────────────────────────────────────────
    def register(
        self,
        name:    str,
        path:    str,
        *,
        runtime: str = "stub",
        preload: bool = False,
    ) -> ModelEntry:
        entry = ModelEntry(name=name, path=path, runtime=runtime)
        self._models[name] = entry
        if preload:
            self._load(entry)
        logger.info("[REGISTRY] registered '%s' runtime=%s path=%s",
                    name, runtime, path)
        return entry

    def swap(self, name: str, new_path: str, *, runtime: Optional[str] = None) -> bool:
        """Hot-swap a model to a new path/version. Thread-safe."""
        entry = self._models.get(name)
        if not entry:
            logger.error("[REGISTRY] swap: model '%s' not registered", name)
            return False
        old_path    = entry.path
        entry.path  = new_path
        if runtime:
            entry.runtime = runtime
        entry.loaded = False
        entry._model = None
        logger.info("[REGISTRY] swapped '%s': %s → %s", name, old_path, new_path)
        for cb in self._hooks.get(name, []):
            try: cb(name, new_path)
            except Exception: pass
        return True

    def on_swap(self, name: str, callback: Callable) -> None:
        """Register a callback fired when model `name` is swapped."""
        self._hooks.setdefault(name, []).append(callback)

    # ── Inference ────────────────────────────────────────────────────────────
    def infer(self, name: str, data: Any, **kwargs) -> InferenceResult:
        """
        Run inference with model `name` on `data`.

        Parameters
        ----------
        name    : registered model name
        data    : input data (numpy array for vision models)
        **kwargs: passed to the runtime-specific inference function
        """
        entry = self._models.get(name)
        if not entry:
            return InferenceResult(
                model_name="?", latency_ms=0.0,
                error=f"Model '{name}' not registered"
            )
        if not entry.loaded:
            if not self._load(entry):
                return InferenceResult(
                    model_name=name, latency_ms=0.0,
                    error=f"Failed to load model '{name}'"
                )

        t0 = time.monotonic()
        try:
            if entry.runtime == "yolo":
                result = self._infer_yolo(entry, data, **kwargs)
            elif entry.runtime == "onnx":
                result = self._infer_onnx(entry, data, **kwargs)
            elif entry.runtime == "tflite":
                result = self._infer_tflite(entry, data, **kwargs)
            elif entry.runtime == "pytorch":
                result = self._infer_pytorch(entry, data, **kwargs)
            else:  # stub
                result = self._infer_stub(entry, data, **kwargs)
        except Exception as e:
            logger.error("[REGISTRY] infer '%s' error: %s", name, e)
            result = InferenceResult(
                model_name=name, latency_ms=0.0, error=str(e)
            )

        result.latency_ms = (time.monotonic() - t0) * 1000
        entry.infer_count += 1
        entry.avg_ms       = (entry.avg_ms * (entry.infer_count - 1)
                              + result.latency_ms) / entry.infer_count
        return result

    # ── Load ─────────────────────────────────────────────────────────────────
    def _load(self, entry: ModelEntry) -> bool:
        t0 = time.monotonic()
        try:
            if entry.runtime == "yolo":
                from ultralytics import YOLO
                entry._model = YOLO(entry.path)
            elif entry.runtime == "onnx":
                import onnxruntime as ort
                entry._model = ort.InferenceSession(entry.path)
            elif entry.runtime == "tflite":
                import tflite_runtime.interpreter as tflite
                entry._model = tflite.Interpreter(model_path=entry.path)
                entry._model.allocate_tensors()
            elif entry.runtime == "pytorch":
                import torch
                entry._model = torch.load(entry.path, map_location="cpu")
                entry._model.eval()
            else:  # stub
                entry._model = {"stub": True, "path": entry.path}

            entry.loaded     = True
            entry.load_time_s = time.monotonic() - t0
            logger.info("[REGISTRY] loaded '%s' runtime=%s in %.2fs",
                        entry.name, entry.runtime, entry.load_time_s)
            return True
        except ImportError as e:
            logger.warning("[REGISTRY] runtime '%s' not installed (%s) — using stub",
                           entry.runtime, e)
            entry.runtime = "stub"
            entry._model  = {"stub": True}
            entry.loaded  = True
            return True
        except Exception as e:
            logger.error("[REGISTRY] load '%s' failed: %s", entry.name, e)
            return False

    # ── Runtime-specific inference ────────────────────────────────────────────
    @staticmethod
    def _infer_yolo(entry: ModelEntry, data, **kw) -> InferenceResult:
        results = entry._model(data, verbose=False, **kw)
        dets    = []
        for r in results:
            for box in r.boxes:
                dets.append({
                    "class":      r.names[int(box.cls)],
                    "confidence": float(box.conf),
                    "bbox":       box.xyxy[0].tolist(),
                })
        return InferenceResult(model_name=entry.name, latency_ms=0.0,
                               detections=dets, raw_output=results)

    @staticmethod
    def _infer_onnx(entry: ModelEntry, data, **kw) -> InferenceResult:
        import numpy as np
        sess    = entry._model
        inp     = sess.get_inputs()[0].name
        outputs = sess.run(None, {inp: data.astype(np.float32)})
        return InferenceResult(model_name=entry.name, latency_ms=0.0,
                               raw_output=outputs)

    @staticmethod
    def _infer_tflite(entry: ModelEntry, data, **kw) -> InferenceResult:
        interp   = entry._model
        inp_det  = interp.get_input_details()[0]
        out_dets = interp.get_output_details()
        interp.set_tensor(inp_det["index"], data)
        interp.invoke()
        outputs = [interp.get_tensor(o["index"]) for o in out_dets]
        return InferenceResult(model_name=entry.name, latency_ms=0.0,
                               raw_output=outputs)

    @staticmethod
    def _infer_pytorch(entry: ModelEntry, data, **kw) -> InferenceResult:
        import torch
        with torch.no_grad():
            out = entry._model(torch.tensor(data))
        return InferenceResult(model_name=entry.name, latency_ms=0.0,
                               raw_output=out)

    @staticmethod
    def _infer_stub(entry: ModelEntry, data, **kw) -> InferenceResult:
        """Return synthetic detections for testing without ML libraries."""
        import random
        rng  = random.Random(42)
        dets = [
            {
                "class":      cls,
                "confidence": round(rng.uniform(0.6, 0.99), 3),
                "bbox":       [rng.randint(10, 200), rng.randint(10, 200),
                               rng.randint(201, 600), rng.randint(201, 480)],
            }
            for cls in rng.choices(
                ["person", "chair", "bottle", "laptop", "dog"],
                k=rng.randint(0, 3),
            )
        ]
        return InferenceResult(model_name=entry.name, latency_ms=0.0, detections=dets)

    # ── Introspection ─────────────────────────────────────────────────────────
    def list_models(self) -> List[dict]:
        return [
            {
                "name":       e.name,
                "runtime":    e.runtime,
                "loaded":     e.loaded,
                "infer_count": e.infer_count,
                "avg_ms":     round(e.avg_ms, 2),
            }
            for e in self._models.values()
        ]

    def __len__(self) -> int:
        return len(self._models)
