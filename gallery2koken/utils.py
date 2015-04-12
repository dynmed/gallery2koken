import argparse
import requests
import base64
import urlparse
import config
import json
import re

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--command",
                        choices=["login", "fetch-albums", "fetch-album-images",
                                 "fetch-album-image-files"],
                        help="Specify command to run")
    parser.add_argument("--album-name", help="Album name to run command on")
    parser.add_argument("--gallery-local", action="store_true", default=False,
                        help="Send requests to Gallery 2 server via localhost")
    args = parser.parse_args()
    if (args.command in ["fetch-album-images", "fetch-album-image-files"] and
        not args.album_name):
        parser.error(
            "--fetch-album-images and --fetch-album-image-files " +
            "also require --album-name be specified."
        )
    return args

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

def pretty_print(obj):
    print json.dumps(obj, indent=2, separators=(',', ': '))
