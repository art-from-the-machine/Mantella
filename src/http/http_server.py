import logging
import click
from flask import Flask
from src.http.routes.routeable import routeable

class http_server:
    """A simple http server using Flask. Can be started using different routes.
    """
    def __init__(self) -> None:
        self.__flask = Flask(__name__)

        ### Deactivate the logging to console by Flask
        log = logging.getLogger('werkzeug')
        log.setLevel(logging.ERROR)

        def secho(text, file=None, nl=None, err=None, color=None, **styles):
            pass

        def echo(text, file=None, nl=None, err=None, color=None, **styles):
            pass

        click.echo = echo
        click.secho = secho
        ### End of deactivate logging

    def start(self, port: int, routes: list[routeable], show_debug: bool = False):
        """Starts the server and sets up the provided routes

        Args:
            routes (list[routeable]): The list of routes to start
            show_debug (bool, optional): should debug output be shown
        """
        for route in routes:
            route.add_route_to_server(self.__flask)
    
        self.__flask.run(port=port, debug=False)