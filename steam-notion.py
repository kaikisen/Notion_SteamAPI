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
from bs4 import BeautifulSoup
from urllib import request, parse
from http import cookiejar
import datetime

'''
重要！在下面四行替换为你的信息
'''
STEAM_API_KEY = "此处替换Steam API 密钥，保留双引号"
STEAM_ID = "此处替换17位Steam ID，保留双引号"
notion_api = "此处替换notion_api 密钥，保留双引号"
database_id = "此处替换32位database_id，保留双引号"
#添加不需要的游戏appid
ban_appid =[]
##########################################################################

import requests

def change_tag_to_text(database_id, notion_api):
    url = f"https://api.notion.com/v1/databases/{database_id}"
    headers = {
        "Authorization": f"Bearer {notion_api}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }
    data = {
        "properties": {
            "tag": {
                "rich_text": {}
            }
        }
    }
    response = requests.patch(url, headers=headers, json=data)
    if response.status_code == 200:
        print("成功将 tag 属性改为文字。")
    else:
        print(f"修改失败，状态码: {response.status_code}")
        print("响应内容:", response.text)
        
change_tag_to_text(database_id, notion_api)

def get_json(url):
    try:
        req = urllib.request.Request(url)
        req.add_header('User-Agent', 'Mozilla/5.0')
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode('utf-8'))
    except Exception as e:
        print(f"请求失败: {e}")
        return None

def get_steam_owned_games():
    url = f"https://api.steampowered.com/IPlayerService/GetOwnedGames/v1/?key={STEAM_API_KEY}&steamid={STEAM_ID}&format=json&include_appinfo=true"
    data = get_json(url)
    if not data or not data.get('response', {}).get('games'):
        print("未找到游戏数据，请检查 API 密钥和 SteamID")
        return []
    return data['response']['games']

def get_game_achievements(appid, game_name):
    url = f"https://api.steampowered.com/ISteamUserStats/GetPlayerAchievements/v1/?key={STEAM_API_KEY}&steamid={STEAM_ID}&appid={appid}"
    try:
        data = get_json(url)
        if not data or not data.get('playerstats', {}).get('achievements'):
            print(f"游戏 '{game_name}' 没有成就数据或无法获取完整信息")
            return None
        achievements = data['playerstats']['achievements']
        total = len(achievements)
        unlocked = sum(1 for a in achievements if a.get('achieved', 0) == 1)
        unlocked_times = [a['unlocktime'] for a in achievements if a.get('achieved') == 1 and a.get('unlocktime', 0) > 0]
        earliest_unlock = min(unlocked_times) if unlocked_times else None
        return {
            '成就完成率(%)': round((unlocked / total * 100), 2) if total > 0 else 0,
            '首个成就解锁于': pd.to_datetime(earliest_unlock, unit='s').strftime('%Y-%m-%d') if earliest_unlock else None
        }
    except Exception as e:
        print(f"获取成就时出错: {e}")
        return None

def get_steam_game_info(appid):
    url = f"https://store.steampowered.com/app/{appid}/?l=schinese"
    headers = {"User-Agent": "Mozilla/5.0"}
    cj = cookiejar.CookieJar()
    opener = request.build_opener(request.HTTPCookieProcessor(cj))
    request.install_opener(opener)
    cookies = {
        'birthtime': '568022401',
        'lastagecheckage': '1-January-1990',
        'wants_mature_content': '1'
    }
    cookie_str = "; ".join([f"{key}={value}" for key, value in cookies.items()])
    headers['Cookie'] = cookie_str
    req = request.Request(url, headers=headers)
    try:
        with request.urlopen(req, timeout=10) as response:
            html = response.read().decode('utf-8', errors='replace')
    except Exception as e:
        print(f"请求失败: AppID {appid}, 错误: {e}")
        return None
    soup = BeautifulSoup(html, 'html.parser')
    try:
        title_tag = soup.find('div', {'class': 'apphub_AppName'})
        game_name = title_tag.get_text(strip=True) if title_tag else None
    except:
        game_name = None
    try:
        tags = [tag.get_text(strip=True) for tag in soup.find_all('a', {'class': 'app_tag'})[:8]]
        tags_str = ', '.join(tags)
    except:
        tags_str = None
    return {
        '游戏名称': game_name,
        'tag': tags_str,
        '封面': f'https://steamcdn-a.akamaihd.net/steam/apps/{appid}/header.jpg'
    }

def query_notion_games():
    url = f"https://api.notion.com/v1/databases/{database_id}/query"
    headers = {
        "Authorization": f"Bearer {notion_api}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }

    notion_games = {}  # {appid: last_played_date}
    has_more = True
    next_cursor = None

    while has_more:
        data = {"page_size": 100}
        if next_cursor:
            data["start_cursor"] = next_cursor

        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        result = response.json()

        for page in result["results"]:
            props = page.get("properties", {})
            try:
                # 读取 appid
                appid_prop = props.get("appid", {}).get("rich_text", [])
                if not appid_prop:
                    continue
                appid = appid_prop[0]["plain_text"]

                # 读取 上次游玩时间（可能没有）
                date_info = props.get("上次游玩时间", {}).get("date", {})
                last_played = date_info.get("start") if date_info else None

                notion_games[appid] = last_played
            except Exception as e:
                print(f"跳过一项，读取失败：{e}")

        has_more = result.get("has_more", False)
        next_cursor = result.get("next_cursor")

    print(f"[INFO] 共获取 Notion 中 {len(notion_games)} 项")
    return notion_games

def create_notion_page(game):
    url = "https://api.notion.com/v1/pages"
    headers = {
        "Authorization": f"Bearer {notion_api}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }
    data = {
        "parent": {"database_id": database_id},
        "cover": {"external": {"url": game['封面']}},
        "properties": {
            "游戏名称": {"title": [{"text": {"content": game['游戏名称']}}]},
            "appid": {"rich_text": [{"text": {"content": str(game['appid'])}}]},
            "tag": {"rich_text": [{"text": {"content": game.get('tag', '')}}]},
            "游戏时长/h": {"number": game.get('游戏时长/h', 0)},
            "上次游玩时间": {"date": {"start": game.get('最后游玩时间')}},
            "成就首次解锁于": {"date": {"start": game['首个成就解锁于']} if game.get('首个成就解锁于') else None},
            "成就完成率(%)": {"number": game.get('成就完成率(%)', 0)}
        }
    }
    response = requests.post(url, headers=headers, json=data)
    if not response.ok:
        print(f"导入失败：{game['游戏名称']}，错误：{response.status_code} {response.text}")

def update_notion_page(page_id, game):
    url = f"https://api.notion.com/v1/pages/{page_id}"
    headers = {
        "Authorization": f"Bearer {notion_api}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }
    data = {
        "properties": {
            "游戏时长/h": {"number": game.get('游戏时长/h', 0)},
            "上次游玩时间": {"date": {"start": game.get('最后游玩时间')}},
            "成就首次解锁于": {"date": {"start": game['首个成就解锁于']} if game.get('首个成就解锁于') else None},
            "成就完成率(%)": {"number": game.get('成就完成率(%)', 0)}
        }
    }
    response = requests.patch(url, headers=headers, json=data)
    if not response.ok:
        print(f"更新失败：{game['游戏名称']}，错误：{response.status_code} {response.text}")

def export_games_to_csv(new_games, updated_games):
    if new_games:
        pd.DataFrame(new_games).to_csv("steam_new_games.csv", index=False, encoding='utf_8_sig')
        print("新增游戏已导出到 steam_new_games.csv")
    if updated_games:
        pd.DataFrame(updated_games).to_csv("steam_updated_games.csv", index=False, encoding='utf_8_sig')
        print("更新游戏已导出到 steam_updated_games.csv")

def find_page_id_by_appid(appid):
    url = f"https://api.notion.com/v1/databases/{database_id}/query"
    headers = {
        "Authorization": f"Bearer {notion_api}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }
    data = {
        "filter": {
            "property": "appid",
            "rich_text": {
                "equals": appid
            }
        }
    }
    response = requests.post(url, headers=headers, json=data)
    if response.ok and response.json().get("results"):
        return response.json()["results"][0]["id"]
    return None

def main():
    owned_games = get_steam_owned_games()
    notion_games = query_notion_games()

    new_games = []
    updated_games = []

    for game in owned_games:
        appid = str(game['appid'])
        #print(appid)
        playtime = round(game.get('playtime_forever', 0) / 60, 2)
        last_played = pd.to_datetime(game.get('rtime_last_played', 0), unit='s').strftime('%Y-%m-%d')
        #print('steam '+last_played)
        if game.get('rtime_last_played') == 0:
            continue
        if appid in ban_appid:
            continue
            
        if appid not in notion_games:
            print(f"新增游戏: {game['name']}")
            achievement = get_game_achievements(appid, game['name']) or {}
            meta = get_steam_game_info(appid) or {}
            game_info = {
                'appid': appid,
                '游戏时长/h': playtime,
                '最后游玩时间': last_played,
                '成就完成率(%)': achievement.get('成就完成率(%)'),
                '首个成就解锁于': achievement.get('首个成就解锁于'),
                **meta
            }
            create_notion_page(game_info)
            new_games.append(game_info)
        else:
            existing_last = notion_games.get(appid)
            if existing_last == last_played:
                continue
            print(f"更新游戏: {game['name']}")
            achievement = get_game_achievements(appid, game['name']) or {}
            game_info = {
                'appid': appid,
                '游戏名称': game['name'],
                '游戏时长/h': playtime,
                '最后游玩时间': last_played,
                '成就完成率(%)': achievement.get('成就完成率(%)'),
                '首个成就解锁于': achievement.get('首个成就解锁于')
            }
            page_id = find_page_id_by_appid(appid)
            if page_id:
                update_notion_page(page_id, game_info)
            updated_games.append(game_info)

    export_games_to_csv(new_games, updated_games)
    print("操作完成！")

if __name__ == "__main__":
    main()
