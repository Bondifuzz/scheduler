from __future__ import annotations
from scheduler.app.pool.pool_manager import PoolManager

from mqtransport import MQApp

from .database.instance import db_init
from .message_queue.instance import MQAppState, mq_init

from aiohttp import web
from .settings import AppSettings

import prometheus_client
import logging

from .external_api.instance import external_api_init


def configure_web_server():

    logger = logging.getLogger("main")
    logger.info("Configuring web server...")

    with open("index.html") as f:
        index_html = f.read()

    async def index(request):
        return web.Response(
            text=index_html,
            content_type="text/html",
            charset="utf-8",
        )

    async def metrics(request):
        return web.Response(
            body=prometheus_client.generate_latest(),
            content_type="text/plain; version=0.0.4;",
        )

    routes = [
        web.get("/", index),
        web.get("/metrics", metrics),
    ]

    app = web.Application()
    app.add_routes(routes)

    logger.info("Configuring web server... OK")
    return app


def run(settings: AppSettings):

    app = configure_web_server()
    logger = logging.getLogger("main")

    async def server_init(app):
        logger.info("Configuring message queue...")
        mq_app: MQApp = await mq_init(settings)
        logger.info("Configuring message queue... OK")

        state: MQAppState = mq_app.state
        state.settings = settings

        state.external_api = await external_api_init(settings)

        logger.info("Configuring database...")
        state.db = await db_init(settings)
        logger.info("Configuring database... OK")

        logger.info("Loading MQ unsent messages...")
        messages = await state.db.unsent_mq.load_unsent_messages()
        mq_app.import_unsent_messages(messages)
        logger.info("Loading MQ unsent messages... OK")

        logger.info("Configuring scheduler loop...")
        state.pool_manager = await PoolManager.create(mq_app)
        logger.info("Configuring scheduler loop... OK")

        await mq_app.start()
        app["mq"] = mq_app
        

    async def server_exit(app):
        mq_app: MQApp = app["mq"]
        state: MQAppState = mq_app.state

        logger.info("Closing message queue...")
        timeout = settings.environment.shutdown_timeout
        await mq_app.shutdown(timeout)
        logger.info("Closing message queue... OK")

        logger.info("Saving MQ unsent messages...")
        messages = mq_app.export_unsent_messages()
        await state.db.unsent_mq.save_unsent_messages(messages)
        logger.info("Saving MQ unsent messages... OK")

        logger.info("Closing external api...")
        await state.external_api.close()
        logger.info("Closing external api... OK")

        logger.info("Closing pool manager...")
        await state.pool_manager.close()
        logger.info("Closing pool manager... OK")

        logger.info("Closing database...")
        await state.db.close()
        logger.info("Closing database... OK")
        

    app.on_startup.append(server_init)
    app.on_shutdown.append(server_exit)

    host = settings.server.host
    port = settings.server.port

    web.run_app(app, host=host, port=port, access_log=None)
