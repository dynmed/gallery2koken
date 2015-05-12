# gallery2koken

This tool wraps the APIs for [Gallery
2](http://codex.galleryproject.org/Gallery_Remote:Protocol) and
[Koken](http://koken.me/) and provides migration functionality from
the former to the latter. The API for Koken is not documented as of
2015-05-08.

### Usage:

Install
[Requests](http://docs.python-requests.org/en/latest/user/install/#install):

```sh
$ pip install requests
```

Create the configuration file and edit it to contain your Gallery and
Koken credentials:

```sh
$ cd gallery2koken/gallery2koken
$ cp config.example.py config.py
$ emacs config.py
```

Migrate the Gallery albums to Koken:

```sh
$ python automate.py --gallery-migrate-albums-to-koken
```

### Compatbility:

Tested using Gallery 2.3.2 and Koken 0.21.2.
