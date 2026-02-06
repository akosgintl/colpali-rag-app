import time
from abc import ABC, abstractmethod
from typing import Any, Protocol

import torch
from loguru import logger


class ColpaliModel(Protocol):
    """Protocol for ColPali models."""

    device: Any

    def __call__(self, **kwargs: Any) -> Any: ...


class ColpaliProcessor(Protocol):
    """Protocol for ColPali processors."""

    def process_queries(self, queries: list[str]) -> Any: ...
    def process_images(self, images: list[Any]) -> Any: ...


class BaseColpaliLoader(ABC):
    """Base class for model loaders."""

    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        self._device = (
            "cuda"
            if torch.cuda.is_available()
            else "mps"
            if torch.backends.mps.is_available()
            else "cpu"
        )
        self._dtype = (
            torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
        )
        self._attn_implementation = self._detect_flash_attention()

    def _detect_flash_attention(self) -> str | None:
        if self._device == "cuda":
            try:
                import flash_attn

                logger.info(
                    "Flash Attention 2 detected | version={}",
                    flash_attn.__version__,
                )
                return "flash_attention_2"
            except ImportError:
                logger.warning(
                    "Flash Attention 2 not available - falling back to default"
                )
        return None

    @property
    def device(self) -> str:
        return self._device

    @abstractmethod
    def load(self) -> tuple[Any, Any]: ...


class ColQwen2_5Loader(BaseColpaliLoader):
    """Loader for ColQwen2.5 models (128-dim output)."""

    def __init__(self, model_name: str) -> None:
        super().__init__(model_name)
        logger.info(
            "ColQwen2_5Loader initialized | model={} | device={} | dtype={} | attn={}",
            model_name,
            self._device,
            self._dtype,
            self._attn_implementation or "default",
        )

    def load(self) -> tuple[Any, Any]:
        from colpali_engine.models import ColQwen2_5, ColQwen2_5_Processor

        logger.info("Loading model and processor")
        start = time.perf_counter()
        model = self._load_model()
        processor = self._load_processor()
        elapsed = time.perf_counter() - start
        logger.success(
            "Model and processor loaded | time_seconds={:.2f}", elapsed
        )
        return model, processor

    def _load_model(self) -> Any:
        from colpali_engine.models import ColQwen2_5

        logger.info(
            "Loading ColQwen2_5 model from pretrained | path={}",
            self.model_name,
        )
        start = time.perf_counter()
        model = ColQwen2_5.from_pretrained(
            pretrained_model_name_or_path=self.model_name,
            device_map=self._device,
            dtype=self._dtype,
            attn_implementation=self._attn_implementation,
        ).eval()
        elapsed = time.perf_counter() - start
        logger.info("Model loaded | time_seconds={:.2f}", elapsed)
        return model

    def _load_processor(self) -> Any:
        from colpali_engine.models import ColQwen2_5_Processor

        logger.info("Loading ColQwen2_5Processor")
        start = time.perf_counter()
        processor = ColQwen2_5_Processor.from_pretrained(
            pretrained_model_name_or_path=self.model_name
        )
        elapsed = time.perf_counter() - start
        logger.info("Processor loaded | time_seconds={:.2f}", elapsed)
        return processor


class ColQwen3Loader(BaseColpaliLoader):
    """Loader for ColQwen3 models (320-dim output)."""

    def __init__(self, model_name: str) -> None:
        super().__init__(model_name)
        logger.info(
            "ColQwen3Loader initialized | model={} | device={} | dtype={} | attn={}",
            model_name,
            self._device,
            self._dtype,
            self._attn_implementation or "default",
        )

    def load(self) -> tuple[Any, Any]:
        from colpali_engine.models import ColQwen3, ColQwen3Processor
        from transformers import AutoConfig

        logger.info("Loading ColQwen3 model and processor")
        start = time.perf_counter()

        # Load and patch config for AWQ models missing rope_scaling
        logger.info(
            "Loading ColQwen3 model from pretrained | path={}",
            self.model_name,
        )
        config = AutoConfig.from_pretrained(self.model_name, trust_remote_code=True)
        
        # Patch missing rope_scaling configuration for Qwen3-VL models
        if hasattr(config, 'text_config') and config.text_config is not None:
            if not hasattr(config.text_config, 'rope_scaling') or config.text_config.rope_scaling is None:
                logger.warning(
                    "rope_scaling missing in config, applying default Qwen3-VL configuration"
                )
                config.text_config.rope_scaling = {
                    "type": "mrope",
                    "mrope_section": [24, 20, 20]  # Default for 4B models
                }
        
        model = ColQwen3.from_pretrained(
            pretrained_model_name_or_path=self.model_name,
            config=config,
            device_map=self._device,
            dtype=self._dtype,
            attn_implementation=self._attn_implementation,
        ).eval()

        logger.info("Loading ColQwen3Processor")
        processor = ColQwen3Processor.from_pretrained(
            pretrained_model_name_or_path=self.model_name
        )

        elapsed = time.perf_counter() - start
        logger.success(
            "ColQwen3 model and processor loaded | time_seconds={:.2f}",
            elapsed,
        )
        return model, processor


class TomoroColQwen3Loader(BaseColpaliLoader):
    """Loader for TomoroAI ColQwen3 models (320-dim output)."""

    def __init__(self, model_name: str) -> None:
        super().__init__(model_name)
        logger.info(
            "TomoroColQwen3Loader initialized | model={} | device={} | dtype={} | attn={}",
            model_name,
            self._device,
            self._dtype,
            self._attn_implementation or "default",
        )

    def load(self) -> tuple[Any, Any]:
        from transformers import AutoModel, AutoProcessor

        logger.info("Loading TomoroAI ColQwen3 model and processor")
        start = time.perf_counter()

        logger.info(
            "Loading TomoroAI model from pretrained | path={}",
            self.model_name,
        )
        model = AutoModel.from_pretrained(
            self.model_name,
            dtype=self._dtype,
            attn_implementation=self._attn_implementation,
            trust_remote_code=True,
            device_map=self._device,
        ).eval()

        logger.info("Loading TomoroAI processor")
        processor = AutoProcessor.from_pretrained(
            self.model_name,
            trust_remote_code=True,
            max_num_visual_tokens=1280,  # TomoroAI default
        )

        elapsed = time.perf_counter() - start
        logger.success(
            "TomoroAI model and processor loaded | time_seconds={:.2f}",
            elapsed,
        )
        return model, processor


def get_loader(model_type: str, model_name: str) -> BaseColpaliLoader:
    """
    Factory function for model loaders.

    Args:
        model_type: One of "colqwen2.5", "colqwen3", "tomoro-colqwen3", or "auto"
        model_name: HuggingFace model name/path

    Returns:
        Appropriate loader instance
    """
    if model_type == "colqwen2.5":
        return ColQwen2_5Loader(model_name)
    elif model_type == "colqwen3":
        return ColQwen3Loader(model_name)
    elif model_type == "tomoro-colqwen3":
        return TomoroColQwen3Loader(model_name)
    elif model_type == "auto":
        # Auto-detect based on model name
        if "tomoro" in model_name.lower():
            logger.info(
                "Auto-detected TomoroAI ColQwen3 model | model_name={}", model_name
            )
            return TomoroColQwen3Loader(model_name)
        elif "colqwen3" in model_name.lower():
            logger.info(
                "Auto-detected ColQwen3 model | model_name={}", model_name
            )
            return ColQwen3Loader(model_name)
        logger.info(
            "Auto-detected ColQwen2.5 model | model_name={}", model_name
        )
        return ColQwen2_5Loader(model_name)
    else:
        raise ValueError(f"Unknown model type: {model_type}")
