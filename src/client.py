
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


class TwitterClient(UserClient):
    def __init__(self, config_file, terms_file,
                 history_file=utils.get_history_file(), max_retries=10,
                 debug=False):
        config = utils.parse_config(config_file)
        super(TwitterClient, self).__init__(
            config["tokens"]["consumer_key"],
            config["tokens"]["consumer_secret"]
        )
        self.debug = debug
        self.max_retries = max_retries
        self.terms_file = terms_file

    def _tweet(self, message):
        if self.debug:
            print(message)
        else:
            self.api.statuses.update.post(status=message)

    def tweet_quote(self, author, quote):
        tweet = utils.TWEET.format(author=author, quote=quote)
        if len(tweet) <= 140:
            self._tweet(tweet)
        else:
            sents = list(split_single(quote))
            if len(sents) > 3 or len(quote) > 500:
                msg = DISMISS_SENT % (author, len(sents), len(quote), quote)
                raise utils.RetryException(msg, author)
            else:
                subtweets = list(utils.partition_quote(author, sents))
                for part, tweet in subtweets:
                    part += 1
                    tweet += utils.PART.format(part=part, total=len(subtweets))
                    self._tweet(tweet)

    def pick_author(self, penalize_repeat=2):
        authors_hist = utils.read_terms(self.terms_file)
        authors, hist = zip(*authors_hist.items())
        weights = utils.compute_weights(hist, penalize_repeat)
        probs = utils.transform_weights(weights)
        pick = utils.weighted_choice(authors, probs)
        return pick, authors_hist[pick]

    def pick_quote(self, author, author_hist):
        try:
            quotes = wikiquote.quotes(author)
            hist = Counter(utils.read_terms(self.terms_file)[author])
            weights = utils.transform_weights([hist[q] for q in quotes])
            return utils.weighted_choice(quotes, weights)
        except wikiquote.utils.NoSuchPageException:
            msg = MISSING_AUTHOR.format(author=author)
            raise utils.RetryException(msg, author)
        except wikiquote.utils.DisambiguationPageException:
            msg = DISAMB_AUTHOR.format(author=author)
            raise utils.RetryException(msg, author)

    def register(self, author, quote):
        with open(self.terms_file, 'r+') as f:
            lines = f.readlines()
            f.seek(0), f.truncate()
            for line in lines:
                if line.startswith(author):
                    hash_str = hashlib.md5(quote.encode()).hexdigest()
                    line = line.strip() + "," + hash_str + "\n"
                f.write(line)

    def run(self):
        retries = 0
        while retries < self.max_retries:
            try:
                wait = min(30 * 60, retries * random.randint(50, 100))
                if wait:
                    utils.logger.info("Waiting [%d] secs" % wait)
                    time.sleep(wait)
                author, author_hist = self.pick_author()
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
    client = TwitterClient("../config.json", "terms.txt", debug=True)
    client.run()
