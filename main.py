import json
import os
import heapq
import sys

import requests
import boto3
from botocore.exceptions import ClientError
from dotenv import load_dotenv
from aws_secretsmanager_caching import SecretCache, SecretCacheConfig


#Loads .env file containing secret name and region name for AWS Secret
load_dotenv()

#Fetches AWS secret name and region from .env file
secret_name = os.getenv('SECRET_NAME')
region = os.getenv('AWS_REGION')

#Creates a secrets manager client and session
session = boto3.session.Session()
client = session.client(
    service_name='secretsmanager',
    region_name=region
)
#Cache for secret retrieved from AWS
cache = SecretCache(
    config = SecretCacheConfig(),
    client = client
)

#Fetches the steam API key of the user from AWS Secrets Manager
def get_secret():
    try:
        get_secret_value_response = cache.get_secret_string(secret_name)
    except ClientError as p:
        raise p

    return get_secret_value_response


#Basic method for calling Steam API
def call_steam_api(endpoint: str, params: dict[str, str]):
    x = requests.get(f'http://api.steampowered.com/{endpoint}/', {**params})
    return x

#Returns list of gameIDs of games in account of user with corresponding steam_id number
def get_owned_games(steam_id: int):
    game_request = call_steam_api('IPlayerService/GetOwnedGames/v0001', {
        'key': get_secret(),
        'steamId': steam_id,
        'include_appinfo': 'true',
        'include_played_free_games': 'true',
        'format': 'json'
    })

    if game_request.status_code == 400:
        return ['error']

    owned_games_json = json.loads(game_request.text)

    #Keyerror occurs when response body is empty (no 'games' field)
    #This occurs when the user's account is private or has no games
    try:
        game_list = []
        for key in owned_games_json['response']['games']:
            game_list.append(key['appid'])
        return game_list
    except KeyError:
        return []



#Returns the achievement list of game, with info on which achievements the player has
#If the account is private, an empty list is returned. If the game has no achievements,
#we return a placeholder achievement
def get_player_achievements(game_id: int):
    player_achievement_request = call_steam_api('ISteamUserStats/GetPlayerAchievements/v0001', {
        'appid': game_id,
        'key': get_secret(),
        'steamId': steamId,
        'format': 'json'
    })
    #Achievement information of account can be private, in which case the request is forbidden
    if (player_achievement_request.status_code == 403):
        return []

    response_dict = json.loads(player_achievement_request.text)

    '''
        The following returns an empty dictionary when the game doesn't have achievements.
        We can tell there aren't achievements from two ways (Due to inconsistent responses among games)
            1 - A bad request error is thrown with the message "requested app has no state"
            2 - A successful response is returned, but with no achievements in the content
    '''
    if ((player_achievement_request.status_code == 400 and response_dict['playerstats']['error'] == "Requested app has no stats")
    or 'achievements' not in response_dict['playerstats']):
        return [{'achieved': 0, 'apiname': 'None', 'unlocktime': 0}]

    return json.loads(player_achievement_request.text)['playerstats']['achievements']


#Returns info on global acquisition rates of a specific game's achievements
#Dictionary is returned where key is achievementId, and value is percentage
def get_global_achievement_stats(game_id: int):
    global_achievement_request = call_steam_api('ISteamUserStats/GetGlobalAchievementPercentagesForApp/v0002', {
        'gameId': game_id,
        'format': 'json'
    })

    #Steam returns an error 403 for missing files. This case occurs when we fetch the achievement information of a game without achievements
    if global_achievement_request.status_code == 403:
        return {}

    achievement_list = json.loads(global_achievement_request.text)['achievementpercentages']['achievements']
    achievement_dict = {}
    for achv in achievement_list:
        achievement_dict[achv['name']] = float(achv['percent'])

    return achievement_dict

def get_schemas(game_id: int):
    schema_call = call_steam_api('ISteamUserStats/GetSchemaForGame/v2', {
        'appid': game_id,
        'key': get_secret(),
        'format': 'json'
    })
    return schema_call



steamId = int(input("Enter your steamID\n"))

total_achievement_list = []
games_list = get_owned_games(steamId)

if not games_list:
    print("User account is private or has no games")
    sys.exit(0)
elif games_list[0] == 'error':
    print("steamID entered does not belong to an account")
    sys.exit(0)

for game_id_no in games_list:
    player_achievements = get_player_achievements(int(game_id_no))
    percentages = get_global_achievement_stats(int(game_id_no))

    if not player_achievements:
        print("User achievement information is private")
        sys.exit(0)

    for achievement in player_achievements:
        if achievement['achieved'] == 1:
            name = achievement['apiname']
            total_achievement_list.append({'id':game_id_no, 'name': name, 'percentage':percentages[name]})

#Uses heap queue to find the 10 achievements with the lowest percentage acquisition rate
smallest = heapq.nsmallest(10, total_achievement_list, key= lambda y: y['percentage'])


#Displays rare achievement information
for index, z in enumerate(smallest):
    info_call_dict = json.loads(get_schemas(z['id']).text)

    achievement_schema_dict = info_call_dict['game']['availableGameStats']['achievements']
    matching_achievement = next(item for item in achievement_schema_dict if item['name'] == z['name'])

    # Calls a different api than the call_steam_api method
    # This is call is needed because the call to get the game's schema has inconsistent responses for the game's title
    game_title = json.loads(requests.get(f'https://store.steampowered.com/api/appdetails?appids={z["id"]}').text)[str(z['id'])]['data']['name']

    print(f"{index+1} - [{game_title}] {matching_achievement['displayName']} (%{round(z['percentage'], 2)})")

    try:
        print(matching_achievement['description'])
    except KeyError as e:                   #For hidden achievements, a description of it is unavailable
        print("Hidden achievement, description unavailable")
    print('\n')