# -*- coding: utf-8 -*-
"""
Created on Sun Apr 27 21:25:45 2025

@author: kaikisen
"""

import urllib.request
import urllib.error
import json
import pandas as pd
import time

'''
重要！在下面两行替换为你的 Steam API 密钥和 Steam ID
'''
STEAM_API_KEY = "此处替换Steam API 密钥，保留双引号"
STEAM_ID = "此处替换17位Steam ID，保留双引号"


def get_json(url):
    try:
        req = urllib.request.Request(url) #urllib代替request包 不然会报错
        req.add_header('User-Agent', 'Mozilla/5.0')
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode('utf-8'))
    except Exception as e:
        print(f"请求失败: {e}")
        return None

def get_game_achievements(appid, game_name):
    url = f"https://api.steampowered.com/ISteamUserStats/GetPlayerAchievements/v1/?key={STEAM_API_KEY}&steamid={STEAM_ID}&appid={appid}"
    try:
        data = get_json(url)
        
        if not data or 'playerstats' not in data or 'achievements' not in data['playerstats']:
            print(f"游戏 '{game_name}' 没有成就数据或无法获取完整信息")
            return None
        
        achievements = data['playerstats']['achievements']
        total = len(achievements)
        unlocked = sum(1 for a in achievements if a.get('achieved', 0) == 1)
        
        return {
            '已解锁成就数': unlocked,
            '总成就数': total,
            '成就完成率(%)': round((unlocked / total * 100), 2) if total > 0 else 0
        }
    except urllib.error.HTTPError as e:
        if e.code == 400:
            print(f"游戏 '{game_name}' 不允许访问成就数据，将只记录基础信息")
            return None
        else:
            print(f"获取游戏 '{game_name}' 成就数据时发生错误: {e}")
            return None
    except Exception as e:
        print(f"获取游戏 '{game_name}' 成就数据时发生意外错误: {e}")
        return None

def get_steam_games():
    """获取 Steam 游戏数据（包含成就信息）"""
    print("正在从 Steam 获取数据...")
    url = f"https://api.steampowered.com/IPlayerService/GetOwnedGames/v1/?key={STEAM_API_KEY}&steamid={STEAM_ID}&format=json&include_appinfo=true"
    data = get_json(url)
    
    if not data or not data.get('response', {}).get('games'):
        print("未找到游戏数据，请检查 API 密钥和 SteamID")
        return []

    games = []
    for idx, game in enumerate(data['response']['games'], 1):
        appid = game.get('appid')
        name = game.get('name', '未知游戏')
        print(f"正在处理游戏 {idx}/{len(data['response']['games'])}: {name}")

        game_info = {
            '游戏名称': name,
            'appid':appid,
            '总游玩时间(小时)': round(game.get('playtime_forever', 0) / 60, 2),
            '总游玩时间(分钟)': game.get('playtime_forever', 0),
            '最后游玩时间': pd.to_datetime(game.get('rtime_last_played', 0), unit='s') if game.get('rtime_last_played') else '从未游玩'
        }

        achievements = get_game_achievements(appid, name)
        if achievements:
            game_info.update(achievements)
        else:
            game_info.update({
                '已解锁成就数': 'N/A',
                '总成就数': 'N/A',
                '成就完成率(%)': 'N/A'
            })
        
        games.append(game_info)
        #time.sleep(1)
    
    return games

def export_to_csv(games, filename="steam_games_info.csv"):
    if not games:
        print("没有可导出的数据")
        return
    
    df = pd.DataFrame(games)
    df = df.sort_values(by='总游玩时间(分钟)', ascending=False)
    df.to_csv(filename, index=False, encoding='utf_8_sig')
    print(f"数据已导出到 {filename}")

if __name__ == "__main__":
    games = get_steam_games()
    export_to_csv(games)
    print("操作完成！")