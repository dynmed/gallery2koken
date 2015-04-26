import utils
import config

def main(args):
    gallery2 = utils.Gallery2(config.GALLERY_2_BASE_URL)
    koken = utils.Koken(config.KOKEN_BASE_URL)

    if args.http_debug:
        utils.setup_logging(debug = True)
    else:
        utils.setup_logging(debug = False)

    if args.command == "login":
        gallery2.login()

    if args.command == "fetch-albums":
        utils.pretty_print(gallery2.fetch_albums())

    if args.command == "fetch-album-images":
        utils.pretty_print(gallery2.fetch_album_images(args.album_name))

    if args.command == "fetch-album-image-files":
        gallery2.fetch_album_image_files(args.album_name)

    if args.command == "migrate-albums":
        gallery2.migrate_albums(koken)

    if args.create_koken_album:
        print "created album: %s" % koken.create_album(args.album_name)

    if args.upload_koken_photo:
        print "uploaded photo: %s" % koken.upload_photo(args.upload_koken_photo)


if __name__ == "__main__":
    config.ARGS = utils.parse_args()
    main(config.ARGS)

