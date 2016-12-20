
import hashlib

from segtok.segmenter import split_single
from birdy.twitter import UserClient
import wikiquote
import utils

DISMISS_SENT = "Dismissing too long quote by %s" + \
               "[%d sentences, %d characters]:\n\t%s"
MISSING_AUTHOR = "Couldn't find author [{author}] in wikiquote"


class TwitterClient(UserClient):
    def __init__(self, config_file, source_file,
                 history_file=utils.get_history_file(), max_retries=10):
        config = utils.parse_config(config_file)
        super(TwitterClient, self).__init__(
            config["tokens"]["consumer_key"],
            config["tokens"]["consumer_secret"]
        )
        self.max_retries = max_retries
        self.source_file = source_file

    def _tweet(self, message):
        # self.api.statuses.update.post(status=message)
        print(message)

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
                    tweet += utils.PART.format(part=part, total=len(subtweets))
                    self._tweet(tweet)

    def pick_author(self, penalize_repeat=2):
        authors, hist = zip(*utils.read_source(self.source_file))
        weights = utils.compute_weights(hist, penalize_repeat=penalize_repeat)
        pick = utils.weighted_choice(authors, weights)
        return authors[pick], hist[pick]

    def pick_quote(self, author, author_hist):
        try:
           quotes = wikiquote.quotes(author)
           # TODO: weighted pick using hashes
        except wikiquote.utils.NoSuchPageException:
            msg = MISSING_AUTHOR.format(author=author)
            raise utils.RetryException(msg, author)

    def register(self, author, quote):
        with open(self.source_file, 'r') as infile:
            with open(self.source_file, 'w') as outfile:
                for line in infile:
                    if line.startswith(author):
                        hash_str = hashlib.md5(quote.encode()).hexdigest()
                        outfile.write(line + "," + hash_str)

    def run(self):
        retries = 0
        while retries < self.max_retries:
            try:
                author, author_hist = self.pick_author()
                quote = self.pick_quote(author, author_hist)
                self.tweet_quote(author, quote)
                self.register(author, quote)
                return
            except utils.RetryException as e:
                retries += 1
                print("Skipped author [%s]. Reason [%s]" % (author, e.message))
