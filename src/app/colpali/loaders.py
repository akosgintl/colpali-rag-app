import time

import torch
from colpali_engine.models import ColQwen2_5, ColQwen2_5_Processor
from loguru import logger
from transformers.utils.import_utils import is_flash_attn_2_available


class ColQwen2_5Loader:
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
        self._attn_implementation = (
            "flash_attention_2" if is_flash_attn_2_available() else None
        )
        logger.info(
            "ColQwen2_5Loader initialized | model={} | device={} | dtype={} | attn={}",
            model_name,
            self._device,
            self._dtype,
            self._attn_implementation or "default",
        )

    def load(self) -> tuple[ColQwen2_5, ColQwen2_5_Processor]:
        logger.info("Loading model and processor")
        start = time.perf_counter()
        model = self.load_model()
        processor = self.load_processor()
        elapsed = time.perf_counter() - start
        logger.success(
            "Model and processor loaded | time_seconds={:.2f}", elapsed
        )
        return model, processor

    def load_model(self) -> ColQwen2_5:
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

    def load_processor(self) -> ColQwen2_5_Processor:
        logger.info("Loading ColQwen2_5Processor")
        start = time.perf_counter()
        processor = ColQwen2_5_Processor.from_pretrained(
            pretrained_model_name_or_path=self.model_name
        )
        assert isinstance(processor, ColQwen2_5_Processor)
        elapsed = time.perf_counter() - start
        logger.info("Processor loaded | time_seconds={:.2f}", elapsed)
        return processor
