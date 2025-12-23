import logging
import click
from fastapi import FastAPI
import uvicorn
from src.http.routes.routeable import routeable
from src import utils

logger = utils.get_logger()


class http_server:
    """A simple http server using FastAPI. Can be started using different routes.
    """
    def __init__(self) -> None:
        self.__app = FastAPI()

        ### Deactivate the logging to console by FastAPI
        log = logging.getLogger('werkzeug')
        log.setLevel(logging.ERROR)

        def secho(text, file=None, nl=None, err=None, color=None, **styles):
            pass

        def echo(text, file=None, nl=None, err=None, color=None, **styles):
            pass

        click.echo = echo
        click.secho = secho
        ### End of deactivate logging

    @property
    def app(self) -> FastAPI:
        return self.__app

    def _setup_routes(self, routes: list[routeable]):
        """Sets up the provided server routes
        
        Args:
            routes (list[routeable]): The list of routes to set up
        """
        for route in routes:
            route.add_route_to_server(self.__app)
        return self.__app

    def start(self, port: int, routes: list[routeable], play_startup_sound: bool, show_debug: bool = False):
        """Starts the server and sets up the provided routes

        Args:
            routes (list[routeable]): The list of routes to start
            show_debug (bool, optional): should debug output be shown
        """
        self._setup_routes(routes)

        if play_startup_sound:
            utils.play_mantella_ready_sound()
        
        logger.log(24, '\nConversations not starting when you select an NPC? See here:')
        logger.log(25, 'https://art-from-the-machine.github.io/Mantella/pages/issues_qna')
        logger.log(24, '\nWaiting for player to select an NPC...')
    
        uvicorn.run(self.__app, port=port)
