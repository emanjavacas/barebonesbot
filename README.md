# barebonesbot
A configurable Twitter-bot

This is a Python project to quickly implement Twitter bots that post authored content. 
It aims at providing the barebones of the Twitter bot, so that users only have to care about computing the content. 
It uses the clever "birdy" library to manage the Twitter API calls (including authentication).

To create a Bot using this library, you need:

 - Twitter app credentials (https://apps.twitter.com/app/new)
 - Subclass `barebonesbot.BarebonesBot` overwritting the `get_selection` method (which takes a single string argument `referrer` holding the value of the randomly picked `referrer` from the `referrers` entry in the config file).
 
To run your bot you need:
 - A configuration file specifying Twitter app credentials, a list of `referrers` (names that are used to associate content with), and optionally other configuration variables.
 
An example using WikiQuote to extract quotes from the internet can be found in the examples directory of the repository.
