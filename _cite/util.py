"""
utility functions for cite process and plugins
"""

import subprocess
import json
import yaml
import os
import tempfile
import time
from yaml.loader import SafeLoader
from pathlib import Path
from datetime import date, datetime
from rich import print
from diskcache import Cache


# cache for time-consuming network requests
cache = Cache(os.environ.get("CITE_CACHE_DIR", "./_cite/.cache"))


# clear expired items from cache
cache.expire()


def log_cache(func):
    """
    decorator to use around memoized function to log if cached or or not
    """

    def wrap(*args):
        key = func.__cache_key__(*args)
        if key in cache:
            log(" (from cache)", level="INFO", newline=False)
        return func(*args)

    return wrap


def log(message="\n--------------------\n", indent=0, level="", newline=True):
    """
    log to terminal, color determined by indent and level
    """

    colors = {
        0: "[orange1]",
        1: "[salmon1]",
        2: "[violet]",
        3: "[sky_blue1]",
        "ERROR": "[#F43F5E]",
        "WARNING": "[#EAB308]",
        "SUCCESS": "[#10B981]",
        "INFO": "[grey70]",
    }
    prefixes = {
        "ERROR": "🚫 ERROR: ",
        "WARNING": "⚠️ WARNING: ",
    }
    color = get_safe(colors, level, "") or get_safe(colors, indent, "") or "[white]"
    prefix = get_safe(prefixes, level, "")
    if newline:
        print()
    print(indent * "    " + color + prefix + str(message) + "[/]", end="", flush=True)


def label(entry):
    """
    get "label" of dict entry (for logging purposes)
    """

    return str(list(entry.keys())[0]) + ": " + str(list(entry.values())[0])


def get_safe(item, path, default=None):
    """
    safely access value in nested lists/dicts
    """

    for part in str(path).split("."):
        try:
            part = int(part)
        except ValueError:
            part = part
        try:
            item = item[part]
        except (KeyError, IndexError, AttributeError, TypeError):
            return default
    return item


def index_of(_list, value, fallback=float("inf")):
    """
    index of, with fallback
    """

    try:
        return _list.index(value)
    except ValueError:
        return fallback


def list_of_dicts(data):
    """
    check if data is list of dicts
    """

    return isinstance(data, list) and all(isinstance(entry, dict) for entry in data)


def format_date(_date):
    """
    format date as YYYY-MM-DD, or no date if malformed
    """

    if isinstance(_date, int):
        return datetime.fromtimestamp(_date // 1000.0).strftime("%Y-%m-%d")
    if isinstance(_date, (date, datetime)):
        return _date.strftime("%Y-%m-%d")
    try:
        parts = str(_date).replace("/", "-").split("-")
        parts += ["1"] * (3 - len(parts))
        return date(*[int(part) for part in parts]).isoformat()
    except Exception:
        return ""


def load_data(path):
    """
    read data from yaml or json file
    """

    # convert to path object
    path = Path(path)

    # check if file exists
    if not path.is_file():
        raise Exception("Can't find file")

    # try to open file
    try:
        file = open(path, encoding="utf8")
    except Exception as e:
        raise Exception(e or "Can't open file")

    # try to parse as yaml
    try:
        with file:
            data = yaml.load(file, Loader=SafeLoader)
    except Exception:
        raise Exception("Can't parse file. Make sure it's valid YAML.")

    # if no errors, return data
    return data


def save_data(path, data):
    """
    write data to yaml file
    """

    # convert to path object
    path = Path(path)

    class Dumper(yaml.SafeDumper):
        def ignore_aliases(self, data):
            return True

    content = "# DO NOT EDIT, GENERATED AUTOMATICALLY\n\n"
    content += yaml.dump(data, Dumper=Dumper, sort_keys=False, allow_unicode=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf8", dir=path.parent, delete=False) as file:
            temporary = file.name
            file.write(content)
        os.replace(temporary, path)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)


def retry_request(request, attempts=3):
    """Bounded backoff. Callers validate inside request so errors are not cached."""
    for attempt in range(attempts):
        try:
            return request()
        except Exception:
            if attempt == attempts - 1:
                raise
            time.sleep(2 ** attempt)


@log_cache
@cache.memoize(name="manubot:v2", expire=7 * (60 * 60 * 24))
def cite_with_manubot(_id):
    """
    generate citation data for source id with Manubot
    """

    # run manubot
    try:
        commands = ["manubot", "cite", _id, "--log-level=WARNING"]
        output = subprocess.run(commands, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, timeout=60)
    except Exception as e:
        log(e, indent=3)
        raise Exception("Manubot could not generate citation")

    # parse results as json
    try:
        manubot = json.loads(output.stdout)[0]
    except Exception:
        raise Exception("Couldn't parse Manubot response")

    # new citation with only needed info
    citation = {}

    # original id
    citation["id"] = _id

    # title
    citation["title"] = get_safe(manubot, "title", "").strip()

    # authors
    citation["authors"] = []
    for author in get_safe(manubot, "author", {}):
        given = get_safe(author, "given", "").strip()
        family = get_safe(author, "family", "").strip()
        if given or family:
            citation["authors"].append(" ".join([given, family]))

    # publisher
    container = get_safe(manubot, "container-title", "").strip()
    collection = get_safe(manubot, "collection-title", "").strip()
    publisher = get_safe(manubot, "publisher", "").strip()
    citation["publisher"] = container or publisher or collection or ""

    # extract date part
    def date_part(citation, index):
        try:
            return citation["issued"]["date-parts"][0][index]
        except (KeyError, IndexError, TypeError):
            return ""

    # date
    year = date_part(manubot, 0)
    if year:
        # fallbacks for month and day
        month = date_part(manubot, 1) or "1"
        day = date_part(manubot, 2) or "1"
        citation["date"] = format_date(f"{year}-{month}-{day}")
    else:
        # if no year, consider date missing data
        citation["date"] = ""

    # link
    citation["link"] = get_safe(manubot, "URL", "").strip()
    if manubot.get("type"):
        citation["type"] = manubot["type"]

    # return citation data
    return citation
