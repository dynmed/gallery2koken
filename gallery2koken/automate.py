import utils
import config

def main(args):
    gallery2 = utils.Gallery2(config.GALLERY_2_BASE_URL)
    if args.command == "login":
        gallery2.login()
    if args.command == "fetch-albums":
        utils.pretty_print(gallery2.fetch_albums())
    if args.command == "fetch-album-images":
        utils.pretty_print(gallery2.fetch_album_images(args.album_name))

    if args.command == "fetch-album-image-files":
        gallery2.fetch_album_image_files(args.album_name)

if __name__ == "__main__":
    config.ARGS = utils.parse_args()
    main(config.ARGS)

