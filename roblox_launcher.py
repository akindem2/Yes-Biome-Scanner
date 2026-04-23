import os
import time
import requests
import re
import urllib.parse

def get_auth_ticket(cookie):
    session = requests.Session()
    session.cookies.set(".ROBLOSECURITY", cookie, domain=".roblox.com")
    
    # We MUST spoof a real browser and declare JSON Content-Type to prevent HTTP 415 errors
    headers = {
        "Referer": "https://www.roblox.com/",
        "Origin": "https://www.roblox.com",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    # 1. Fetch CSRF token by intentionally hitting logout endpoint
    # Send empty JSON {} body to bypass the "UnsupportedMediaType" error
    req = session.post("https://auth.roblox.com/v2/logout", headers=headers, json={})
    csrf_token = req.headers.get("x-csrf-token")
        
    if not csrf_token:
        return None, "AUTH_FAILED: Failed to get CSRF token. Is the cookie valid/expired?"
        
    # 2. Re-send with CSRF token to grab authentication ticket
    headers["x-csrf-token"] = csrf_token
    req = session.post("https://auth.roblox.com/v1/authentication-ticket", headers=headers, json={})
    
    if req.status_code == 200:
        ticket = req.headers.get("rbx-authentication-ticket")
        return ticket, "Success"
    
    if req.status_code in (401, 403):
        return None, f"AUTH_FAILED: HTTP {req.status_code} — cookie is invalid or expired."
    return None, f"HTTP {req.status_code}: {req.text}"
def resolve_share_link(cookie, share_code):
    """Resolves a Roblox share link code into the actual placeId and privateServerLinkCode
    by calling the authenticated sharelinks API."""
    session = requests.Session()
    session.cookies.set(".ROBLOSECURITY", cookie, domain=".roblox.com")
    
    headers = {
        "Referer": "https://www.roblox.com/",
        "Origin": "https://www.roblox.com",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    # 1. Get CSRF token
    req = session.post("https://auth.roblox.com/v2/logout", headers=headers, json={})
    csrf_token = req.headers.get("x-csrf-token")
    if not csrf_token:
        return None, None, "Failed to get CSRF token for share link resolution. Is the cookie valid?"
    
    headers["x-csrf-token"] = csrf_token
    
    # 2. Resolve the share link
    req = session.post(
        "https://apis.roblox.com/sharelinks/v1/resolve-link",
        headers=headers,
        json={"linkId": share_code, "linkType": "Server"}
    )
    
    if req.status_code != 200:
        return None, None, f"Share link resolve failed (HTTP {req.status_code}): {req.text}"
    
    data = req.json()
    ps_data = data.get("privateServerInviteData")
    
    if not ps_data:
        return None, None, "Share link did not resolve to a private server invite."
    
    if ps_data.get("status") != "Valid":
        return None, None, f"Share link status: {ps_data.get('status')} (not Valid). The link may be expired or revoked."
    
    place_id = str(ps_data.get("placeId"))
    link_code = ps_data.get("linkCode")
    
    if not place_id or not link_code:
        return None, None, "Share link resolved but missing placeId or linkCode."
    
    return place_id, link_code, None


def launch_private_server(cookie, pslink):
    place_id = None
    link_code = None
    
    # Format 1: Check for standard Private Server link format
    match_standard = re.search(r"(?:games|place)/(\d+)(?:/.*?)?\?privateServerLinkCode=([a-zA-Z0-9_-]+)", pslink)
    
    if match_standard:
        place_id = match_standard.group(1)
        link_code = match_standard.group(2)
    else:
        # Format 2: Check for the new Share link format (share?code=...)
        # These share codes are NOT privateServerLinkCodes — they must be resolved
        # through Roblox's authenticated sharelinks API to get the real linkCode.
        match_share = re.search(r"share\?code=([a-zA-Z0-9_-]+)", pslink)
        if match_share:
            share_code = match_share.group(1)
            place_id, link_code, error = resolve_share_link(cookie, share_code)
            if error:
                return False, f"Share link resolution failed: {error}"

    if not place_id or not link_code:
        return False, "Could not parse PS link. Make sure it contains 'privateServerLinkCode=' or 'share?code='."
            
    ticket, error_msg = get_auth_ticket(cookie)
    if not ticket:
        return False, error_msg
        
    launch_time = int(time.time() * 1000)
    
    place_launcher_url = f"https://assetgame.roblox.com/game/PlaceLauncher.ashx?request=RequestPrivateGame&placeId={place_id}&linkCode={link_code}"
    encoded_url = urllib.parse.quote(place_launcher_url, safe='')
    
    uri = f"roblox-player:1+launchmode:play+gameinfo:{ticket}+launchtime:{launch_time}+placelauncherurl:{encoded_url}"
    
    try:
        os.startfile(uri)
        return True, "Success"
    except Exception as e:
        return False, f"System Error: {e}"
