from logging.config import dictConfig
from contextlib import suppress
import logging
import yaml
import random

from .app.settings import get_app_settings
from .app.server import run

# fmt: off
with suppress(ModuleNotFoundError):
    import uvloop; uvloop.install()
# fmt: on

if __name__ == "__main__":

    random.seed()

    # Configure logging
    with open("logging.yaml") as f:
        dictConfig(yaml.safe_load(f))

    settings = get_app_settings()
    logging.info("%-16s %s" % ("ENVIRONMENT", settings.environment.name))
    logging.info("%-16s %s" % ("SERVICE_NAME", settings.environment.service_name))
    logging.info("%-16s %s" % ("SERVICE_VERSION", settings.environment.service_version))
    logging.info("%-16s %s" % ("COMMIT_ID", settings.environment.commit_id))
    logging.info("%-16s %s" % ("BUILD_DATE", settings.environment.build_date))
    logging.info("%-16s %s" % ("COMMIT_DATE", settings.environment.commit_date))
    logging.info("%-16s %s" % ("GIT_BRANCH", settings.environment.git_branch))

    # Run server
    run(settings)
