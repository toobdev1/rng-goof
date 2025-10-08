# --- GITHUB STATS FUNCTIONS (safe) ---
async def load_stats():
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{STATS_PATH}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=GITHUB_HEADERS) as resp:
            text = await resp.text()
            print(f"[LOAD_STATS] HTTP {resp.status}")
            if resp.status == 200:
                try:
                    data = json.loads(text)
                    content = base64.b64decode(data['content']).decode()
                    stats = json.loads(content)
                    stats.setdefault('total_rolls', 0)
                    stats.setdefault('leaderboard', [])
                    stats['_sha'] = data['sha']
                    return stats
                except Exception as e:
                    print(f"[LOAD_STATS] JSON parse error: {e}")
                    print(f"Response text:\n{text}")
                    return {"total_rolls": 0, "leaderboard": []}
            else:
                print(f"[LOAD_STATS] Failed ({resp.status}):\n{text}")
                # If file not found, create default stats
                if resp.status == 404:
                    print("[LOAD_STATS] Creating new stats.json (file not found).")
                    return {"total_rolls": 0, "leaderboard": []}
                return {"total_rolls": 0, "leaderboard": []}


async def save_stats(stats):
    sha = stats.pop('_sha', None)
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{STATS_PATH}"
    payload = {
        "message": f"Update stats - total rolls {stats['total_rolls']}",
        "content": base64.b64encode(json.dumps(stats, indent=2).encode()).decode()
    }
    if sha:
        payload["sha"] = sha

    async with aiohttp.ClientSession() as session:
        async with session.put(url, headers=GITHUB_HEADERS, json=payload) as resp:
            text = await resp.text()
            print(f"[SAVE_STATS] HTTP {resp.status}")
            print(f"[SAVE_STATS] Response: {text}")
            if resp.status in (200, 201):
                try:
                    response = json.loads(text)
                    stats['_sha'] = response['content']['sha']
                    print("[SAVE_STATS]  Stats saved successfully.")
                except Exception as e:
                    print(f"[SAVE_STATS]  JSON parse failed: {e}")
            elif resp.status == 422 and sha:
                print("[SAVE_STATS] ⚙️ SHA mismatch — retrying without SHA.")
                payload.pop("sha", None)
                async with session.put(url, headers=GITHUB_HEADERS, json=payload) as retry:
                    retry_text = await retry.text()
                    print(f"[SAVE_STATS-RETRY] {retry.status}: {retry_text[:500]}")
                    if retry.status in (200, 201):
                        response = json.loads(retry_text)
                        stats['_sha'] = response['content']['sha']
                        print("[SAVE_STATS]  Retry succeeded.")
                    else:
                        print("[SAVE_STATS]  Retry failed.")
            else:
                print(f"[SAVE_STATS]  Failed ({resp.status}) — full body:\n{text}")

