
import hashlib
import time
import random
from collections import Counter

from birdy.twitter import UserClient

from . import utils

DISMISS_TWEET = "Dismissing too long tweet by %s (%d characters):\n\t%s"
SKIP = "Skipped referrer [{referrer}]. Reason [{message}]"


class BarebonesBot(UserClient):
    """A configurable Twitter Bot that tweets stuff

    Parameters:
    -----------
    config_file : str
        Path to the JSON config file. It must at least contain the values
        for ["tokens"]["consumer_key"] and ["tokens"]["consumer_secret"].
    username : str, optional
        Twitter username used to group complex tweets using replies. It is
        used to compute the extra length of the tweet taken by the user
        mention. Username will be considered 15-char long (i.e. Twitter's
        username max length) if not given.
    referrers : list, optional
        List of referrers to be used to retrieve tweets. It will overwrite
        the corresponding value in the config file if available.
    hist_file : str, optional
        path to the history file, it will override the value in the config
        file if available and the default "~/.WikiQuoteBot".
    max_chars : int, optional
        Maximum length of a quote in characters allowed. It will overwrite
        the corresponding value in the config file if available.
    max_retries : int, optional
        Maximum number of retries on failing tweet attempt (e.g. caused by
        unavailability of the author in wikiquote, ...). It will overwrite
        the corresponding value in the config file if available.
    penalize : int, optional
        A parameter to tune the degree of downsampling of referrers or messages
        that have already been sampled. It will overwrite
        the corresponding value in the config file if available.
    debug : bool, optional
        Run the module in debug mode.
    """
    def __init__(self, config_file,
                 username=None, referrers=None, hist_file=None,
                 max_chars=500, max_retries=10, penalize=2,
                 debug=False):
        config = utils.parse_config(config_file)
        tokens = config.get("tokens", {})
        super(BarebonesBot, self).__init__(
            tokens.get("consumer_key", ""),
            tokens.get("consumer_secret", ""),
            tokens.get("access_token", ""),
            tokens.get("access_token_secret", "")
        )
        self.username = username or config.get("username")
        self.hist_file = \
            hist_file or \
            config.get("hist_file") or \
            utils.get_history_file()
        self.referrers = referrers or config.get("referrers")
        self.max_chars = config.get("max_chars") or max_chars
        self.penalize = config.get("penalize") or penalize
        self.max_retries = config.get("max_retries") or max_retries
        self.debug = debug

    def _tweet(self, status, reply_id=None, reply_name=None):
        if reply_id and reply_name:
            status = utils.REPLY_PREFIX.format(username=reply_name) + status

        utils.logger.info("TWEETED [%d chars]: %s" % (len(status), status))

        if not self.debug:
            if reply_id and reply_name:
                tweet_data = self.api.statuses.update.post(
                    status=status,
                    in_reply_to_status_id=reply_id)
            else:
                tweet_data = self.api.statuses.update.post(status=status)
            return tweet_data.data

    def tweet_message(self, referrer, message):
        """Tweet a text by processing it to match Twitter max-lenght
        restrictions as well as adding referrer and part info.
        Texts longer than 140 are splited and later parts are tweeted
        as reply to the previous part.

        Parameters:
        -----------
        referrer : str

        quote : str
        """
        tweet = utils.TWEET.format(referrer=referrer, tweet=message)
        if len(tweet) <= 140:
            self._tweet(tweet)
        else:
            name, tweet_id = None, None
            if len(message) > self.max_chars:
                error = DISMISS_TWEET % (referrer, len(message), message)
                raise utils.RetryException(error, referrer)
            else:
                tweets = list(utils.partition_tweet(
                    referrer, message, self.username))
                for part, tweet in tweets:
                    tweet = utils.TWEET.format(referrer=referrer, tweet=tweet)
                    tweet += utils.PART.format(part=part+1, total=len(tweets))
                    if tweet_id and name:
                        self._tweet(tweet, reply_id=tweet_id, reply_name=name)
                    else:
                        tweet_data = self._tweet(tweet)
                        tweet_id = tweet_data.get("id")
                        name = tweet_data.get("user", {}).get("screen_name")

    def pick_referrer(self, hist):
        """Sample a referrer from the input referrers taking into account the
        record of tweets by the bot: already tweeted referrers are downsample
        based on their frequency.

        Parameters:
        -----------
        hist : dict
            Dict from referrers to tweet history as per utils.read_history
        """
        referrers, hist = zip(*hist.items())
        weights = utils.compute_weights(hist, self.penalize)
        probs = utils.transform_weights(weights)
        pick = utils.weighted_choice(referrers, probs)
        return pick

    def pick_message(self, referrer, hash_hist):
        """Sample a quote from the picked referrer taking into account the
        record of tweets by the bot: already tweeted messages are downsample
        based on their frequency.

        Parameters:
        -----------
        referrer : str
            A name with which the tweet is associated. E.g: an author, actor...
        hist : list
            List of message hashes of tweets by the picked referrer
        """
        messages = self.get_selection(referrer)
        counts = Counter(hash_hist)
        ws = [counts[message] * self.penalize for message in messages]
        return utils.weighted_choice(messages, utils.transform_weights(ws))

    def get_selection(self, referrer):
        raise NotImplementedError

    def register(self, referrer, message):
        """Register referrer and hash of message of a newly tweeted message

        Parameters:
        -----------
        referrer : str
            Referrer name
        message : str
            Message text
        """
        wrote_referrer = False
        hash_str = hashlib.md5(message.encode()).hexdigest()
        with utils.touchopen(self.hist_file, 'r+') as f:
            lines = f.readlines()
            f.seek(0), f.truncate()
            for line in lines:
                if line.startswith(referrer):
                    wrote_referrer = True
                    line = line.strip() + "," + hash_str + "\n"
                f.write(line)
            if not wrote_referrer:
                f.write(referrer + "," + hash_str + "\n")

    def run(self):
        """Runs a tweet attempt"""
        retries = 0
        while retries < self.max_retries:
            try:
                wait = min(30 * 60, retries * random.randint(50, 100))
                if wait:
                    utils.logger.info("Waiting [%d] secs" % wait)
                    time.sleep(wait)
                hist = utils.read_history(self.hist_file)
                hist = {ref: hist.get(ref, []) for ref in self.referrers}
                referrer = self.pick_referrer(hist)
                message = self.pick_message(referrer, hist.get(referrer, []))
                self.tweet_message(referrer, message)
                self.register(referrer, message)
                return
            except utils.RetryException as e:
                retries += 1
                utils.logger.info(SKIP.format(
                    referrer=referrer, message=e.message))
        else:
            utils.logger.info("Reached max retries [%d]" % self.max_retries)
