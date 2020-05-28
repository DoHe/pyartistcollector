import pprint
import json
import os
import sys
import time

from dotenv import load_dotenv
from mutagen.easyid3 import EasyID3
from spotipy import Spotify
from spotipy.util import prompt_for_user_token

load_dotenv()


MUSIC_EXTS = [
    ".mp3",
    ".wav",
    ".ogg"
]

IGNORED_ARTISTS = [
    'various artists',
    'unknown',
    'untitled',
    ''
]


GENERATED_PLAYLISTS = [
    'spotify',
    'spotifydiscover'
]


def chunkify(iterable, chunk_size):
    for i in range(0, len(iterable), chunk_size):
        yield iterable[i:i+chunk_size]


def get_artists(path):
    try:
        id3 = EasyID3(path)
        artists = id3.get("artist", [])
        return [artist.lower() for artist in artists if artist.lower not in IGNORED_ARTISTS]
    except Exception as e:
        print("Couldn't open {}: {}".format(path, e), file=sys.stderr)
        return []


def collect_artists(dirs):
    all_artists = set()
    for adir in dirs:
        for root, _, files in os.walk(adir):
            print("Now reading:", root)
            for path in files:
                if os.path.splitext(path)[-1] not in MUSIC_EXTS:
                    continue
                path = os.path.join(root, path)
                artists = get_artists(path)
                all_artists.update(artists)
        print("Done")
    return all_artists


def existing_dir(path):
    if not os.path.exists(path):
        raise argparse.ArgumentTypeError(
            "Path does not exist: {}".format(path))
    return path


class SpotifyClient:

    def __init__(self, user):
        self.user = user
        scopes = "user-library-read user-follow-modify user-library-modify playlist-read-private playlist-read-collaborative"
        token = prompt_for_user_token(self.user, scope=scopes)
        self.spotify_client = Spotify(auth=token)

    def upload_artists(self, artists):
        for artist in artists:
            self.add_to_libraray(artist)

    def all_playlists(self):
        playlists = self.spotify_client.user_playlists(self.user)
        yield from playlists['items']
        while playlists['next']:
            playlists = self.spotify_client.next(playlists)
            yield from playlists['items']

    def artists_from_tracks(self, tracks):
        for track_item in tracks['items']:
            for artist in track_item['track']['artists']:
                yield artist['name']

    def all_artists_from_playlist(self, playlist_content):
        tracks = playlist_content['tracks']
        yield from self.artists_from_tracks(tracks)
        while tracks['next']:
            tracks = self.spotify_client.next(tracks)
            yield from self.artists_from_tracks(tracks)

    def get_library_artists(self):
        result = set()
        playlists = list(self.all_playlists())
        print("Found %d playlists" % len(playlists))
        for playlist in playlists:
            if playlist['owner']['id'] in GENERATED_PLAYLISTS:
                continue
            playlist_content = self.spotify_client.user_playlist(
                self.user,
                playlist['id'],
                fields="tracks,next"
            )
            artists = set(self.all_artists_from_playlist(playlist_content))
            print("Found %d artists in playlist %s" % (len(artists), playlist["name"]))
            result |= artists
        return result

    def add_to_libraray(self, artist):
        spotify_artists = self.spotify_client.search(artist, type="artist").get('artists', {}).get('items')
        if not spotify_artists:
            return
        print("Following", spotify_artists[0].get('name'))
        artist_id = spotify_artists[0].get("id")
        self.spotify_client.user_follow_artists(ids=[artist_id])
        albums = self.spotify_client.artist_albums(artist_id, limit=50).get('items')
        album_ids = []
        for album in albums:
            if album.get('album_type') != 'album':
                continue
            album_ids.append(album.get('id'))
        if album_ids:
            print("Found", len(album_ids), "albums in total for", artist.title())
            contained = self.spotify_client.current_user_saved_albums_contains(album_ids)
            new_album_ids = []
            for album_id, is_contained in zip(album_ids, contained):
                if not is_contained:
                    new_album_ids.append(album_id)
            if not new_album_ids:
                print("All of them already in your library")
            print("Adding {} new albums for {}".format(len(new_album_ids), artist.title()))
            for chunk in chunkify(list(new_album_ids), 50):
                self.spotify_client.current_user_saved_albums_add(albums=chunk)
            time.sleep(1)
        else:
            print("No albums for", artist)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Collect local mp3 tags and add to Spotify library')
    parser.add_argument('dirs', metavar='dirst', type=existing_dir, nargs="+",
                        help='Directories to search.')
    parser.add_argument('-p', '--playlist', action='store_true',
                        help='Add playlist artists to library')
    parser.add_argument('-u', '--user', type=str, required=True,
                        help='Add playlist artists to library')
    args = parser.parse_args()
    artists = collect_artists(args.dirs)
    print(("Found {} artists".format(len(artists))))
    c = SpotifyClient(args.user)
    if args.playlist:
        artists |= c.get_library_artists()
    c.upload_artists(sorted(artists))
