"""
"""
from datetime import datetime
import json
import logging
import os
import pathlib
from pprint import pformat
import sqlite3

from bs4 import BeautifulSoup
from dateutil.parser import parse
import requests


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
logger.addHandler(logging.StreamHandler())


class WargearAPIClient:
    def __init__(self, username, password):
        self.base_url = "http://www.wargear.net"
        self.session = requests.Session()
        self.username = username
        self.password = password

    def authorize_session(self):
        """Loads cookies if present on disk, otherwise authorizes by POST."""
        cookie_jar = pathlib.Path("cookies.json")
        if cookie_jar.is_file():
            logger.debug("Loading cookies from disk.")
            with cookie_jar.open("r") as file_handle:
                cookies = json.load(file_handle)
            self.session.cookies.update(cookies)
            return

        auth_url = self.base_url + "/player/login"
        self.session.get(auth_url)
        login_params = {
            "uid": "",
            "username": f"{self.username}",
            "password": f"{self.password}",
            "cookie_setting": "autologin",
            "loginbtn": "loginbtn",
        }
        logger.debug("Authorizing")
        # The POST response updates the cookiejar
        self.session.post(auth_url, data=login_params)
        cookie_jar = requests.utils.dict_from_cookiejar(self.session.cookies)
        with cookie_jar.open("w") as filehandle:
            json.dump(cookie_jar, filehandle)

    def get_games(self):
        """Call API for game data."""
        self.authorize_session()

        response = self.session.get(
            self.base_url + f"/rest/GetGameList/my",
            params={"viewselector": "Live", "player": self.username},
        )

        return response.json()

    def get_games_info(self):
        """Filter and structure data from API."""

        def iso_format(timestamp):
            return datetime.fromtimestamp(int(timestamp)).isoformat()

        games = []

        for game in self.get_games():
            games.append(
                {
                    "game name": game.get("name"),
                    "message timestamp": iso_format(game.get("msgstamp")),
                    "turn timestamp": iso_format(game.get("turnstamp")),
                    "visit timestamps": [
                        {player: iso_format(visit_ts)}
                        for player, visit_ts in game.get("visitstamps").items()
                    ],
                }
            )

        return games

    def last_site_visit_for(self, player):
        """Parse player profile page for their last site visit time."""
        # TODO: Player profiles don't expose timezone. In order to alert
        # properly, correlate individual game visit to profile timestamp

        response = requests.get(self.base_url + f"/players/info/{player}")

        return parse(
            list(
                BeautifulSoup(response.text, "html.parser")
                .find("table", {"class": "data"})
                .find("td", string="Last Visit")
                .next_siblings
            )[1].text
        )


def get_games_info(username, password):
    wargear_client = WargearAPIClient(username, password)
    games = wargear_client.get_games_info()
    return games


def main():
    username = os.environ["WARGEAR_USER"]
    password = os.environ["WARGEAR_PASS"]

    games = get_games_info(username, password)
    logger.debug(pformat(games))


if __name__ == "__main__":
    main()
