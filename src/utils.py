
import json
import os
import sys
from collections import Counter

from random import random
from itertools import takewhile

import logging
logging.basicConfig(
    level=logging.INFO, format='%(asctime)s: %(message)s')
logger = logging.getLogger(__name__)

PART = ' ({part}/{total})'
REPLY_PREFIX = '@{username} '
MAX_LENGTH = 140
TWEET = '{referrer}: "{tweet}"'


class ConfigParseException(Exception):
    def __init__(self, message, errors):
        super(self, ConfigParseException).__init__(message)
        self.errors = errors


class RetryException(Exception):
    def __init__(self, message, referrer):
        super(RetryException, self).__init__(message)
        self.message = message
        self.referrer = referrer


def get_history_file():
    return os.path.join(os.path.expanduser("~"), ".BarebonsBot")


def parse_config(path_to_config):
    with open(path_to_config, 'r') as f:
        config = json.load(f)
    try:
        config["tokens"]
    except KeyError:
        raise ConfigParseException('Missing attribute', 'tokens')
    try:
        config["tokens"]["consumer_key"]
    except KeyError:
        raise ConfigParseException('Missing attribute', 'consumer_key')
    try:
        config["tokens"]["consumer_secret"]
    except KeyError:
        raise ConfigParseException('Missing attribute', 'consumer_secret')
    return config


def touchopen(filename, *args, **kwargs):
    """
    Ensure the file exists before a open-truncate (r+) file mode open
    """
    open(filename, "a").close()  # "touch" file
    return open(filename, *args, **kwargs)


def read_history(history_file):
    """
    Returns a dict of referrer names to their tweet history.
    Each entry in the tweet history is a hash of a succesfully tweeted quote
    """
    try:
        with open(history_file, 'r') as f:
            output = {}
            for line in f:
                referrer, *hist = line.split(",")
                output[referrer.strip()] = hist
            return output
    except FileNotFoundError:
        return {}
    except IOError:
        logger.info("Couldn't open history file [%s]" % history_file)
        raise sys.exit(1)


def get_max_length(referrer, username, idx):
    boilerplate = TWEET.format(referrer=referrer, tweet="")
    boilerplate += PART.format(part=idx, total=10)  # assume 1 char more
    if idx > 0:
        username = username or "a15charlongname"
        boilerplate += REPLY_PREFIX.format(username=username)
    return MAX_LENGTH - len(boilerplate)


def partition_text(sent, max_length):
    """
    partitions a tokenized sent in chunks of max possible
    length that is less than `max_length`. `max_length` can
    be altered by a coroutine using generator.send()
    """
    acc, comax_length = "", None
    sent.reverse()
    while sent:
        next_word = sent.pop()
        if len(acc) + len(next_word) < (comax_length or max_length):
            acc += next_word + " "
        else:
            comax_length = yield acc.strip()
            acc = next_word + " "
    else:
        yield acc.strip()


def partition_tweet(referrer, tweet, username):
    """
    partitions a text to be tweeted in tweets according to Twitter length.
    """
    idx, comax_length = 0, None
    max_length = get_max_length(referrer, username, idx)
    subtweets = partition_text(tweet.split(), max_length)
    while True:
        try:
            subsubtweet = subtweets.send(comax_length)
            yield idx, subsubtweet
            idx += 1
            comax_length = get_max_length(referrer, username, idx)
        except StopIteration:
            break


def accumulate(iterator):
    cur = 0
    for value in iterator:
        cur += value
        yield cur


def weighted_choice(items, weights):
    """
    shamelessly taken from:
    http://stackoverflow.com/questions/10803135/weighted-choice-short-and-simple/

    Return a random item from objects, with the weighting defined by weights
    (which must sum to 1).
    """
    limit = random()
    pick = sum(takewhile(bool, (v < limit for v in accumulate(weights))))
    return items[pick]


def laplace_smooth(weights, alpha=1):
    """
    Additive smoothing
    """
    return [weight + alpha for weight in weights]


def compute_weights(items, penalize):
    """
    Computes a list of weights from a list of lists of items, applying
    some penalization on items that are repeated in the input.
    """
    return [sum(val * penalize for val in Counter(x).values()) for x in items]


def transform_weights(weights):
    """
    Transform a list of weights, inverting them, using additive smoothing and
    squashing into a probability distribution.
    """
    inversed = [max(weights) - v for v in weights]
    smoothed = laplace_smooth(inversed)
    return [val / sum(smoothed) for val in smoothed]
