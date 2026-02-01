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
        -device: str
        -dtype: torch.dtype
        -attn_implementation: str

        +__init__(model_name: str)
        +load() Tuple[ColQwen2_5, Processor]
        +load_model() ColQwen2_5
        +load_processor() ColQwen2_5_Processor
        -_detect_device() str
        -_detect_dtype() torch.dtype
        -_detect_attention() str
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
def __init__(self, model_name: str):
    self.model_name = model_name
    self.device = self._detect_device()
    self.dtype = self._detect_dtype()
    self.attn_implementation = self._detect_attention()
```

**Parameters:**
- `model_name`: HuggingFace model identifier (e.g., `"vidore/colqwen2.5-v0.2"`)

---

### Device Detection

```mermaid
graph TD
    Start["_detect_device()"]

    CUDA{"torch.cuda.is_available()?"}
    MPS{"torch.backends.mps.is_available()?"}

    RetCUDA["return 'cuda'"]
    RetMPS["return 'mps'"]
    RetCPU["return 'cpu'"]

    Start --> CUDA
    CUDA -->|Yes| RetCUDA
    CUDA -->|No| MPS
    MPS -->|Yes| RetMPS
    MPS -->|No| RetCPU
```

```python
def _detect_device(self) -> str:
    if torch.cuda.is_available():
        return "cuda"
    elif torch.backends.mps.is_available():
        return "mps"
    return "cpu"
```

---

### Data Type Detection

```mermaid
graph TD
    Start["_detect_dtype()"]

    IsCUDA{"device == 'cuda'?"}
    SupportsBF16{"cuda.is_bf16_supported()?"}

    RetBF16["return torch.bfloat16"]
    RetFP16["return torch.float16"]

    Start --> IsCUDA
    IsCUDA -->|Yes| SupportsBF16
    SupportsBF16 -->|Yes| RetBF16
    SupportsBF16 -->|No| RetFP16
    IsCUDA -->|No| RetFP16
```

```python
def _detect_dtype(self) -> torch.dtype:
    if self.device == "cuda" and torch.cuda.is_bf16_supported():
        return torch.bfloat16
    return torch.float16
```

---

### Attention Implementation Detection

```mermaid
graph TD
    Start["_detect_attention()"]

    ImportFA{"Can import flash_attn?"}

    RetFA2["return 'flash_attention_2'"]
    RetEager["return 'eager'"]

    Start --> ImportFA
    ImportFA -->|Yes| RetFA2
    ImportFA -->|No| RetEager
```

```python
def _detect_attention(self) -> str:
    try:
        import flash_attn  # noqa: F401
        return "flash_attention_2"
    except ImportError:
        return "eager"
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
    logger.info(f"Loading model: {self.model_name}")
    logger.info(f"Device: {self.device}, dtype: {self.dtype}")
    logger.info(f"Attention: {self.attn_implementation}")

    model = ColQwen2_5.from_pretrained(
        self.model_name,
        torch_dtype=self.dtype,
        device_map=self.device,
        attn_implementation=self.attn_implementation,
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
