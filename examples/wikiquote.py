
import wikiquote
from barebonesbot import BarebonesBot, RetryException


MISSING_AUTHOR = "Couldn't find author '{author}' in wikiquote"
DISAMB_AUTHOR = "Couldn't disambiguate author '{author}' in wikiquote"


class WikiQuoteBot(BarebonesBot):
    def __init__(self, config_file, *args, **kwargs):
        super(WikiQuoteBot, self).__init__(config_file, *args, **kwargs)

    def get_selection(self, author):
        try:
            return wikiquote.quotes(author)
        except wikiquote.utils.NoSuchPageException:
            msg = MISSING_AUTHOR.format(author=author)
            raise RetryException(msg, author)
        except wikiquote.utils.DisambiguationPageException:
            msg = DISAMB_AUTHOR.format(author=author)
            raise RetryException(msg, author)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("config_file")
    parser.add_argument("-r", "--real-run", action="store_true", default=False)
    args = parser.parse_args()

    # dry run by default
    client = WikiQuoteBot(args.config_file, debug=not args.real_run)
    client.run()
