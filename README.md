# News Crawlers

Contains various spiders which crawl websites for new content. If any new
content is found, users are alerted via email.

![Tests](https://github.com/jprevc/news_crawlers/actions/workflows/tests.yml/badge.svg)

Installation
------------------
Install this application with

    python -m pip install news_crawlers

After installation, News Crawlers can be run from CLI, to view help you can write:

    python -m news_crawlers -h

Configuration
----------------------------
NewsCrawlers's configuration is defined with a *news_crawlers.yaml* file.

Configuration file path can then be provided via CLI, like this:

    python -m news_crawlers -c {news_crawlers.yaml path}

If path is not provided, application will search the file in *config* folder (if it exists) and in the current working
directory.

When spider is run, it will append any new items found in *.nc_cache* folder. Location of that folder can be customized
with a --cache option, like this

python -m news_crawlers --cache {data path}

If not specified, application will put cache to *data/.nc_cache*, relative to current working directory.

Within the configuration file, there should be a *spiders* segment, where spiders and their configurations are listed,
for example:

    spiders:
            example:
                notifications:
                  email:
                    email_user: "__env_EMAIL_USER"
                    email_password: "__env_EMAIL_PASS"
                    recipients: ['jost.prevc@gmail.com']
                    message_body_format: "Query: {query}\nURL: {url}\nPrice: {price}\n"
                  pushover:
                    recipients: ['ukdwndomjog3swwos57umfydpsa2sk']
                    send_separately: True
                    message_body_format: "Query: {query}\nPrice: {price}\n"
                urls:
                  'pet_prijateljev': https://example.com/?ctl=search_ads&keywords=pet+prijateljev
                  'enid_blyton': https://example.com/?ctl=search_ads&keywords=enid%20blyton

Spider name (for example "example", above), should match the *name* attribute of a spider, defined in spiders.py.
Each spider should have a *notifications* and *urls* segment. *notifications* defines how user(s) will be notified on
any found changes when crawling the urls, defined in *urls* segment.

Note that prepending any configuration value with "\_\_env\_" will treat the subsequent string as an environment
variable and will attempt to obtain the value from environment variables. For example "__env_EMAIL_USER" will
be replaced with the value of "EMAIL_USER" environment variable. This can be useful to avoid storing secrets within the
configuration file.

Crawling can also be set on a schedule, by adding a schedule segment to news_crawlers.yaml file:

    schedule:
        every: 15
        units: minutes

So the entire *news_crawlers.yaml* file should look like this:

    schedule:
        every: 15
        units: minutes
    spiders:
        example:
            notifications:
              email:
                email_user: "__env_EMAIL_USER"
                email_password: "__env_EMAIL_PASS"
                recipients: ['jost.prevc@gmail.com']
                message_body_format: "Query: {query}\nURL: {url}\nPrice: {price}\n"
              pushover:
                recipients: ['ukdwndomjog3swwos57umfydpsa2sk']
                send_separately: True
                message_body_format: "Query: {query}\nPrice: {price}\n"
            urls:
              'pet_prijateljev': https://example.com/?ctl=search_ads&keywords=pet+prijateljev
              'enid_blyton': https://example.com/?ctl=search_ads&keywords=enid%20blyton

Notification configuration
------------------------------
Next, you should configure notification, which will alert you about any found news. Currently, there are two options -
Email via Gmail SMTP server or Pushover.

### Email configuration

Visit [google app passwords](https://myaccount.google.com/apppasswords) and generate a new app password for your account.

Username and password can then be placed directly to configuration file or referenced via environment variables
(see instructions above).

### Pushover configuration

[Pushover](https://pushover.net) is a platform which enables you to easily send and receive push notifications on your
smart device. To get it running, you will first need to create a user account. You can sign-up on
this [link](https://pushover.net/signup). When sign-up is complete, you will receive a unique user token, which you
will have to copy and paste to your crawler configuration (see example configuration above). Any user that wants to
receive push notifications needs to create its own pushover username to receive their own user tokens, which will
be stored in crawler configuration.

Next, you should register your crawler application on pushover. To do this, visit [registration site](https://pushover.net/apps/build)
and fill out the provided form. Once your application is registered, you will receive an API token. This token can then
be placed directly to configuration file or referenced via environment variables (see instructions above).

To receive notifications, every user should download the Pushover app to the smart device on which they want to
receive push notifications. Once logged in, they will receive push notifications when any crawler finds news.

- [Android](https://play.google.com/store/apps/details?id=net.superblock.pushover)
- [AppStore](https://apps.apple.com/us/app/pushover-notifications/id506088175?ls=1)

Note: Pushover trial version expires after 30 days. After that, you will need to create a one-time purchase with a cost
of 5$ to keep it working, see [pricing](https://pushover.net/pricing).


Running the crawlers
----------------------
Run the scraper by executing the following command on the project root:

    python -m news_crawlers scrape

You can also run individual spiders with

    python -m news_crawlers scrape -s {spider_name}


This will run specified spider and then send a configured notifications if any
news are found.

Contribution
==================

Checkout
----------------
Checkout this project with

    git clone https://github.com/jprevc/news_crawlers.git

Adding new custom crawlers
----------------------------

New spiders need to be added to news_crawlers/spiders.py file. Spider is a class which must subclass Spider class.

When crawling, crawler needs to yield all found items in a form of dictionary. Keys of each item need to correspond to
referenced values of "message_body_format" field within the configuration file.
