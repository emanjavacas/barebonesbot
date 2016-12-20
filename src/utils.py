
import json
import os
import sys
from collections import Counter

from random import random
from itertools import takewhile


PART = ' ({part}/{total})'
MAX_LENGTH = 140 - len(PART.format(part=0, total=0))
TWEET = "{author}: {quote}"


class ConfigParseException(Exception):
    def __init__(self, message, errors):
        super(self, ConfigParseException).__init__(message)
        self.errors = errors


class RetryException(Exception):
    def __init__(self, message, author):
        super(RetryException, self).__init__(message)
        self.message = message
        self.author = author


def get_history_file():
    return os.path.join(os.path.expanduser("~"), ".EMMAQuote")


def parse_config(path_to_config):
    with open(path_to_config, 'r') as f:
        config = json.load(f)
    try:
        config["tokens"]
    except AttributeError:
        raise ConfigParseException('Missing attribute', 'tokens')
    try:
        config["tokens"]["consumer_key"]
    except AttributeError:
        raise ConfigParseException('Missing attribute', 'consumer_key')
    try:
        config["tokens"]["consumer_secret"]
    except AttributeError:
        raise ConfigParseException('Missing attribute', 'consumer_secret')
    return config


def read_source(source_file):
    """
    Returns a dict of author names to their tweet history.
    Each entry in the tweet history is a hash of a succesfully tweeted quote
    """
    try:
        with open(source_file, 'r') as f:
            output = []
            for line in f:
                author, *hist = line.split()
                hist = hist.split(',') if hist else []
                output.append(tuple(author, hist))
            return output
    except FileNotFoundError:
        print("Couldn't open source file [%s]" % source_file)
        raise sys.exit(1)


def partition_sent(sent, max_length):
    """
    partitions a tokenized sent in chunks of max possible
    length that is less than `max_length`
    """
    acc = ""
    sent.reverse()
    while sent:
        next_word = sent.pop()
        if len(acc) + len(next_word) + 1 < max_length:
            acc += " " + next_word
        else:
            yield acc
            acc = next_word


def get_max_length(author):
    return MAX_LENGTH - len(TWEET.format(author=author, quote=""))


def partition_quote(author, sents, idx=0):
    """
    partitions a quote in sentences as per `segtok`, and further each
    sent inside a quote if its length is still longer than Twitter length.
    """
    for sent in sents:
        tweet = TWEET.format(author=author, quote=sent)
        if len(tweet) > MAX_LENGTH:
            subtweets = partition_sent(sent.split(), get_max_length(author))
            for subtweet in partition_quote(author, subtweets, idx=idx):
                yield idx, subtweet
                idx += 1
        else:
            yield idx, tweet
            idx += 1


def accumulate(iterator):
    cur = 0
    for value in iterator:
        cur += value
        yield cur


# shamelessly taken from:
# http://stackoverflow.com/questions/10803135/weighted-choice-short-and-simple/10803136#10803136


def weighted_choice(items, weights):
    """
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


def compute_weights(hist, penalize):
    """
    Transform a list of lists of hashes into a list of weights using additive
    simple additive smoothing.
    """
    vals = [sum(val * penalize for val in Counter(hs).values()) for hs in hist]
    smoothed = laplace_smooth(vals)
    inversed = [max(smoothed) - v for v in smoothed]
    return [val / sum(inversed) for val in inversed]
