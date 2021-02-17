# Active_Streamer_cog
This is a cog that can be used with the discord.py bot library. You add it like any other [cog](https://discordpy.readthedocs.io/en/latest/ext/commands/cogs.html)

Requirements to run in it's current state.
* Python3.6+ 
* Credentials.py file with valid values [More on that here](#Credentials)
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

   
   #Credentials
   You will need 
   * DB credentials
   * Twitch Client ID
   * Twitch Secret ID
   
   You will not need
   * Discord bot Token <= (but it is nice having creds all in one file)
   * OAUTH_TOKEN <= This is a hold over from when this was all Twitch API used
   
   
   #Activation
   Since the cog checks the subscriptions table to see if a guild even has the active_streamers cog you need to first register it there.
   