"""
Copyright 2021-present Tylerlhess

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""

import requests, psycopg2, re. logging, datetime
from credentials import DBUSER, DBPASS, DBNAME, OAUTH_TOKEN, TWITCH_CLIENT_ID, TWITCH_SECRET

logger = logging.getLogger('as_discord')
logger.setLevel(logging.DEBUG)
handler = logging.FileHandler(filename='as_discord.log', encoding='utf-8', mode='w')
handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
logger.addHandler(handler)

oauth_token = OAUTH_TOKEN

AUTH = {"twitch_oauth_token": "", "token_ttl": datetime.datetime.now(), "client_id": TWITCH_CLIENT_ID, "secret": TWITCH_SECRET}


def get_twitch_oauth_token(AUTH):
    logger.info(f"Got an Auth request old data was ")
    url = f"https://id.twitch.tv/oauth2/token?client_id={AUTH['client_id']}&client_secret={AUTH['secret']}&grant_type=client_credentials"
    r = requests.post(url, timeout=15)
    r.raise_for_status()
    jsonResponse = r.json()
    AUTH["twitch_oauth_token"] = jsonResponse["access_token"]
    AUTH["token_ttl"] = datetime.datetime.now() + datetime.timedelta(seconds=jsonResponse["expires_in"])
    return AUTH


def check_auth(AUTH):
    if AUTH['token_ttl'] > datetime.datetime.now() + datetime.timedelta(seconds=60):
        return True
    else:
        get_twitch_oauth_token(AUTH)
        return True
    return False


def get_headers(AUTH):
    if check_auth(AUTH):
        headers = {}
        headers['Client-ID'] = AUTH['client_id']
        headers['Authorization'] = f"Bearer {AUTH['twitch_oauth_token']}"
        return headers
    else:
        return None


def get_user(stream):
    user_id = stream['user_id']
    conn = psycopg2.connect(f"dbname={DBNAME} user={DBUSER} password={DBPASS}")
    cur = conn.cursor()
    sql = f"SELECT display_name FROM twitch_streamers WHERE user_id = '{user_id}';"
    logger.info(sql)

    cur.execute(sql)
    results = cur.fetchall()
    cur.close()
    conn.close()
    if len(results) < 1:
        #pull from api
        username = user_id_to_name(user_id)
        return username
    else:
        username = str(results[0][0])
        return username


def user_id_to_name(user_id):
    url = f'https://api.twitch.tv/helix/users?id={user_id}'
    info = None
    r = requests.get(url, headers=get_headers(AUTH), timeout = 15)
    r.raise_for_status()
    info = r.json()
    user = user_id
    login = info['data'][0]['login']
    display_name = info['data'][0]['display_name']
    conn = psycopg2.connect(f"dbname={DBNAME} user={DBUSER} password={DBPASS}")
    cur = conn.cursor()
    sql = f"""INSERT into twitch_streamers(user_id, login, display_name, stream_url) VALUES('{user}', '{login}', '{display_name}', 'https://twitch.tv/{display_name}');"""
    logger.info(sql)

    cur.execute(sql)
    conn.commit()
    cur.close()
    conn.close()
    return display_name


def get_streams(game_id=None):
    if not game_id:
        logger.info(f'called get_streams with {game_id}')

        conn = psycopg2.connect(f"dbname={DBNAME} user={DBUSER} password={DBPASS}")
        cur = conn.cursor()
        sql = f"SELECT distinct(game_id) FROM streaming_subscription;"
        cur.execute(sql)
        game_id = [r[0] for r in cur.fetchall()]
    logger.info(f'called get_streams with {[game for game in game_id]} trying ')
    final = []
    for game in game_id:
        logger.info(f'https://api.twitch.tv/helix/streams?game_id={game}')
        url = f'https://api.twitch.tv/helix/streams?game_id={game}'
        info = None
        r = requests.get(url, headers=get_headers(AUTH), timeout=15)
        r.raise_for_status()
        info = r.json()
        logger.info(f'{info["data"]}')
        final = final + info["data"]
        logger.info(final)
    return final


def get_stream_list(game_id=None):
    """Escaping in fstrings is tedious"""
    logger.info(f"called get_stream_list {game_id}")
    escaped_back_3 = "_"
    return '\r\n'.join([f"`{get_user(stream)}, is streaming for {stream['viewer_count']} ` <https://twitch.tv/{re.sub(' ', escaped_back_3, get_user(stream))}>" for stream in get_streams(game_id=game_id)])

def get_gameids(guild):
    logger.info(f"In get_gameids with {guild}")
    conn = psycopg2.connect(f"dbname={DBNAME} user={DBUSER} password={DBPASS}")
    cur = conn.cursor()
    sql = f"SELECT distinct(game_id) FROM streaming_subscription WHERE guild = '{guild}';"
    cur.execute(sql)
    game_id = [r[0] for r in cur.fetchall()]
    logger.info(f"{sql} returned {game_id} for guild {guild}")

    return game_id
