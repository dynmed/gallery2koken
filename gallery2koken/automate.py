"""
This module wraps the APIs for Gallery 2 [1] and Koken [2] and provides migration
functionality from the former to the latter.
[1] http://codex.galleryproject.org/Gallery_Remote:Protocol
[2] http://koken.me/ (API not documented)

Copyright (c) 2015 Dynamic Media
Licensed under the MIT License. See LICENSE for more details.
"""

import utils
import config

def main(args):
    gallery2 = utils.Gallery2(config.GALLERY_2_BASE_URL)
    koken = utils.Koken(config.KOKEN_BASE_URL)

    if args.http_debug:
        utils.setup_logging(debug = True)
    else:
        utils.setup_logging(debug = False)

    if args.gallery_login:
        gallery2.login()

    if args.gallery_fetch_albums:
        utils.pretty_print(gallery2.fetch_albums())

    if args.gallery_fetch_album_images:
        utils.pretty_print(gallery2.fetch_album_images(args.album_name))

    if args.gallery_fetch_album_image_files:
        gallery2.fetch_album_image_files(args.album_name)

    if args.gallery_migrate_albums_to_koken:
        gallery2.migrate_albums(koken)

    if args.koken_create_album:
        print "created album: %s" % koken.create_album(args.album_name)

    if args.koken_upload_photo:
        print "uploaded photo: %s" % koken.upload_photo(args.upload_koken_photo)

    if args.koken_reset_album_date:
        koken.reset_album_date(args.reset_koken_album_date)

if __name__ == "__main__":
    config.ARGS = utils.parse_args()
    main(config.ARGS)
