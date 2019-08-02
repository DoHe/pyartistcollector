import json
import os
import sys

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


def get_artists(path):
    try:
        id3 = EasyID3(path)
        artists = id3.get("artist", [])
        return [artist.lower() for artist in artists]
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


def upload_artists(artists):
    token = prompt_for_user_token("dohe", scope="user-follow-modify")
    spotify_client = Spotify(auth=token)
    spotify_client.user_follow_artists(ids=[])


def existing_dir(path):
    if not os.path.exists(path):
        raise argparse.ArgumentTypeError(
            "Path does not exist: {}".format(path))
    return path


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description='Collect local mp3 tags and add to Spotify library')
    parser.add_argument('dirs', metavar='dirst', type=existing_dir, nargs="+",
                        help='Directories to search.')

    args = parser.parse_args()
    # artists = collect_artists(args.dirs)
    artists = ["finger eleven"]
    print(("Found {} artists".format(len(artists))))
    upload_artists(artists)
