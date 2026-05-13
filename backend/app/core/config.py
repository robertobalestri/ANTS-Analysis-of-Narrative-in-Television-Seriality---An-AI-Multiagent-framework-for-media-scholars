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
    visible: bool = True


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
        visible=False
    ),
    EnvVarSpec(
        name="DATABASE_NAME",
        required=False,
        description="SQLite database file path",
        default="sqlite:///./narrative_storage/narrative.db",
        visible=False
    ),
    EnvVarSpec(
        name="LLM_RETRY_MAX_ATTEMPTS",
        required=False,
        description="Maximum retry attempts for LLM calls",
        default="3",
        visible=False
    ),
    EnvVarSpec(
        name="LLM_RETRY_BASE_DELAY_SECONDS",
        required=False,
        description="Base delay in seconds between LLM retries",
        default="1",
        visible=False
    ),
    EnvVarSpec(
        name="LLM_RETRY_BACKOFF_MULTIPLIER",
        required=False,
        description="Backoff multiplier for LLM retries",
        default="2",
        visible=False
    ),
    EnvVarSpec(
        name="ARC_SIMILARITY_THRESHOLD",
        required=False,
        description="Cosine distance threshold for arc deduplication (0.0-1.0). Lower = stricter matching.",
        default="0.2",
        visible=False
    ),
    EnvVarSpec(
        name="LOG_LEVEL",
        required=False,
        description="Logging level: DEBUG, INFO, WARNING, ERROR, CRITICAL",
        default="INFO",
        visible=False
    ),
    EnvVarSpec(
        name="LOG_FILE",
        required=False,
        description="Log file path",
        default="logs/app.log",
        visible=False
    ),
    EnvVarSpec(
        name="LOG_FORMAT",
        required=False,
        description="Log format: 'text' for colored output, 'json' for structured JSON",
        default="text",
        visible=False
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
    # Load .env file from the backend directory explicitly
    backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    env_path = os.path.join(backend_dir, ".env")
    env_example_path = os.path.join(backend_dir, ".env.example")

    # If .env doesn't exist, try to copy it from .env.example
    if not os.path.exists(env_path) and os.path.exists(env_example_path):
        import shutil
        logger.info(f"Initializing .env from .env.example at {env_path}")
        shutil.copyfile(env_example_path, env_path)

    load_dotenv(dotenv_path=env_path, override=True)

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
def save_env_vars(updates: dict):
    """
    Update the .env file with new values.
    """
    backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    env_path = os.path.join(backend_dir, ".env")
    
    # Read existing lines
    lines = []
    if os.path.exists(env_path):
        with open(env_path, "r") as f:
            lines = f.readlines()
    
    # Update or add variables
    updated_vars = updates.copy()
    new_lines = []
    
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            new_lines.append(line)
            continue
            
        key = stripped.split("=")[0].strip()
        if key in updated_vars:
            new_lines.append(f"{key}={updated_vars.pop(key)}\n")
        else:
            new_lines.append(line)
            
    # Append any new variables that weren't in the file
    for key, value in updated_vars.items():
        new_lines.append(f"{key}={value}\n")
        
    # Write back to file
    with open(env_path, "w") as f:
        f.writelines(new_lines)
    
    return True
