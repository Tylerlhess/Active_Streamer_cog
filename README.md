# Active_Streamer_cog
This is a cog that can be used with the discord.py bot library. You add it like any other [cog](https://discordpy.readthedocs.io/en/latest/ext/commands/cogs.html)

Requirements to run in it's current state.
* Python3.6+ 
* Credentials.py file with valid values [More on that here](# Credentials)
* Postgres database w/ following tables

Table "public.streaming_subscription"

|Column|Type|Modifiers|
|------|----|-----------|
|guild|bigint||
|game_id|integer|||

   Table "public.streams"

|Column|Type|Modifiers|
|------|----|---------|
|user_id|bigint|notnull|
|start_time|timestampwithouttimezone|notnull|
|end_time|timestampwithouttimezone||
|is_live|integer||
|game_id|integer|||
 
        Indexes:
            "streams_pkey" PRIMARY KEY, btree (user_id, start_time)
        Foreign-key constraints:
            "streams_user_id_fkey" FOREIGN KEY (user_id) REFERENCES twitch_streamers(user_id) ON UPDATE CASCADE ON DELETE CASCADE
     
Table "public.subscriptions"

|Column|Type|Modifiers|
|-----|----|---------|
|cog|charactervarying(255)||
|guild|bigint|||


Table "public.twitch_streamers"
          
|Column|Type|Modifiers|
|------|----|---------|
|user_id|bigint|not null|
|login|character varying(255)|not null|
|display_name|character varying(255)|not null|
|stream_url|character varying(255)||
|discord_user|character varying(255)|||
             
        Indexes:
            "twitch_streamers_pkey" PRIMARY KEY, btree (user_id)
            "twitch_streamers_stream_url_key" UNIQUE CONSTRAINT, btree (stream_url)
        Referenced by:
            TABLE "streams" CONSTRAINT "streams_user_id_fkey" FOREIGN KEY (user_id) REFERENCES twitch_streamers(user_id) ON UPDATE CASCADE ON DELETE CASCADE

   
   # Credentials
   You will need 
   * DB credentials
   * Twitch Client ID
   * Twitch Secret ID
   
   You will not need
   * Discord bot Token <= (but it is nice having creds all in one file)
   * OAUTH_TOKEN <= This is a hold over from when this was all Twitch API used
   
   
   # Activation
   > This sectionassumes the use of "!" as the bot command marker
 
   Since the cog checks the subscriptions table to see if a guild even has the active_streamers cog you need to first register it there.
   1. First you will need to make sure you have an "Admin" role in your discord and that this role is only given to those you want to manage this plugin. This is configurable in the is_admin function at the top of the activestreamers.py for now I may move it to be in credentials.py in the future.
   2. The discord must add the active streamers cog to the subscriptions. An admin must run the following command.   
        
          !add_cog active_streaming
    
   3. This can be confirmed as having been done by using the list cogs command

          !list_cogs
     
   4. The game must then be tracked by the discord. I am open to better terminology this is the best I could manage.
   
          !track_game <game_name>
          
      This command is in my TODO list of things that needs help. 
      
   5. The list of currently tracked games can be checked with
   
          !tracked_games
          
   6. Have interested parties register their Discord names with the bot.
           
           !register
           
      will will give instructions on how to register with the bot and 
      
           !register_twitch <twitch_username>
           
      will actually assign that username to the twitch userId.
      
      This is also in my TODO list to be addressed. 
         
   
   # Future Development
   * I would like to pull out the DB auth into its own function and have the cursor passed to the sql functions as needed. It would also get a cursor if none were passed.
   * I would like to setup the database automatically if the tables don't exist.
   * I would like to add an auto db creation of an sqlite3 db if no database credentials are present.
   * Update tracked_games function. 

        * Currently it is a dictionary directly in the function. 
        * This needs to be moved to a json config file
        * Have ability to discover games on twitch through a name search. 
            * Each game has it's unique gameId on twitch 
            * finding that is not easy or intuitive. 
            * The currently listed games were requested.  
            * A locally stored json configuration file with the option of having that file updated by the track games function would allow the other functions that utilize this to just pull directly from the file while allowing the flexibility to edit it locally. It would also need to be added to the .gitignore so it isn't wiped by updates.      
        
   * Update user registration. 
        
        * Have this based on the Twitch/Discord integration. 
        * Use a uuid from discord for the user so in the event the user changes their username's tail with Nitro from the random 4 digits it will stick to the user where it presently does not
        * Failing this allow users to petition username updates.
        
   * Automated Update feature alerting admins to available updates to the repo
   * System to alert admins to requests related to the cog's operation or perceived defects. 