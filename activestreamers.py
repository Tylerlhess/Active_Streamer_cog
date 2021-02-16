import psycopg2, logging, re
# discord.py imports
from discord.ext import commands, tasks
# package related imports
from getStreams import get_streams, get_user, get_stream_list, get_gameids
from credentials import DBUSER, DBPASS, DBNAME


logger = logging.getLogger('as_discord')
logger.setLevel(logging.DEBUG)
handler = logging.FileHandler(filename='as_discord.log', encoding='utf-8', mode='w')
handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
logger.addHandler(handler)


def is_admin(ctx):
    logger.info(f'checking {ctx} for admin')
    return True if 'Admin' in [str(x) for x in ctx.message.author.roles] else False

def get_discord_name(streamer_id):
    """Helper function to translate twitch streamer_id to a discord name"""
    conn = psycopg2.connect(f"dbname={DBNAME} user={DBUSER} password={DBPASS}")
    cur = conn.cursor()
    logger.info(f"Translating {streamer_id} to Discord User")
    sql = f"SELECT discord_user FROM twitch_streamers WHERE user_id = {streamer_id};"
    logger.debug(f'{sql} came out right?')
    cur.execute(sql)
    result = cur.fetchone()
    if result[0] is not None:
        logger.info(f"Found {result[0]} as the Discord Username.")
        return result[0]
    else:
        logger.info(f"Did not find a Discord Username")
        return None

def get_streamer_id(discord_name):
    """Helper function to translate discord user names to twitch streamer_id"""
    conn = psycopg2.connect(f"dbname=eternaldecks user={DBUSER} password={DBPASS}")
    cur = conn.cursor()
    logger.info(f"Translating {discord_name} to streamer_id")
    sql = f"SELECT user_id from twitch_streamers where discord_user = '{discord_name}';"
    cur.execute(sql)
    result = cur.fetchall()
    try:
        if result[0] is not None:
            logger.info(f"Found {result[0][0]} as the Discord user_id.")
            return result[0][0]
        else:
            logger.info(f"Did not find a Discord user_id")
            return None
    except Exception as e:
        logger.info(f'{e} exception was thrown')
        return None


class active_streamers(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.record_streamers.start()

    def cog_unload(self):
        self.read_streamers.cancel()

    def get_guilds(self, game=None):
        """Collect a list of guild_id's for either a specific game or return all guilds subscribing to a game by the bot
        to track for user streaming updates."""
        logger.debug(f'call to get guilds for {game}')
        conn = psycopg2.connect(f"dbname={DBNAME} user={DBUSER} password={DBPASS}")
        cur = conn.cursor()
        guilds_sub_to_game = None
        if game:
            sql1 = f"SELECT guild FROM streaming_subscription WHERE game_id = {game}"
            logger.debug(sql1)
            cur.execute(sql1)
            guilds_sub_to_game = [r[0] for r in cur.fetchall()]
            logger.debug(f"Guild games for {game} = {guilds_sub_to_game}")
        sql = f"SELECT guild FROM subscriptions WHERE cog = 'active_streaming';"
        logger.debug(sql)
        cur.execute(sql)
        results = [r[0] for r in cur.fetchall()]
        logger.debug(f'''results is {results} and guilds_sub_to_game is {guilds_sub_to_game}''')
        if guilds_sub_to_game:
            for result in results:
                if result not in guilds_sub_to_game:
                    logger.debug(f"{result} not in guilds_sub_to_game ({guilds_sub_to_game}) removing it.")
                    results.remove(result)
        logger.info(f'''Function get_guilds({game}) returning {results}''')
        return results

    def get_games(self):
        """Get a list of all "twitch" game_id's subbed to in the database"""
        conn = psycopg2.connect(f"dbname={DBNAME}s user={DBUSER} password={DBPASS}")
        cur = conn.cursor()
        sql = f"SELECT distinct(game_id) FROM streaming_subscription;"
        cur.execute(sql)
        results = [r[0] for r in cur.fetchall()]
        logger.info(f'{results} are from get_games')
        return results

    def get_guild_games(self, guild):
        """Gets a list of games for a specific guild"""
        conn = psycopg2.connect(f"dbname={DBNAME}s user={DBUSER} password={DBPASS}")
        cur = conn.cursor()
        sql = f"SELECT game_id FROM streaming_subscription WHERE guild = {guild};"
        cur.execute(sql)
        results = [r[0] for r in cur.fetchall()]
        logger.info(f'{results} are from get_guild_games')
        return results



    @tasks.loop(seconds=60.0)
    async def record_streamers(self):
        """Loop that updates status of streamers currently streaming.
        This can probably be written better to fully utilize async but in its current state having it run serially was
        beneficial for troubleshooting.
        Loop logic.
        Get a list of games you will be tracking.
        For each game, one at a time,
            Use that list to generate a list of all streams
            From that list generate a list of the streamers that are streaming.
            Generate a list of all streams you have in an 'active' state from the database
                sql = SELECT user_id, start_time from streams where is_live = 1 and game_id = {str(game)};
            Go through the active list and remove those that are still streaming from list of all streams.
            If they are not still streaming end their stream record.
            You now have a list of streamers that don't have a stream record so insert those streams and add roles.
            Finally go through all the guilds and clean up users that have the role but are no longer streaming.
        """
        logger.info("")
        logger.info("========> starting record_streamers <==========")
        logger.info("")
        conn = psycopg2.connect(f"dbname={DBNAME}s user={DBUSER} password={DBPASS}")
        #get list of active streams
        logger.info(f"games are {self.get_games()}")
        #get list of open streams from database
        for game in self.get_games():
            streams = get_streams(game_id=[f"{game}"])
            logger.info(f" streams = {streams} for game {game}")
            streamers = [x['user_id'] for x in streams]
            logger.info(f"streamers set to {streamers}")

            logger.info(f"Starting {game} in get_games loop.")
            cur = conn.cursor()
            sql = f"SELECT user_id, start_time from streams where is_live = 1 and game_id = {str(game)};"
            cur.execute(sql)
            result = True
            while result:
                #While Loop 1 Game > Live Users
                result = cur.fetchone()
                logger.info(f" In game {game}, result = {result} ")
                #result[record number][user_id, start_time, end_time, live]
                if result is not None:
                    logger.info(f"Results are currently {result[0]} streamers currently {streamers}")
                    if str(result[0]) in streamers:
                        # Check that User is an active Streamer
                        # update end time to current
                        logger.info(f" Updating {result[0]}'s end_time to still streaming")
                        cur2 = conn.cursor()
                        sql2 = f"UPDATE streams SET end_time = now(), is_live = 1 where user_id = '{result[0]}' and end_time >= now() - interval '5 minutes' and game_id = '{str(game)}';"
                        cur2.execute(sql2)
                        conn.commit()
                        logger.info(sql2)
                        try:
                            logger.info(f"adding {str(result[0])} to active streamers")
                            streamers.remove(str(result[0]))
                            discord_name = get_discord_name(str(result[0]))
                            try:
                                if discord_name is not None:
                                    logger.info(f'{game} game {discord_name}')
                                    logger.info(self.get_guilds(game=game))
                                    for guild in self.get_guilds(game=game):
                                        try:
                                            logger.info(f"guild {guild}")
                                            thisguild = self.bot.get_guild(int(guild))
                                            logger.info(f"Found Guild {thisguild} {type(thisguild)}")
                                            logger.info(f"what does a guild member look like {thisguild.members[0]}")
                                            if len([x for x in thisguild.members if str(x) == discord_name]) > 0:
                                                user = [x for x in thisguild.members if str(x) == discord_name][0]
                                                logger.info(f"Using {user} to add role to.")
                                                logger.info(f"the Guild has roles {[x for x in thisguild.roles if 'Streaming' in str(x)]}")
                                                await user.add_roles([x for x in thisguild.roles if "Streaming" in str(x)][0])
                                                logger.info(f"Added {user} to active streamers role to.")
                                            else:
                                                logger.info(f"{discord_name} not in {thisguild}")
                                        except Exception as e:
                                            logger.info(
                                                f"failed adding {discord_name} to active streamers in {thisguild} Got exception {e}")
                                            pass
                                logger.info(f"done trying to add {str(result[0])} to active streamers")
                            except Exception as e:
                                logger.info(f"failed adding {result[0]} to active streamers Got exception {e}")
                                pass
                        except:
                            logger.info(f"failed removing {result[0]} from {streamers}")
                            pass
                    else:
                        # close out extra streams
                        logger.info(f"Ending {str(result[0])}'s stream as not in  {streamers}")
                        cur2 = conn.cursor()
                        sql2 = f"UPDATE streams SET is_live = 0 where user_id = {result[0]};"
                        cur2.execute(sql2)
                        conn.commit()
                        #try:
                        #    logger.info(f"removing {str(result[0])} from {streamers}")
                        #    streamers.remove(str(result[0]))
                        #except:
                        #    logger.info(f"failed removing {str(result[0])} from {streamers}")
                        #    pass
                        discord_name = get_discord_name(str(result[0]))
                        logger.info(f"discord_name = {discord_name} from get_discord_name({result[0]})")

                        try:
                            logger.info(f" Location Game > Live User > Streamer not in Streams")
                            logger.info(f"Streamer {result[0]}, discord_name {discord_name}")
                            if discord_name is not None:
                                for guild in self.get_guilds(game=game):
                                    try:
                                        thisguild = self.bot.get_guild(guild)
                                        user = [x for x in thisguild.members if str(x) == discord_name][0]
                                        logger.info(f"Using {user} to remove role.")
                                        role = [x for x in thisguild.roles if "Streaming" in str(x)][0]
                                        logger.info(f'====>> Trouble role = {role}')
                                        if len(role) > 0 and str(user) == discord_name:
                                            await user.remove_roles([x for x in thisguild.roles if "Streaming" in str(x)][0])
                                            logger.info(f"Removed {user} from active streamers role to.")

                                    except Exception as e:
                                        logger.info(f"failed removing {discord_name} from active streamers {e}")
                                        pass
                        except Exception as e:
                            logger.info(f"failed removing {discord_name} from active streamers {e}")
                            pass
            for stream in streamers:
                # create and activate missing streams
                logger.info(f"starting stream {stream} for game {game}")
                fake_stream = dict()
                fake_stream['user_id'] = stream
                logger.info(f"recording stream start of {get_user(fake_stream)}")
                cur = conn.cursor()
                sql = f"INSERT INTO streams(user_id, start_time, end_time, is_live, game_id) VALUES ('{str(stream)}', now(), now(), 1, {game}) ;"
                logger.info(sql)
                cur.execute(sql)
                conn.commit()
                discord_name = get_discord_name(str(stream))
                try:
                    if discord_name is not None:
                        for guild in self.get_guilds(game=game):
                            try:
                                logger.info(f'{guild}')
                                thisguild = self.bot.get_guild(guild)
                                logger.info(f"Found Guild {thisguild} {type(thisguild)}")
                                if len([x for x in thisguild.members if str(x) == discord_name]) > 0:
                                    user = [x for x in thisguild.members if str(x) == discord_name][0]
                                    role = [x for x in thisguild.roles if "Streaming" in str(x)]
                                    logger.info(f'====>> Trouble role = {role}')
                                    if len(role) > 0 and str(user) == discord_name :
                                        logger.info(f"Using {user} to add role to.")
                                        await user.add_roles([x for x in thisguild.roles if "Streaming" in str(x)][0])
                                        logger.info(f"Added {user} to active streamers role to.")
                                    else:
                                        logger.info(f"Failed adding {discord_name} to active streamers as no role exists")
                                else:
                                    logger.info(f"{discord_name} is not a member of {thisguild}")
                            except Exception as e:
                                logger.info(f"Failed adding {discord_name} to active streamers of {thisguild} - {e}")
                                pass
                except Exception as e:
                    logger.info(f"failed adding {stream} to active streamers {e}")
                    pass
            for guild in self.get_guilds(game=game):
                logger.info(f" Games > Guild")
                logger.info(f'{guild} is called')
                thisguild = self.bot.get_guild(int(guild))
                games = self.get_guild_games(guild)
                logger.info(f'''{thisguild.id} might be working ''') #{thisguild.roles}''')
                if len([x for x in thisguild.roles if "Streaming" in str(x)]) > 0:
                    role = [x for x in thisguild.roles if "Streaming" in str(x)][0]
                    logger.info(f'''{role} came back ''') #from {thisguild.roles}''')
                    try:
                        logger.info(f"streamers with streaming role {role} in {thisguild} {[x.name for x in thisguild.members if role in x.roles]}")
                    except Exception as e:
                        logger.info(f"{role} failed to be found with {e}")
                        pass
                    try:
                        for streamer in [x for x in thisguild.members if role in x.roles]:
                            logger.info(f'{streamer} is being processed')
                            streamerd = get_streamer_id(str(streamer))
                            logger.info(f"{streamerd} came back from get_streamer_id")
                            sql = f"SELECT streams.user_id, twitch_streamers.discord_user from streams inner join twitch_streamers on twitch_streamers.user_id=streams.user_id where streams.is_live = 1 and streams.game_id in ({', '.join([str(x) for x in games])});"
                            logger.info(f"{sql}")
                            cur.execute(sql)
                            results2_5 = [r for r in cur.fetchall()]
                            logger.info(f'Results of sql {results2_5}')
                            results3 = [r[0] for r in results2_5 ]
                            logger.info(f"results of {sql} - {results3} streamer = {streamerd}")
                            still_streaming = [x for x in results3 if x == streamerd]
                            logger.info(f"reporting {still_streaming}")
                            if len(still_streaming) < 1:
                                try:
                                    user = [x for x in thisguild.members if str(x) == str(streamer)][0]
                                    logger.info(f"roles should be {[x for x in thisguild.roles if 'Streaming' in str(x)]} and streamer has {[x.id for x in streamer.roles]}")
                                    await user.remove_roles([x for x in thisguild.roles if "Streaming" in str(x)][0], atomic=True)
                                    logger.info(f" ==========> Removed {streamer} from active streamers roles see. {streamer.roles}")
                                except Exception as e:
                                    logger.info(f"failed removing {streamer} from active streamers {e}")
                                    pass
                    except Exception as e:
                        logging.info(f"for streamer in failed with - {e}")
                        pass


                else:
                    logger.info(f"{guild} has no Streaming Role Skipping")
                    pass
        conn.commit()
        conn.close()

    @record_streamers.before_loop
    async def before_record_streamers(self):
        await self.bot.wait_until_ready()


    @commands.command(pass_context = True)
    async def register(self, ctx):
        await ctx.channel.send(f"Please send !register_twitch <twitch_user_name> in a DM")
        await ctx.author.send(f"I am trusting the community here to only register their twitch accounts to their discord name. Abuses of this priviledge will be treated harshly. Please report abuses to the Eternal discord moderation team. This command will fail to run on any twitch streamer not in our database load up a stream to resolve this issue. Also spelling counts and twitch api goes off original account name so if you have changed it in the past use the original for this registration. Report any other issues to BadGuyTy")

    @commands.command(pass_context = True)
    async def register_twitch(self, ctx, *args):
        statement = ' '.join(args)
        statement = statement.lower().strip()
        logger.info(f"Got a request for twitch registration for {statement} by {str(ctx.author)}")
        conn = psycopg2.connect(f"dbname={DBNAME}s user={DBUSER} password={DBPASS}")
        cur = conn.cursor()
        sql = f"SELECT * from twitch_streamers where login = '{statement}';"
        cur.execute(sql)
        result = cur.fetchone()
        if result is not None:
            logger.info(f"Found login {statement} for {str(ctx.author)} as {result}")
            cur2 = conn.cursor()
            if result[4] is None:
                sql2 = f"UPDATE twitch_streamers SET discord_user = '{str(ctx.author)}' where login = '{statement}';"
                cur2.execute(sql2)
                logger.info(f"{statement} for {str(ctx.author)} has been set")
                await ctx.author.send(f"{statement} has been registered to you")
            else:
                logger.info(f"Failed setting {statement} for {str(ctx.author)} as already set - {result}")
                await ctx.author.send(f"Sorry {statement} has a discord username of {result[4]} already if this is an error please report it to BadGuyTy")
        else:
            logger.info(f"Failed to find login {statement} for {str(ctx.author)} as {result}")
            await ctx.author.send(f"Failed to find login {statement} in my database. Please check spelling and/or start an Eternal stream again remember this must be your original twitch account login name.")
        conn.commit()

    @commands.command(pass_context = True)
    @commands.check(is_admin)
    async def track_game(self, ctx, *args):
        game = str(*args)
        games = { "eternal": 491403, "Pokemon_Sword_Shield": 497451, "ROOT": 507089}
        logger.info(f'attempting to add {game}')
        if game not in games:
            await ctx.send(f'{game} is not configured at this time please request it from BadGuyTy')
            return
        else:
            conn = psycopg2.connect(f"dbname={DBNAME}s user={DBUSER} password={DBPASS}")
            cur = conn.cursor()
            sql = f"SELECT game_id FROM streaming_subscription where guild = {int(ctx.guild.id)};"
            cur.execute(sql)
            results = [r[0] for r in cur.fetchall()]
            logger.info(f'''track game pre insert results are {results}''')
            if game not in results:
                sql = f"INSERT INTO streaming_subscription(guild, game_id) VALUES ({int(ctx.guild.id)}, {int(games[game])});"

                logger.info(f'attempting to run {sql}')

                cur.execute(sql)
            conn.commit()
            conn.close()
        await ctx.channel.send(f'{game} seems to have added to you games please use !tracked_games to get you current list.')
        await ctx.channel.send(f'Please support BotGuyTy\'s development and operation @ www.patreon.com/badguyty ')


    @commands.command(pass_context = True)
    @commands.check(is_admin)
    async def tracked_games(self, ctx):
        games = {"eternal": 491403, "Pokemon_Sword_Shield": 497451, "ROOT": 507089}
        conn = psycopg2.connect(f"dbname={DBNAME}s user={DBUSER} password={DBPASS}")
        logger.info(f'attempting to get {ctx.guild.id} games')

        cur = conn.cursor()
        sql = f"SELECT game_id FROM streaming_subscription WHERE guild = {int(ctx.guild.id)};"
        cur.execute(sql)
        result = " ".join([key for key, value in games.items() if value in [r[0] for r in cur.fetchall()]])
        await ctx.channel.send(f'{result} ')
        await ctx.channel.send(f'Please support BotGuyTy\'s development and operation @ www.patreon.com/badguyty ')


    @commands.command(pass_context = True)
    async def streams(self, ctx, *args):
        """While not perfect this has been the closest to getting the streamers names
        to show correct. Still has issues with spaces and will show the original
        user name if the twitch user name was updated."""
        escaped_back2 = "\\_"
        logger.info(f'''streams called from {int(ctx.guild.id)}''')
        await ctx.channel.send(re.sub('_GETRID', escaped_back2, get_stream_list(get_gameids(ctx.guild.id))))



