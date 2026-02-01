# ColPali Module

The ColPali module handles loading and configuration of the ColQwen 2.5 vision-language model.

## Module Structure

```
src/app/colpali/
├── __init__.py
└── loaders.py    # Model loading logic
```

## Overview

```mermaid
graph TD
    subgraph ColPali["ColPali Module"]
        Loader["ColQwen2_5Loader"]
    end

    subgraph HuggingFace["HuggingFace Hub"]
        Model["vidore/colqwen2.5-v0.2"]
    end

    subgraph Hardware["Hardware Detection"]
        CUDA["CUDA"]
        MPS["MPS (Apple)"]
        CPU["CPU"]
    end

    subgraph Output["Loaded Components"]
        ColQwen["ColQwen2_5"]
        Processor["ColQwen2_5_Processor"]
    end

    Loader --> HuggingFace
    Loader --> Hardware
    Loader --> Output
```

---

## loaders.py

### ColQwen2_5Loader Class

Main class for loading the ColQwen 2.5 model with automatic hardware detection.

```mermaid
classDiagram
    class ColQwen2_5Loader {
        -model_name: str
        -_device: str
        -_dtype: torch.dtype
        -_attn_implementation: str | None

        +__init__(model_name: str)
        +load() Tuple[ColQwen2_5, Processor]
        +load_model() ColQwen2_5
        +load_processor() ColQwen2_5_Processor
    }

    class ColQwen2_5 {
        +forward(**kwargs) Tensor
        +eval()
        +to(device)
    }

    class ColQwen2_5_Processor {
        +process_images(images) BatchFeature
        +process_queries(queries) BatchFeature
    }

    ColQwen2_5Loader --> ColQwen2_5 : creates
    ColQwen2_5Loader --> ColQwen2_5_Processor : creates
```

### Constructor

```python
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
```

**Parameters:**
- `model_name`: HuggingFace model identifier (e.g., `"vidore/colqwen2.5-v0.2"`)

---

### Device Detection

```mermaid
graph TD
    Start["Device Detection"]

    CUDA{"torch.cuda.is_available()?"}
    MPS{"torch.backends.mps.is_available()?"}

    RetCUDA["'cuda'"]
    RetMPS["'mps'"]
    RetCPU["'cpu'"]

    Start --> CUDA
    CUDA -->|Yes| RetCUDA
    CUDA -->|No| MPS
    MPS -->|Yes| RetMPS
    MPS -->|No| RetCPU
```

```python
self._device = (
    "cuda"
    if torch.cuda.is_available()
    else "mps"
    if torch.backends.mps.is_available()
    else "cpu"
)
```

---

### Data Type Detection

```mermaid
graph TD
    Start["Data Type Detection"]

    SupportsBF16{"torch.cuda.is_bf16_supported()?"}

    RetBF16["torch.bfloat16"]
    RetFP16["torch.float16"]

    Start --> SupportsBF16
    SupportsBF16 -->|Yes| RetBF16
    SupportsBF16 -->|No| RetFP16
```

```python
self._dtype = (
    torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
)
```

---

### Attention Implementation Detection

```mermaid
graph TD
    Start["Attention Detection"]

    CheckFA{"is_flash_attn_2_available()?"}

    RetFA2["return 'flash_attention_2'"]
    RetNone["return None (default)"]

    Start --> CheckFA
    CheckFA -->|Yes| RetFA2
    CheckFA -->|No| RetNone
```

```python
from transformers.utils.import_utils import is_flash_attn_2_available

self._attn_implementation = (
    "flash_attention_2" if is_flash_attn_2_available() else None
)
```

---

### Load Methods

#### `load() -> Tuple[ColQwen2_5, ColQwen2_5_Processor]`

Loads both model and processor.

```python
def load(self) -> tuple[ColQwen2_5, ColQwen2_5_Processor]:
    return self.load_model(), self.load_processor()
```

---

#### `load_model() -> ColQwen2_5`

Loads the ColQwen 2.5 model from HuggingFace.

```python
def load_model(self) -> ColQwen2_5:
    model = ColQwen2_5.from_pretrained(
        pretrained_model_name_or_path=self.model_name,
        device_map=self._device,
        dtype=self._dtype,
        attn_implementation=self._attn_implementation,
    ).eval()
    return model
```

**Returns:** Loaded model in evaluation mode

---

#### `load_processor() -> ColQwen2_5_Processor`

Loads the processor for image/text preprocessing.

```python
def load_processor(self) -> ColQwen2_5_Processor:
    return ColQwen2_5_Processor.from_pretrained(self.model_name)
```

**Returns:** Processor instance

---

## Model Specifications

### ColQwen 2.5

| Property | Value |
|----------|-------|
| Model ID | `vidore/colqwen2.5-v0.2` |
| Output Dimension | 128 |
| Multi-vector | Yes |
| Vision Encoder | Qwen2-VL |

### Processing Pipeline

```mermaid
sequenceDiagram
    participant Input as Input
    participant Processor
    participant Model
    participant Output as Output

    rect rgb(240, 248, 255)
        Note over Input,Processor: Image Processing
        Input->>Processor: PIL.Image[]
        Processor->>Processor: Resize, normalize
        Processor-->>Model: BatchFeature (pixel_values)
    end

    rect rgb(255, 248, 240)
        Note over Input,Processor: Query Processing
        Input->>Processor: query_text
        Processor->>Processor: Tokenize
        Processor-->>Model: BatchFeature (input_ids)
    end

    rect rgb(240, 255, 240)
        Note over Model,Output: Forward Pass
        Model->>Model: Forward with inference_mode
        Model-->>Output: embeddings (N x 128)
    end
```

---

## Usage Example

```python
from src.app.colpali.loaders import ColQwen2_5Loader
from PIL import Image
import torch

# Load model and processor
loader = ColQwen2_5Loader("vidore/colqwen2.5-v0.2")
model, processor = loader.load()

# Process images
images = [Image.open("page1.jpg"), Image.open("page2.jpg")]
batch = processor.process_images(images)
batch = {k: v.to(model.device) for k, v in batch.items()}

# Generate embeddings
with torch.inference_mode():
    embeddings = model(**batch)

# embeddings shape: [batch_size, num_patches, 128]
```

---

## Hardware Requirements

| Configuration | Memory (Model Only) | Recommended |
|--------------|---------------------|-------------|
| CPU + FP16 | ~4 GB | Development |
| CUDA + BF16 | ~4 GB VRAM | Production |
| MPS + FP16 | ~4 GB | Mac development |

---

## Performance Tips

1. **Use CUDA if available**: Significantly faster inference
2. **Enable Flash Attention 2**: Reduces memory and improves speed
3. **Use bfloat16**: Better numerical stability on supported GPUs
4. **Batch processing**: Process multiple images together when possible
5. **inference_mode**: Always use `torch.inference_mode()` for inference
