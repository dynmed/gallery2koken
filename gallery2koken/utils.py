import argparse
import requests
import logging
import base64
import urlparse
import config
import json
import re
import httplib

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--command",
                        choices=["login", "fetch-albums", "fetch-album-images",
                                 "fetch-album-image-files", "migrate-albums"],
                        help="Specify command to run")
    parser.add_argument("--album-name", help="Album name to run command on")
    parser.add_argument("--create-koken-album", action="store_true", default=False,
                        help="Create new album in Koken")
    parser.add_argument("--gallery-local", action="store_true", default=False,
                        help="Send requests to Gallery 2 server via localhost")
    parser.add_argument("--koken-local", action="store_true", default=False,
                        help="Send requests to Koken server via localhost")
    parser.add_argument("--http-debug", action="store_true", default=False,
                        help="Extra HTTP debugging output")
    args = parser.parse_args()
    if ((args.command in ["fetch-album-images", "fetch-album-image-files"] or
         args.create_koken_album) and
        not args.album_name):
        parser.error(
            "--fetch-album-images, --fetch-album-image-files, and --create-koken-album " +
            "also require --album-name be specified."
        )
    return args

def setup_http_debug():
    httplib.HTTPConnection.debuglevel = 1
    logging.basicConfig()
    logging.getLogger().setLevel(logging.DEBUG)
    requests_log = logging.getLogger("requests.packages.urllib3")
    requests_log.setLevel(logging.DEBUG)
    requests_log.propagate = True

class Gallery2(object):
    def __init__(self, url):
        self.url = url
        # container for extra request headers
        self.headers = {}
        self.auth_token = None
        # base URL for an ablum
        self.base_url = None
        # modify some attributes if we are accessing the Gallery via localhost
        if config.ARGS.gallery_local:
            parts = urlparse.urlparse(self.url)
            self.url = urlparse.urlunparse(parts._replace(netloc="localhost"))
            # access virtual host by replacing Host header from the original URL
            self.headers = {"Host": parts.netloc}

    def parse_response(self, response):
        response_obj = {}
        for line in response.text.splitlines():
            # skip lines that don't contain name-value pairs
            if "=" not in line:
                continue
            name, value = line.split("=", 1)
            # unescape the Java properties-escaped characters
            response_obj[name] = value.replace("\:", ":").replace("\=", "=")
        return response_obj

    def login(self):
        if self.auth_token is not None:
            return

        data = {
            "g2_controller": "remote:GalleryRemote",
            "g2_form[cmd]": "login",
            "g2_form[protocol_version]": "2.0",
            "g2_form[uname]": config.GALLERY_2_USERNAME,
            "g2_form[password]": config.GALLERY_2_PASSWORD
        }
        response = self.parse_response(
            requests.post(self.url, data = data, headers = self.headers)
        )
        self.auth_token = response.get("auth_token")

    def fetch_albums(self):
        if self.auth_token is None:
            self.login()

        data = {
            "g2_controller": "remote:GalleryRemote",
            "g2_form[cmd]": "fetch-albums",
            "g2_form[protocol_version]": "2.0",
            "g2_form[g2_authToken]": self.auth_token
        }
        return self.parse_response(
            requests.post(self.url, data = data, headers = self.headers)
        )

    def fetch_album_images(self, album_name):
        if self.auth_token is None:
            self.login()

        data = {
            "g2_controller": "remote:GalleryRemote",
            "g2_form[cmd]": "fetch-album-images",
            "g2_form[protocol_version]": "2.4",
            "g2_form[albums_too]": "yes", # return sub-albums as well
            "g2_form[set_albumName]": album_name,
            "g2_form[g2_authToken]": self.auth_token
        }
        response = self.parse_response(
            requests.post(self.url, data = data, headers = self.headers)
        )
        self.base_url = response.get("baseurl")
        # modify some attributes if we are accessing the Gallery via localhost
        if config.ARGS.gallery_local:
            parts = urlparse.urlparse(self.base_url)
            self.base_url = urlparse.urlunparse(parts._replace(netloc="localhost"))
        return response

    def fetch_album_image_files(self, album_name):
        album_images = self.fetch_album_images(album_name)
        for image_id in [key for key in album_images.keys() if key.startswith("image.name")]:
            image_id_num = re.search("\d+$", image_id).group()
            with open(album_images.get("image.title.%s" % image_id_num), "wb") as fp:
                image = self.fetch_image(album_images.get("image.name.%s" % image_id_num))
                for chunk in image.iter_content(1024):
                    fp.write(chunk)

    def fetch_image(self, image_id):
        return requests.get("%s%s" % (self.base_url, image_id), headers = self.headers)

    # main wrapper function to iterate through Gallery 2 albums and create corresponding
    # albums in Koken
    def migrate_albums(self):
        if self.auth_token is None:
            self.login()

        albums = self.fetch_albums()
        for album_id in [key for key in albums.keys() if key.startswith("album.name")]:
            album_id_num = re.search("\d+$", album_id).group()
            # collect all the relevant information about this album before we export it
            title = albums.get("album.title.%s" % album_id_num)
            summary = albums.get("album.summary.%s" % album_id_num)
            name_id = albums.get("album.name.%s" % album_id_num)
            # get the images for this album
            images = self.fetch_album_images(name_id)
            
            pretty_print(images)
            print ""

class Koken(object):
    def __init__(self, url):
        self.url = url
        self.session = requests.Session()
        self.headers = {"X-Koken-Auth": "cookie"}
        # modify some attributes if we are accessing Koken via localhost
        if config.ARGS.koken_local:
            parts = urlparse.urlparse(self.url)
            self.url = urlparse.urlunparse(parts._replace(netloc="localhost"))
            # access virtual host by replacing Host header from the original URL
            self.headers["Host"] = parts.netloc

    def login(self):
        if self.session.cookies.get("koken_session_ci") is not None:
            return

        data = {
            "email": config.KOKEN_USERNAME,
            "password": config.KOKEN_PASSWORD
        }
        url = "%s/api.php?/sessions" % self.url
        self.session.post(url, data = data, headers = self.headers)

    def create_album(self, album_name):
        self.login()
        url = "%s/api.php?/albums" % self.url
        data = {
            "title": album_name,
            "album_type": 0, # normal album
            "visibility": "public"
        }
        self.session.post(url, data = data, headers = self.headers)

def pretty_print(obj):
    print json.dumps(obj, indent=2, separators=(',', ': '))
