import sqlite3
import requests

TMDB_API_KEY = "Enter your API key here"

TMDB_BASE = "https://api.themoviedb.org/3"
DB_FILE = "watchlist.db"

WATCH_STATUSES = ["Want to Watch", "Watching", "Completed", "Dropped"]
MEDIA_TYPES = ["movie", "tv"]

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS watchlist (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            tmdb_id         INTEGER NOT NULL,
            media_type      TEXT NOT NULL,
            title           TEXT NOT NULL,
            release_year    TEXT,
            genres          TEXT,
            overview        TEXT,
            tmdb_rating     REAL,
            runtime         TEXT,
            watch_status    TEXT DEFAULT 'Want to Watch',
            my_rating       INTEGER,
            notes           TEXT,
            UNIQUE(tmdb_id, media_type)
        )
    """)
    conn.commit()
    conn.close()

def search_tmdb(query, media_type="movie"):
    endpoint = f"{TMDB_BASE}/search/{media_type}"
    params = {"api_key": TMDB_API_KEY, "query": query, "language": "en-US", "page": 1}
    try:
        response = requests.get(endpoint, params=params, timeout=10)
        response.raise_for_status()
        results = response.json().get("results", [])
        return results[:5]  # Return top 5 matches
    except requests.exceptions.ConnectionError:
        print("ERROR: No internet connection.")
        return []
    except requests.exceptions.HTTPError as e:
        if response.status_code == 401:
            print("ERROR: Invalid API key. Check your TMDB_API_KEY.")
        else:
            print(f"ERROR: TMDB returned status {response.status_code}.")
        return []
    except requests.exceptions.RequestException as e:
        print(f"ERROR: {e}")
        return []

def fetch_details(tmdb_id, media_type="movie"):
    """Fetch full details for a specific movie or TV show."""
    endpoint = f"{TMDB_BASE}/{media_type}/{tmdb_id}"
    params = {"api_key": TMDB_API_KEY, "language": "en-US"}
    try:
        response = requests.get(endpoint, params=params, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"ERROR fetching details: {e}")
        return None

def parse_details(data, media_type):
    """Extract the fields we care about from TMDB's response."""
    title = data.get("title") or data.get("name", "Unknown")

    # Release year
    date = data.get("release_date") or data.get("first_air_date", "")
    release_year = date[:4] if date else "?"

    # Genres
    genres = ", ".join(g["name"] for g in data.get("genres", []))

    # Overview
    overview = data.get("overview", "No overview available.")

    # TMDB rating
    tmdb_rating = data.get("vote_average")

    # Runtime
    if media_type == "movie":
        mins = data.get("runtime")
        runtime = f"{mins} min" if mins else "?"
    else:
        seasons = data.get("number_of_seasons")
        episodes = data.get("number_of_episodes")
        runtime = f"{seasons} season(s), {episodes} ep(s)" if seasons else "?"

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

def add_to_watchlist(details, watch_status, my_rating=None, notes=None):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO watchlist
                (tmdb_id, media_type, title, release_year, genres, overview, tmdb_rating, runtime, watch_status, my_rating, notes)
            VALUES
                (:tmdb_id, :media_type, :title, :release_year, :genres, :overview, :tmdb_rating, :runtime, :watch_status, :my_rating, :notes)
        """, {**details, "watch_status": watch_status, "my_rating": my_rating, "notes": notes})
        conn.commit()
        print(f"Added \"{details['title']}\" to your watchlist.")
    except sqlite3.IntegrityError:
        print("This title is already in your watchlist.")
    finally:
        conn.close()

def display_watchlist(filter_status=None, filter_genre=None, filter_type=None):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    query = "SELECT id, title, media_type, release_year, genres, runtime, tmdb_rating, watch_status, my_rating FROM watchlist"
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
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY watch_status, title"

    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()

    if not rows:
        print("Nothing found.")
        return

    print(f"\n{'ID':<5} {'Title':<35} {'Type':<6} {'Year':<6} {'Genre':<25} {'Runtime':<20} {'TMDB':>5} {'Status':<16} {'Mine':>5}")
    print("-" * 130)
    for row in rows:
        id_, title, mtype, year, genres, runtime, tmdb_r, status, my_r = row
        tmdb_str = f"{tmdb_r:.1f}" if tmdb_r else "-"
        my_str = str(my_r) if my_r else "-"
        print(f"{id_:<5} {title[:33]:<35} {mtype:<6} {year:<6} {(genres or '')[:23]:<25} {(runtime or '?')[:18]:<20} {tmdb_str:>5} {status:<16} {my_str:>5}")

def view_details(entry_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM watchlist WHERE id = ?", (entry_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        print("ID not found.")
        return
    cols = ["id", "tmdb_id", "media_type", "title", "release_year", "genres",
            "overview", "tmdb_rating", "runtime", "watch_status", "my_rating", "notes"]
    data = dict(zip(cols, row))
    print(f"""
Title      : {data['title']} ({data['release_year']})
Type       : {data['media_type']}
Genres     : {data['genres']}
Runtime    : {data['runtime']}
TMDB Rating: {data['tmdb_rating']}
Overview   : {data['overview']}
-----------------------------
Watch Status: {data['watch_status']}
My Rating   : {data['my_rating'] or 'Not rated'}
Notes       : {data['notes'] or 'None'}
""")

def update_entry(entry_id, field, new_value):
    allowed = ("watch_status", "my_rating", "notes")
    if field not in allowed:
        print(f"Can only update: {', '.join(allowed)}")
        return
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(f"UPDATE watchlist SET {field} = ? WHERE id = ?", (new_value, entry_id))
    if cursor.rowcount == 0:
        print("ID not found.")
    else:
        conn.commit()
        print("Updated.")
    conn.close()

def delete_entry(entry_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM watchlist WHERE id = ?", (entry_id,))
    if cursor.rowcount == 0:
        print("ID not found.")
    else:
        conn.commit()
        print("Removed from watchlist.")
    conn.close()

def show_stats():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM watchlist")
    total = cursor.fetchone()[0]

    cursor.execute("SELECT watch_status, COUNT(*) FROM watchlist GROUP BY watch_status")
    by_status = cursor.fetchall()

    cursor.execute("SELECT media_type, COUNT(*) FROM watchlist GROUP BY media_type")
    by_type = cursor.fetchall()

    cursor.execute("SELECT AVG(my_rating) FROM watchlist WHERE my_rating IS NOT NULL")
    avg_rating = cursor.fetchone()[0]

    cursor.execute("SELECT title, my_rating FROM watchlist WHERE my_rating IS NOT NULL ORDER BY my_rating DESC LIMIT 3")
    top_rated = cursor.fetchall()

    conn.close()

    print(f"\nTotal titles tracked: {total}")
    print("\nBy status:")
    for status, count in by_status:
        print(f"  {status}: {count}")
    print("\nBy type:")
    for mtype, count in by_type:
        print(f"  {mtype}: {count}")
    if avg_rating:
        print(f"\nYour average rating: {avg_rating:.1f}/10")
    if top_rated:
        print("\nYour top rated:")
        for title, rating in top_rated:
            print(f"  {rating}/10 — {title}")

init_db()

while True:
    try:
        print("""
1. View watchlist
2. Search & add a title
3. View full details of an entry
4. Update status / rating / notes
5. Remove a title
6. Filter by status
7. Filter by genre
8. Filter by type (movie / tv)
9. Stats
0. Exit""")
        menu = int(input("Choose: "))

        if menu == 1:
            display_watchlist()

        elif menu == 2:
            print("Search for: 1. Movie  2. TV Show")
            while True:
                try:
                    type_choice = int(input("Choose (1-2): "))
                    if type_choice in (1, 2):
                        break
                except ValueError:
                    pass
            media_type = "movie" if type_choice == 1 else "tv"
            query = input("Enter title to search: ").strip()
            results = search_tmdb(query, media_type)

            if not results:
                print("No results found.")
                continue

            print("\nResults:")
            for i, r in enumerate(results):
                title = r.get("title") or r.get("name", "?")
                date = r.get("release_date") or r.get("first_air_date", "")
                year = date[:4] if date else "?"
                rating = r.get("vote_average", "?")
                print(f"  {i+1}. {title} ({year}) — TMDB: {rating}")

            print(f"  0. Cancel")
            while True:
                try:
                    pick = int(input("Pick a result: "))
                    if 0 <= pick <= len(results):
                        break
                except ValueError:
                    pass

            if pick == 0:
                continue

            chosen = results[pick - 1]
            print("Fetching full details...")
            data = fetch_details(chosen["id"], media_type)
            if not data:
                continue

            details = parse_details(data, media_type)
            print(f"\n{details['title']} ({details['release_year']})")
            print(f"Genres : {details['genres']}")
            print(f"Runtime: {details['runtime']}")
            print(f"TMDB   : {details['tmdb_rating']}")
            print(f"Overview: {details['overview'][:200]}...")

            print("\nWatch status:")
            for i, s in enumerate(WATCH_STATUSES):
                print(f"  {i+1}. {s}")
            while True:
                try:
                    status_pick = int(input("Pick (1-4): ")) - 1
                    if 0 <= status_pick <= 3:
                        break
                except ValueError:
                    pass
            watch_status = WATCH_STATUSES[status_pick]

            rating_input = input("Your rating out of 10 (or Enter to skip): ").strip()
            my_rating = int(rating_input) if rating_input.isdigit() and 1 <= int(rating_input) <= 10 else None
            notes = input("Notes (or Enter to skip): ").strip() or None

            add_to_watchlist(details, watch_status, my_rating, notes)

        elif menu == 3:
            entry_id = int(input("Enter ID: "))
            view_details(entry_id)

        elif menu == 4:
            entry_id = int(input("Enter ID to update: "))
            print("Update: 1. Watch status  2. My rating  3. Notes")
            field_choice = int(input("Choose (1-3): "))
            if field_choice == 1:
                for i, s in enumerate(WATCH_STATUSES):
                    print(f"  {i+1}. {s}")
                while True:
                    try:
                        pick = int(input("Pick (1-4): ")) - 1
                        if 0 <= pick <= 3:
                            break
                    except ValueError:
                        pass
                update_entry(entry_id, "watch_status", WATCH_STATUSES[pick])
            elif field_choice == 2:
                r = input("New rating (1-10): ").strip()
                update_entry(entry_id, "my_rating", int(r) if r.isdigit() else None)
            elif field_choice == 3:
                n = input("New notes: ").strip()
                update_entry(entry_id, "notes", n)

        elif menu == 5:
            entry_id = int(input("Enter ID to remove: "))
            confirm = input("Are you sure? (Y/N): ").upper()
            if confirm == "Y":
                delete_entry(entry_id)

        elif menu == 6:
            for i, s in enumerate(WATCH_STATUSES):
                print(f"  {i+1}. {s}")
            while True:
                try:
                    pick = int(input("Pick (1-4): ")) - 1
                    if 0 <= pick <= 3:
                        break
                except ValueError:
                    pass
            display_watchlist(filter_status=WATCH_STATUSES[pick])

        elif menu == 7:
            genre = input("Enter genre to filter by (e.g. Action, Drama): ").strip()
            display_watchlist(filter_genre=genre)

        elif menu == 8:
            print("1. Movies only  2. TV only")
            while True:
                try:
                    pick = int(input("Choose (1-2): "))
                    if pick in (1, 2):
                        break
                except ValueError:
                    pass
            display_watchlist(filter_type="movie" if pick == 1 else "tv")

        elif menu == 9:
            show_stats()

        elif menu == 0:
            print("Goodbye!")
            break

        else:
            print("Invalid option.")

    except ValueError:
        print("Please enter a valid number.")
    except Exception as e:
        print("ERROR:", e)
