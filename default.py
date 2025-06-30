import xbmcplugin
import xbmcgui
import xbmcaddon
import urllib
import urllib2
import json
import os
import re
import sys
import time
import urlparse
import subprocess

ADDON = xbmcaddon.Addon()
HANDLE = int(sys.argv[1])
GAMES_FILE = ADDON.getSetting('GAMES_FILE')
CACHE_FILE = ADDON.getSetting('CACHE_FILE')
ITEMS_PER_PAGE = int(ADDON.getSetting('PAGINATION'))

# Load entries from cache if available to prevent searching every single game on HLTB on boot.
if os.path.exists(CACHE_FILE):
    with open(CACHE_FILE, 'r') as f:
        cache = json.load(f)
else:
    cache = {}

# Parse games from games.txt, will eventually be replaced by scannning MyPrograms6.db whenever I get that to stop crashing.
def parse_games(file_path):
    games = []
    with open(file_path, 'r') as f:
        for line in f:
            match = re.match(r'"(.*?)",\s*"(.*?)"', line)
            if match:
                games.append((match.group(1), match.group(2)))
    return games

# Search HLTB database via hltb-proxy.fly.dev and make an appropriate match.
def search_hltb(title):
    if title in cache:
        return cache[title]

    try:
        query = urllib.quote(title)
        url = 'https://hltb-proxy.fly.dev/v1/query?title=' + query
        req = urllib2.Request(url, headers={'User-Agent': 'XBMC4Xbox-HLTB-Script'})
        response = urllib2.urlopen(req)
        result = json.loads(response.read())

        if result and isinstance(result, list):
            best_match = None
            # Find the best matching game
            for game in result:
                if game.get('gameName', '').lower() == title.lower():
                    best_match = game
                    break
            if not best_match:
                best_match = result[0]  # Fallback to first result

            beat = best_match.get('beatTime', {})
            def to_hours(seconds):
                return round(seconds / 3600.0, 2) if seconds else 0

            times = {
                'main': to_hours(beat.get('main', {}).get('avgSeconds', 0)),
                'plus': to_hours(beat.get('extra', {}).get('avgSeconds', 0)),
                '100': to_hours(beat.get('completionist', {}).get('avgSeconds', 0)),
                'all': to_hours(beat.get('all', {}).get('avgSeconds', 0)),
                'image': best_match.get('gameImage', '')
            }

            cache[title] = times
            return times
    except Exception as e:
        xbmc.log('HLTB fetch failed for {}: {}'.format(title, str(e)), xbmc.LOGERROR)

    return None

# Format play time 
def format_time(hours):
    if not hours:
        return "N/A"
    h = int(hours)
    m = int(round((hours - h) * 60))
    if m == 0:
        return "%d hours" % h
    if m == 30:
        return "%d 1/2 hours" % h
    return "%d hours, %d minutes" % (h, m)

def parse_query():
    if len(sys.argv) > 2:
        return dict(urlparse.parse_qsl(sys.argv[2][1:]))
    return {}

params = parse_query()

if params.get('action') == 'launch':
    game_path = urllib.unquote(params.get('path'))
    if game_path.lower().endswith('.xbe') and os.path.exists(game_path):
        xbmc.executebuiltin('XBMC.RunXBE("%s")' % game_path)
    else:
        xbmcgui.Dialog().ok('Error', 'Game not found or path invalid.')
    sys.exit()

def build_menu():
    games = parse_games(GAMES_FILE)
    total_games = len(games)

    current_page = int(params.get('page', '1'))

    start_index = (current_page - 1) * ITEMS_PER_PAGE
    end_index = start_index + ITEMS_PER_PAGE

    if current_page > 1:
        prev_url = sys.argv[0] + '?page=' + str(current_page - 1)
        prev_item = xbmcgui.ListItem('<< Previous Page')
        xbmcplugin.addDirectoryItem(handle=HANDLE, url=prev_url, listitem=prev_item, isFolder=True)

    paged_games = games[start_index:end_index]

    for title, path in paged_games:
        times = search_hltb(title)
        thumb = 'https://howlongtobeat.com/games/' + times['image'] if times and times.get('image') else ''

        title_item = xbmcgui.ListItem(title)
        if thumb:
            title_item.setIconImage(thumb)
            title_item.setThumbnailImage(thumb)
        url = sys.argv[0] + '?action=launch&path=' + urllib.quote(path)
        xbmcplugin.addDirectoryItem(handle=HANDLE, url=url, listitem=title_item, isFolder=False)

        if times:
            for label, key in [('Main Story', 'main'), ('Main + Sides', 'plus'), 
                               ('Completionist', '100'), ('All Styles', 'all')]:
                time_item = xbmcgui.ListItem("- {}: {}".format(label, format_time(times[key])))
                if thumb:
                    time_item.setIconImage(thumb)
                    time_item.setThumbnailImage(thumb)
                xbmcplugin.addDirectoryItem(handle=HANDLE, url=url, listitem=time_item, isFolder=False)
        else:
            no_data_item = xbmcgui.ListItem("No HLTB data found")
            xbmcplugin.addDirectoryItem(handle=HANDLE, url=url, listitem=no_data_item, isFolder=False)

    if end_index < total_games:
        next_url = sys.argv[0] + '?page=' + str(current_page + 1)
        next_item = xbmcgui.ListItem('Next Page >>')
        xbmcplugin.addDirectoryItem(handle=HANDLE, url=next_url, listitem=next_item, isFolder=True)

    xbmcplugin.endOfDirectory(HANDLE)

# Save entries from cache if available to prevent searching every single game on HLTB on boot.
def save_cache():
    with open(CACHE_FILE, 'w') as f:
        json.dump(cache, f)

# Run
build_menu()
save_cache()
