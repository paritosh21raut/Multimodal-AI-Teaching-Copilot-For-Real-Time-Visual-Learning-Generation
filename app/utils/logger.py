from pathlib import Path
from loguru import logger


# Create logs folder if it doesn't exist
Path("logs").mkdir(exist_ok=True)

# Remove default logger
logger.remove()

# Log to terminal
logger.add(
    sink=lambda msg: print(msg, end=""),
    level="INFO",
    colorize=True,
)

# Log to file
logger.add(
    "logs/project.log",
    rotation="5 MB",
    retention="10 days",
    level="INFO",
)

app_logger = logger