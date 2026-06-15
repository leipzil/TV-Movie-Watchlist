import sqlite3
import requests

TMDB_API_KEY = "0027014ff7945860eb80ccb24f384ee4"
TMDB_BASE = "https://api.themoviedb.org/3"
DB_FILE = "watchlist.db"

WATCH_STATUSES = ["Want to Watch", "Watching", "Completed", "Dropped"]

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS watchlist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tmdb_id INTEGER NOT NULL,
            media_type TEXT NOT NULL,
            title TEXT NOT NULL,
            release_year TEXT,
            genres TEXT,
            overview TEXT,
            tmdb_rating REAL,
            runtime TEXT,
            watch_status TEXT,
            my_rating INTEGER,
            notes TEXT,
            UNIQUE(tmdb_id, media_type)
        )
    """)
    conn.commit()
    conn.close()

def search_tmdb(query, media_type):
    endpoint = f"{TMDB_BASE}/search/{media_type}"
    params = {"api_key": TMDB_API_KEY, "query": query, "language": "en-US", "page": 1}
    try:
        r = requests.get(endpoint, params=params, timeout=10)
        r.raise_for_status()
        return r.json().get("results", [])[:5]
    except requests.exceptions.ConnectionError:
        print("No internet connection.")
        return []
    except requests.exceptions.HTTPError:
        if r.status_code == 401:
            print("Invalid API key.")
        else:
            print(f"TMDB error {r.status_code}")
        return []
    except Exception as e:
        print(f"Something went wrong: {e}")
        return []

def fetch_details(tmdb_id, media_type):
    endpoint = f"{TMDB_BASE}/{media_type}/{tmdb_id}"
    params = {"api_key": TMDB_API_KEY, "language": "en-US"}
    r = requests.get(endpoint, params=params, timeout=10)
    r.raise_for_status()
    data = r.json()

    title = data.get("title") or data.get("name", "Unknown")
    date = data.get("release_date") or data.get("first_air_date", "")
    release_year = date[:4] if date else "?"
    genres = ", ".join(g["name"] for g in data.get("genres", []))
    overview = data.get("overview", "")
    tmdb_rating = data.get("vote_average")

    if media_type == "movie":
        mins = data.get("runtime")
        runtime = f"{mins} min" if mins else "?"
    else:
        seasons = data.get("number_of_seasons")
        episodes = data.get("number_of_episodes")
        runtime = f"{seasons}s {episodes}ep" if seasons else "?"

    return {
        "tmdb_id": data["id"],
        "media_type": media_type,
        "title": title,
        "release_year": release_year,
        "genres": genres,
        "overview": overview,
        "tmdb_rating": tmdb_rating,
        "runtime": runtime,
    }

def display_results(results):
    if not results:
        print("No results.")
        return
    print()
    for i, r in enumerate(results):
        title = r.get("title") or r.get("name", "?")
        date = r.get("release_date") or r.get("first_air_date", "")
        year = date[:4] if date else "?"
        rating = r.get("vote_average", "?")
        media = r.get("media_type", "")
        tag = f"[{media.upper()}]" if media else ""
        print(f"{i+1}. {title} ({year}){tag} - {rating}")

def add_to_watchlist(details, watch_status, my_rating=None, notes=None):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    try:
        c.execute("""
            INSERT INTO watchlist
                (tmdb_id, media_type, title, release_year, genres, overview, tmdb_rating, runtime, watch_status, my_rating, notes)
            VALUES
                (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (details["tmdb_id"], details["media_type"], details["title"], details["release_year"],
              details["genres"], details["overview"], details["tmdb_rating"], details["runtime"],
              watch_status, my_rating, notes))
        conn.commit()
        print(f"Added \"{details['title']}\".")
    except sqlite3.IntegrityError:
        print("Already in watchlist.")
    finally:
        conn.close()

def display_watchlist(filter_status=None, filter_genre=None, filter_type=None):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    q = "SELECT id, title, media_type, release_year, genres, runtime, tmdb_rating, watch_status, my_rating FROM watchlist"
    params = []
    conditions = []

    if filter_status:
        conditions.append("watch_status = ?")
        params.append(filter_status)
    if filter_genre:
        conditions.append("genres LIKE ?")
        params.append(f"%{filter_genre}%")
    if filter_type:
        conditions.append("media_type = ?")
        params.append(filter_type)

    if conditions:
        q += " WHERE " + " AND ".join(conditions)
    q += " ORDER BY watch_status, title"

    c.execute(q, params)
    rows = c.fetchall()
    conn.close()

    if not rows:
        print("Nothing found.")
        return

    print(f"\n{'ID':<5} {'Title':<35} {'Type':<6} {'Year':<6} {'Genre':<27} {'Runtime':<20} {'TMDB':>5} {'Status':<16} {'Mine':>5}")
    print("-" * 133)
    for row in rows:
        id_, title, mtype, year, genres, runtime, tmdb_r, status, my_r = row
        tmdb_str = f"{tmdb_r:.1f}" if tmdb_r else "-"
        my_str = str(my_r) if my_r else "-"
        mtype = "TV" if mtype == "tv" else "Movie"
        print(f"{id_:<5} {title[:33]:<35} {mtype:<6} {year:<6} {(genres or '')[:25]:<27} {(runtime or '?')[:18]:<20} {tmdb_str:>5} {status:<16} {my_str:>5}")

def view_details(entry_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT * FROM watchlist WHERE id = ?", (entry_id,))
    row = c.fetchone()
    conn.close()
    if not row:
        print("Not found.")
        return
    cols = ["id", "tmdb_id", "media_type", "title", "release_year", "genres", "overview", "tmdb_rating", "runtime", "watch_status", "my_rating", "notes"]
    d = dict(zip(cols, row))
    print(f"""
{d['title']} ({d['release_year']}) - {d['media_type']}
Genres  : {d['genres']}
Runtime : {d['runtime']}
TMDB    : {d['tmdb_rating']}

{d['overview']}

Status  : {d['watch_status']}
My rating: {d['my_rating'] or 'unrated'}
Notes   : {d['notes'] or '-'}
""")

def trending(media_type, time_window):
    endpoint = f"{TMDB_BASE}/trending/{media_type}/{time_window}"
    params = {"api_key": TMDB_API_KEY, "language": "en-US"}
    r = requests.get(endpoint, params=params, timeout=10)
    r.raise_for_status()
    return r.json().get("results", [])[:5]

def update_entry(entry_id, field, new_value):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(f"UPDATE watchlist SET {field} = ? WHERE id = ?", (new_value, entry_id))
    if c.rowcount == 0:
        print("ID not found.")
    else:
        conn.commit()
        print("Updated.")
    conn.close()

def delete_entry(entry_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM watchlist WHERE id = ?", (entry_id,))
    if c.rowcount == 0:
        print("ID not found.")
    else:
        conn.commit()
        print("Removed.")
    conn.close()

init_db()

while True:
    try:
        print("""
1. View watchlist
2. Search & add
3. View entry details
4. Update entry
5. Remove entry
6. Trending
0. Exit""")
        menu = int(input("Choice: "))

        if menu == 1:
            print("\n1. All  2. By status  3. By genre  4. By type")
            fc = int(input("Choice: "))
            if fc == 1:
                display_watchlist()
            elif fc == 2:
                for i, s in enumerate(WATCH_STATUSES):
                    print(f"  {i+1}. {s}")
                while True:
                    try:
                        pick = int(input("Pick: ")) - 1
                        if 0 <= pick <= 3:
                            break
                    except ValueError:
                        pass
                display_watchlist(filter_status=WATCH_STATUSES[pick])
            elif fc == 3:
                genre = input("Genre: ").strip()
                display_watchlist(filter_genre=genre)
            elif fc == 4:
                print("1. Movies  2. TV")
                pick = int(input("Choice: "))
                display_watchlist(filter_type="movie" if pick == 1 else "tv")

        elif menu == 2:
            print("1. Movie  2. TV")
            type_choice = int(input("Choice: "))
            media_type = "movie" if type_choice == 1 else "tv"
            query = input("Search: ").strip()
            results = search_tmdb(query, media_type)
            display_results(results)
            if not results:
                continue

            print("  0. Cancel")
            while True:
                try:
                    pick = int(input("Pick: "))
                    if 0 <= pick <= len(results):
                        break
                except ValueError:
                    pass
            if pick == 0:
                continue

            chosen = results[pick - 1]
            details = fetch_details(chosen["id"], media_type)
            if not details:
                continue

            print(f"\n{details['title']} ({details['release_year']}) | {details['genres']} | {details['runtime']} | TMDB: {details['tmdb_rating']}")
            print(details['overview'][:200])

            for i, s in enumerate(WATCH_STATUSES):
                print(f"  {i+1}. {s}")
            while True:
                try:
                    status_pick = int(input("Status: ")) - 1
                    if 0 <= status_pick <= 3:
                        break
                except ValueError:
                    pass
            watch_status = WATCH_STATUSES[status_pick]

            rating_input = input("Your rating /10 (enter to skip): ").strip()
            my_rating = int(rating_input) if rating_input.isdigit() and 1 <= int(rating_input) <= 10 else None
            notes = input("Notes (enter to skip): ").strip() or None
            add_to_watchlist(details, watch_status, my_rating, notes)

        elif menu == 3:
            entry_id = int(input("ID: "))
            view_details(entry_id)

        elif menu == 4:
            entry_id = int(input("ID: "))
            print("1. Status  2. Rating  3. Notes")
            field_choice = int(input("Choice: "))
            if field_choice == 1:
                for i, s in enumerate(WATCH_STATUSES):
                    print(f"  {i+1}. {s}")
                while True:
                    try:
                        pick = int(input("Pick: ")) - 1
                        if 0 <= pick <= 3:
                            break
                    except ValueError:
                        pass
                update_entry(entry_id, "watch_status", WATCH_STATUSES[pick])
            elif field_choice == 2:
                r = input("Rating (1-10): ").strip()
                update_entry(entry_id, "my_rating", int(r) if r.isdigit() else None)
            elif field_choice == 3:
                n = input("Notes: ").strip()
                update_entry(entry_id, "notes", n)

        elif menu == 5:
            entry_id = int(input("ID: "))
            confirm = input("Sure? (y/n): ").lower()
            if confirm == "y":
                delete_entry(entry_id)

        elif menu == 6:
            print("\n1. Today  2. This week")
            time_window = "day" if int(input("Choice: ")) == 1 else "week"
            print("1. All  2. Movies  3. TV")
            media_map = {1: "all", 2: "movie", 3: "tv"}
            media_type = media_map.get(int(input("Choice: ")), "all")
            results = trending(media_type, time_window)
            display_results(results)

        elif menu == 0:
            break

        else:
            print("Invalid.")

    except ValueError:
        print("Enter a number.")
    except Exception as e:
        print("Error:", e)
