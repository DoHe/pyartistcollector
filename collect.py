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

    def __init__(self):
        token = prompt_for_user_token("dohe", scope="user-library-read user-follow-modify user-library-modify")
        self.spotify_client = Spotify(auth=token)

    def upload_artists(self, artists):
        for artist in artists:
            self.add_to_libraray(artist)

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
    args = parser.parse_args()
    artists = collect_artists(args.dirs)
    print(("Found {} artists".format(len(artists))))
    c = SpotifyClient()
    c.upload_artists(sorted(artists))
