
import hashlib
import time
import random
from collections import Counter

from segtok.segmenter import split_single
from birdy.twitter import UserClient
import wikiquote

import utils

DISMISS_SENT = "Dismissing too long quote by %s " + \
               "(%d sentences, %d characters):\n\t%s"
MISSING_AUTHOR = "Couldn't find author '{author}' in wikiquote"
DISAMB_AUTHOR = "Couldn't disambiguate author '{author}' in wikiquote"


class WikiQuoteBot(UserClient):
    """A configurable Twitter Bot that tweets quotes from WikiQuote

    Parameters:
    -----------
    config_file : str
        Path to the JSON config file. It must at least contain the values
        for ["tokens"]["consumer_key"] and ["tokens"]["consumer_secret"].
    terms_file : str
        Path to a file with terms (possibly author names) to query for.
        Format is one term per line (commas are not allowed).
    max_chars : int, optional
        Maximum length of a quote in characters allowed. It will be overwritten
        by the corresponding value in the config file if available.
    max_sents : int, optional
        Maximum length of a quote in sents allowed. It will be overwritten
        by the corresponding value in the config file if available.
    max_retries : int, optional
        Maximum number of retries on failing tweet attempt (caused by
        unavailability of the author in wikiquote, ...). It will be overwritten
        by the corresponding value in the config file if available.
    penalize : int, optional
        A parameter to tune the degree of downsampling of authors or quotes
        that have already been sampled. It will be overwritten
        by the corresponding value in the config file if available.
    debug : bool, optional
        Run the module in debug mode.
    """
    def __init__(self, config_file, authors=None, hist_file=None,
                 max_sents=3, max_chars=500, max_retries=10, penalize=2,
                 debug=False):
        config = utils.parse_config(config_file)
        tokens = config.get("tokens", {})
        super(WikiQuoteBot, self).__init__(
            tokens.get("consumer_key", ""),
            tokens.get("consumer_secret", ""),
            tokens.get("access_token", ""),
            tokens.get("access_token_secret", "")
        )
        self.hist_file = hist_file or utils.get_history_file()
        self.authors = authors or config.get("authors")
        self.max_sents = config.get("max_sents") or max_sents
        self.max_chars = config.get("max_chars") or max_chars
        self.penalize = config.get("penalize") or penalize
        self.max_retries = config.get("max_retries") or max_retries
        self.debug = debug

    def _tweet(self, message):
        utils.logger.info("TWEETED: " + message)
        if not self.debug:
            tweet_data = self.api.statuses.update.post(status=message)
            utils.logger.info(str(tweet_data))

    def tweet_quote(self, author, quote):
        """Tweet a quote by a given author processing the text to
        match Twitter max-lenght restrictions.

        Parameters:
        -----------
        author : str
            Name of the author to be tweeted as per self.authors.
        quote : str
            Text of the quote to be tweeted.
        """
        tweet = utils.TWEET.format(author=author, quote=quote)
        if len(tweet) <= 140:
            self._tweet(tweet)
        else:
            sents = list(split_single(quote))
            if len(sents) > self.max_sents or len(quote) > self.max_chars:
                msg = DISMISS_SENT % (author, len(sents), len(quote), quote)
                raise utils.RetryException(msg, author)
            else:
                subtweets = list(utils.partition_quote(author, sents))
                for part, tweet in subtweets:
                    part += 1
                    tweet += utils.PART.format(part=part, total=len(subtweets))
                    self._tweet(tweet)

    def pick_author(self, authors_hist):
        """Sample an author from the input authors taking into account the
        record of tweets by the bot: already tweeted authors are downsample
        based on their frequency.

        Parameters:
        -----------
        authors_hist : dict
            Dictionary from authors to tweet history as per utils.read_history
        """
        authors, hist = zip(*authors_hist.items())
        weights = utils.compute_weights(hist, self.penalize)
        probs = utils.transform_weights(weights)
        pick = utils.weighted_choice(authors, probs)
        return pick, authors_hist[pick]

    def pick_quote(self, author, author_hist):
        """Sample a quote from the picked author taking into account the
        record of tweets by the bot: already tweeted quotes are downsample
        based on their frequency.

        Parameters:
        -----------
        author : str
            Author name
        author_hist : list
            List of quote hashes of already tweeted quotes by the picked author
        """
        try:
            qs = wikiquote.quotes(author)
            counts = Counter(author_hist)
            weights = [counts[q] * self.penalize for q in qs]
            return utils.weighted_choice(qs, utils.transform_weights(weights))
        except wikiquote.utils.NoSuchPageException:
            msg = MISSING_AUTHOR.format(author=author)
            raise utils.RetryException(msg, author)
        except wikiquote.utils.DisambiguationPageException:
            msg = DISAMB_AUTHOR.format(author=author)
            raise utils.RetryException(msg, author)

    def register(self, author, quote):
        """Register author and hash of quote of a newly tweeted quote

        Parameters:
        -----------
        author : str
            Author name
        quote : str
            Quote text
        """
        wrote_author = False
        hash_str = hashlib.md5(quote.encode()).hexdigest()
        with utils.touchopen(self.hist_file, 'r+') as f:
            lines = f.readlines()
            f.seek(0), f.truncate()
            for line in lines:
                if line.startswith(author):
                    wrote_author = True
                    line = line.strip() + "," + hash_str + "\n"
                f.write(line)
            if not wrote_author:
                f.write(author + "," + hash_str + "\n")

    def run(self):
        """Runs a tweet attemp"""
        retries = 0
        while retries < self.max_retries:
            try:
                wait = min(30 * 60, retries * random.randint(50, 100))
                if wait:
                    utils.logger.info("Waiting [%d] secs" % wait)
                    time.sleep(wait)
                authors_hist = utils.read_history(self.hist_file, self.authors)
                author, author_hist = self.pick_author(authors_hist)
                quote = self.pick_quote(author, author_hist)
                self.tweet_quote(author, quote)
                self.register(author, quote)
                return
            except utils.RetryException as e:
                retries += 1
                utils.logger.info(
                    "Skipped author [%s]. Reason [%s]" % (author, e.message))
        else:
            utils.logger.info("Reached max retries [%d]" % self.max_retries)

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("config_file")
    parser.add_argument("-r", "--real-run", action="store_true", default=False)
    args = parser.parse_args()

    # dry run by default
    client = WikiQuoteBot(args.config_file, debug=not args.real_run)
    client.run()
