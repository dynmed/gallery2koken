import argparse
import requests
import logging
import base64
import urlparse
import config
import json
import re
import httplib
import os
import sys
import mimetypes
import time
import io

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--command",
                        choices=["login", "fetch-albums", "fetch-album-images",
                                 "fetch-album-image-files", "migrate-albums"],
                        help="Specify command to run")
    parser.add_argument("--album-name", help="Album name to run command on")
    parser.add_argument("--create-koken-album", action="store_true", default=False,
                        help="Create new album in Koken")
    parser.add_argument("--upload-koken-photo", help="Upload a photo to Koken")
    parser.add_argument("--move-photo-to-album", action="store_true",
                        default=False, help="Upload a photo to Koken")
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

def setup_logging(debug = False):
    logging.basicConfig()
    if debug:
        httplib.HTTPConnection.debuglevel = 1
        logging.getLogger().setLevel(logging.DEBUG)
        requests_log = logging.getLogger("requests.packages.urllib3")
        requests_log.setLevel(logging.DEBUG)
        requests_log.propagate = True
    else:
        logging.getLogger().setLevel(logging.INFO)

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
    def migrate_albums(self, koken):
        if self.auth_token is None:
            self.login()

        koken.login()

        albums = self.fetch_albums()
        for album_id in [key for key in albums.keys() if key.startswith("album.name")]:
            album_id_num = re.search("\d+$", album_id).group()
            # collect all the relevant information about this album before we export it
            title = albums.get("album.title.%s" % album_id_num)
            summary = albums.get("album.summary.%s" % album_id_num)
            name_id = albums.get("album.name.%s" % album_id_num)
            # get the images for this album
            images = self.fetch_album_images(name_id)
            # skip the root-level gallery album which doesn't contain any photos
            if images.get("album.caption") == "Gallery":
                continue
            # create the new album instance in Koken
            koken_album = koken.create_album(name = title, description = summary)
            if koken_album is None:
                continue
            # upload the photos to Koken
            for photo_id in [key for key in images.keys()
                             if key.startswith("image.name")]:
                photo_id_num = re.search("\d+$", photo_id).group()
                filename = images.get("image.title.%s" % photo_id_num)
                image = self.fetch_image(images.get("image.name.%s" % photo_id_num))
                koken_photo = koken.upload_photo_bytes(io.BytesIO(image.content),
                                                       filename)
                # move the photo to the new album
                koken.move_photo_to_album(koken_photo, koken_album)

        # clear the system cache so the new albums show up
        koken.clear_system_caches()

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

    def create_album(self, name, description = None):
        self.login()
        url = "%s/api.php?/albums" % self.url
        data = {
            "title": name,
            "album_type": 0, # normal album
            "visibility": "public"
        }
        # don't follow the redirect so we can parse out the album number from
        # the Location header
        response = self.session.post(url, data = data, headers = self.headers,
                                     allow_redirects = False)

        # make sure the album was successfully created
        if response.status_code == 302 and "Location" in response.headers:
            album_id = re.search("\d+$", response.headers.get("Location")).group(0)

        # something went wrong with the request
        if album_id is None:
            return None

        if description is not None:
            url = "%s/api.php?/albums/%s" % (self.url, album_id)
            data = {
                "summary": description,
                "description": description,
                "_method": "PUT"
            }
            self.session.post(url, data = data, headers = self.headers)

        return album_id

    def upload_photo(self, image_path):
        self.login()

        # attempt to resolve the filename relative to this script
        dirname = os.path.dirname(__file__)
        real_path = os.path.realpath(os.path.join(dirname, image_path))
        if not os.path.isfile(real_path):
            logging.error("file not found: %s" % real_path)
            return None

        # upload the photo
        url = "%s/api.php?/content" % self.url
        filename = os.path.basename(real_path)
        files = {
            "file": (filename, open(real_path, "rb"), mimetypes.guess_type(filename)[0])
        }
        data = {
            "name": filename,
            "visibility": "public",
            "max_download": "none",
            "license": "all",
            "upload_session_start": int(time.time())
        }
        # don't follow the redirect so we can parse out the album number from
        # the Location header
        response = self.session.post(url, data = data, files = files,
                                     headers = self.headers, allow_redirects = False)

        # make sure the album was successfully created
        if response.status_code == 302 and "Location" in response.headers:
            return re.search("\d+$", response.headers.get("Location")).group(0)

        # something went wrong with the request
        return None

    def upload_photo_bytes(self, bytesio, filename):
        self.login()

        # upload the photo
        url = "%s/api.php?/content" % self.url
        files = {
            "file": (filename, bytesio, mimetypes.guess_type(filename)[0])
        }
        data = {
            "name": filename,
            "visibility": "public",
            "max_download": "none",
            "license": "all",
            "upload_session_start": int(time.time())
        }
        # don't follow the redirect so we can parse out the album number from
        # the Location header
        response = self.session.post(url, data = data, files = files,
                                     headers = self.headers, allow_redirects = False)

        # make sure the album was successfully created
        if response.status_code == 302 and "Location" in response.headers:
            return re.search("\d+$", response.headers.get("Location")).group(0)

        # something went wrong with the request
        return None

    def move_photo_to_album(self, photo_id, album_id):
        self.login()

        url = "%s/api.php?/albums/%s/content/%s" % (self.url, album_id, photo_id)
        response = self.session.post(url, headers = self.headers)

    # emulate clicking the "Clear System Caches" button in Settings > System
    def clear_system_caches(self):
        self.login()

        url = "%s/api.php?/update/migrate/schema" % (self.url)
        self.session.post(url, headers = self.headers)

        url = "%s/api.php?/system/clear_caches" % (self.url)
        self.session.post(url, headers = self.headers)

def pretty_print(obj):
    print json.dumps(obj, indent=2, separators=(',', ': '))
