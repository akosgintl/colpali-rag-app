from pathlib import Path

from loguru import logger


def read_prompt_from_plain_file(filename: str) -> str:
    filepath = Path(filename)
    logger.info("Reading prompt file | path={}", filepath)
    try:
        with filepath.open(mode="r") as prompt:
            content = prompt.read()
            logger.info(
                "Prompt loaded | path={} | length={}", filepath, len(content)
            )
            return content
    except FileNotFoundError:
        logger.error("Prompt file not found | path={}", filepath)
        raise
    except Exception as e:
        logger.error(
            "Failed to read prompt file | path={} | error={}", filepath, str(e)
        )
        raise
