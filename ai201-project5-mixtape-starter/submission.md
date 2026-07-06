# Mixtape Bug Hunt Submission

## AI Usage

I used AI for ideas while reading and debugging. I asked it to help summarize unfamiliar files and think through route-to-service data flow, especially how routes delegate to service functions.


## Codebase Map

`app.py` is the Flask application factory. It creates the shared SQLAlchemy `db`, loads configuration, registers the route blueprints, and creates database tables inside the app context.

`models.py` defines the database shape for the app. The main models are `User`, `Song`, `ListeningEvent`, `Rating`, `Playlist`, `Tag`, and `Notification`. It also defines association tables for friendships, song tags, and playlist entries.

`routes/` contains the HTTP layer. The route files parse request data, call service functions, translate service return values into JSON, and convert `ValueError`s into HTTP error responses.

- `routes/songs.py` handles song search, song detail lookup, rating, and listening events.
- `routes/playlists.py` handles playlist creation, playlist details, playlist song retrieval, and adding songs to playlists.
- `routes/users.py` handles user details, streak lookup, notification lookup, and marking notifications read.
- `routes/feed.py` handles the friends-listening-now feed and general activity feed.

`services/` contains the business logic where the README says the bugs live.

- `services/streak_service.py` records listening events and updates a user's listening streak based on the user's previous listening date.
- `services/feed_service.py` builds the friends-listening-now feed and the broader friend activity feed from `ListeningEvent` records.
- `services/search_service.py` searches songs by title or artist and returns song dictionaries with tags.
- `services/notification_service.py` creates notifications, adds songs to playlists with notification side effects, records ratings, retrieves notifications, and marks notifications read.
- `services/playlist_service.py` creates playlists and retrieves playlist metadata or ordered playlist songs.

`seed_data.py` creates realistic local data: users, bidirectional friendships, tagged songs, listening events, playlists, playlist entries, and example notifications.

`tests/` contains pytest coverage for service behavior. Existing tests cover streak rules, search duplicate behavior, and playlist song retrieval.

## Data Flow Trace

Feature traced: adding a song to a playlist and notifying the original sharer.

1. A client sends `POST /playlists/<playlist_id>/songs` with `song_id` and `added_by`.
2. `routes/playlists.py` validates that both fields are present.
3. The route calls `notification_service.add_to_playlist(playlist_id, song_id, added_by)`.
4. `add_to_playlist` loads the `Song`, the adding `User`, and the `Playlist` from the database. Missing records raise `ValueError`, which the route returns as a `400`.
5. If the song is not already in the playlist relationship, the service appends it and commits.
6. If the person adding the song is not the original sharer, the service calls `create_notification`.
7. `create_notification` inserts a `Notification` row for the original sharer with type `song_added_to_playlist`.
8. The route returns `{"message": "Song added to playlist"}` with status `201`.

Pattern noticed: routes stay thin and delegate business behavior to services.

## Five Issues Read

1. My listening streak keeps resetting - `services/streak_service.py`
2. Friends Listening Now shows people from yesterday - `services/feed_service.py`
3. The same song keeps showing up twice in search - `services/search_service.py`
4. I got notified when a friend added my song to a playlist but not when they rated it - `services/notification_service.py`
5. The last song in a playlist never shows up - `services/playlist_service.py`
