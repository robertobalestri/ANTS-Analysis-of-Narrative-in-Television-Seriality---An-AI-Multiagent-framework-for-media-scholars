"""Environment variable validation at startup."""
import logging
import os
import sys
from dataclasses import dataclass
from typing import List, Optional

from dotenv import load_dotenv

logger = logging.getLogger(__name__)


@dataclass
class EnvVarSpec:
    """Specification for an environment variable."""
    name: str
    required: bool = True
    description: str = ""
    default: Optional[str] = None


# Required environment variables for the application
REQUIRED_ENV_VARS: List[EnvVarSpec] = [
    EnvVarSpec(
        name="LLM_API_KEY",
        required=True,
        description="API key for the LLM provider (e.g., OpenAI, Azure OpenAI)",
    ),
    EnvVarSpec(
        name="LLM_API_BASE",
        required=True,
        description="API base URL for the LLM provider",
    ),
    EnvVarSpec(
        name="LLM_MODEL",
        required=True,
        description="Model name for LLM operations",
    ),
    EnvVarSpec(
        name="EMBED_API_KEY",
        required=True,
        description="API key for the embedding provider",
    ),
    EnvVarSpec(
        name="EMBED_API_BASE",
        required=True,
        description="API base URL for the embedding provider",
    ),
    EnvVarSpec(
        name="EMBED_MODEL",
        required=False,
        description="Embedding model name",
        default="embed-v-4-0",
    ),
    EnvVarSpec(
        name="LLM_PROVIDER",
        required=False,
        description="LLM provider name (e.g., 'openai', 'azure')",
        default="",
    ),
    EnvVarSpec(
        name="EMBED_PROVIDER",
        required=False,
        description="Embedding provider name",
        default="",
    ),
    EnvVarSpec(
        name="LLM_API_VERSION",
        required=False,
        description="API version for the LLM provider (mainly for Azure)",
        default=None,
    ),
    EnvVarSpec(
        name="EMBED_API_VERSION",
        required=False,
        description="API version for the embedding provider",
        default=None,
    ),
    EnvVarSpec(
        name="PERSIST_DIRECTORY",
        required=False,
        description="Directory for ChromaDB vector store persistence",
        default="./narrative_storage/chroma_db",
    ),
    EnvVarSpec(
        name="DATABASE_NAME",
        required=False,
        description="SQLite database file path",
        default="sqlite:///./narrative_storage/narrative.db",
    ),
    EnvVarSpec(
        name="LLM_RETRY_MAX_ATTEMPTS",
        required=False,
        description="Maximum retry attempts for LLM calls",
        default="3",
    ),
    EnvVarSpec(
        name="LLM_RETRY_BASE_DELAY_SECONDS",
        required=False,
        description="Base delay in seconds between LLM retries",
        default="1",
    ),
    EnvVarSpec(
        name="LLM_RETRY_BACKOFF_MULTIPLIER",
        required=False,
        description="Backoff multiplier for LLM retries",
        default="2",
    ),
    EnvVarSpec(
        name="ARC_SIMILARITY_THRESHOLD",
        required=False,
        description="Cosine distance threshold for arc deduplication (0.0-1.0). Lower = stricter matching.",
        default="0.35",
    ),
    EnvVarSpec(
        name="LOG_LEVEL",
        required=False,
        description="Logging level: DEBUG, INFO, WARNING, ERROR, CRITICAL",
        default="DEBUG",
    ),
    EnvVarSpec(
        name="LOG_FILE",
        required=False,
        description="Log file path",
        default="api.log",
    ),
    EnvVarSpec(
        name="LOG_FORMAT",
        required=False,
        description="Log format: 'text' for colored output, 'json' for structured JSON",
        default="text",
    ),
]


def validate_env_vars() -> List[str]:
    """
    Validate that all required environment variables are set.

    Returns:
        List of error messages for missing required variables.
    """
    errors = []
    warnings = []

    for spec in REQUIRED_ENV_VARS:
        value = os.getenv(spec.name)

        if value is None or value.strip() == "":
            if spec.required:
                errors.append(
                    f"Missing required environment variable: {spec.name}\n"
                    f"  Description: {spec.description}"
                )
            elif spec.default is not None:
                warnings.append(
                    f"Optional environment variable {spec.name} not set, "
                    f"using default: {spec.description}"
                )

    return errors, warnings


def check_env_or_exit():
    """
    Validate environment variables and exit with clear error message if any required ones are missing.
    Call this at application startup before any services are initialized.
    """
    # Load .env file first
    load_dotenv(override=True)

    errors, warnings = validate_env_vars()

    # Log warnings
    for warning in warnings:
        logger.warning(warning)

    # Log errors and exit if any required vars are missing
    if errors:
        error_lines = [
            "",
            "=" * 60,
            "ENVIRONMENT VARIABLE VALIDATION FAILED",
            "=" * 60,
            "",
            "The following required environment variables are missing:",
            "",
        ]
        for i, error in enumerate(errors, 1):
            error_lines.append(f"  {i}. {error}")
        error_lines.extend([
            "",
            "Please set these variables in your .env file or environment.",
            "See .env.example for a template.",
            "",
            "=" * 60,
        ])

        error_message = "\n".join(error_lines)
        logger.error(error_message)
        print(error_message, file=sys.stderr)
        sys.exit(1)

    logger.info("Environment variable validation passed")


def get_env_summary() -> str:
    """Get a summary of current environment variable configuration."""
    lines = ["Environment Configuration:"]

    for spec in REQUIRED_ENV_VARS:
        value = os.getenv(spec.name)
        if value is not None:
            # Mask API keys for security
            if "API_KEY" in spec.name and value:
                display_value = value[:4] + "..." + value[-4:] if len(value) > 8 else "****"
            else:
                display_value = value
            lines.append(f"  {spec.name} = {display_value}")
        elif spec.default is not None:
            lines.append(f"  {spec.name} = {spec.default} (default)")
        else:
            lines.append(f"  {spec.name} = <not set>")

    return "\n".join(lines)
