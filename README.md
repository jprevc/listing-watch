# News Crawlers
Contains various spiders which crawl websites for new content. If any new
content is found, users are alerted via email.


Checkout
----------------
Checkout this project with

    git clone https://github.com/jprevc/news_crawlers.git


Environment configuration
----------------------------
NewsCrawlers needs configuration for each spider. This configuration is provided
in user defined .yaml files. Location of those files should be set as an environment variable.
Define new environment variable named NEWS_CRAWLERS_HOME and set its path to location
where configuration will be stored. 

This location will also be used to store all crawled items (cache), so program will be 
able to determine, whether a crawled item is new when crawling is run again.

If NEWS_CRAWLERS_HOME variable is not set, home directory will be set to project root by default.

Within this location, each created spider should have its own .yaml file named

    {spider_name}_configuration.yaml

An example of configuration file contents (example_configuration.yaml):

    notifications:
      email:
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
Email via Gmail SMTP server or Pushover (https://pushover.net/).

### Email configuration

Visit https://myaccount.google.com/apppasswords and generate a new app password for your account.

After the password has been generated, scraper program will need to access it through environment variables.
Add the following environment variables:

    EMAIL_USER - your email
    EMAIL_PASS - generated password for gmail account

### Pushover configuration

Pushover is a platform which enables you to easily send and receive push notifications on your smart device. 
To get it running, you will first need to create a user account. You can sign-up on this link: 
https://pushover.net/signup. When sign-up is complete, you will receive a unique user token, which you will have to 
copy and paste to your crawler configuration (see example configuration above). Any user that wants to receive push 
notifications needs to create its own pushover username to receive their own user tokens, which will be stored in
crawler configuration.

Next, you should register your crawler application on pushover. To do this, visit https://pushover.net/apps/build and 
fill out the provided form. Once your application is registered, you will receive an API token. This token then needs 
to be stored in the environment variables under the name 'PUSHOVER_APP_TOKEN'. This needs to be done on the machine 
where NewsCrawler will run.

To receive notifications, every user should download the Pushover app to the smart device on which they want to 
receive push notifications. Once logged in, they will receive push notifications when any crawler finds news.

Android: https://play.google.com/store/apps/details?id=net.superblock.pushover  
AppStore: https://apps.apple.com/us/app/pushover-notifications/id506088175?ls=1

Note: Pushover trial version expires after 30 days. After that, you will need to create a one-time purchase with a cost 
of 5$ to keep it working: https://pushover.net/pricing


Running the crawlers
----------------------
Run the scraper by executing the following command on the project root:

    python scrape.py spider_name

This will run specified spider and then send an email notification if any
news are found.


Adding new custom crawlers
----------------------------

New crawlers need to be added to news_crawlers/spiders folder. Crawler is a class which must subclass scrapy.Spider.
This class needs to be written in a separate file called {spider_name}_spider.py.

When crawling, crawler needs to yield all found items in a form of dictionary (see https://docs.scrapy.org/en/latest/
for more information about how crawlers are created). Created crawler will then automatically be run when scrape.py 
is run, which will also handle checking whether any of the crawled items are new. In this case, a notification will be
sent to all users.
