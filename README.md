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
able to determine, whether an item is new when crawling is run again.

If NEWS_CRAWLERS_HOME variable is not set, home directory will be set to project root by default 

Within this location, each created spider should have its own .yaml file named

    {spider_name}_configuration.yaml

An example of configuration file contents (example_configuration.yaml):

    email_recipients: ['jost.prevc@gmail.com']
    email_body_format: "Query: {query}\nURL: {url}\nPrice: {price}\n"
    urls:
      'pet_prijateljev': https://example.com/?ctl=search_ads&keywords=pet+prijateljev
      'enid_blyton': https://example.com/?ctl=search_ads&keywords=enid%20blyton

Email configuration
----------------------
Next, you should configure email notification. This project uses gmail's SMTP server to send emails, and requires
your account credentials. 

Visit https://myaccount.google.com/apppasswords and generate a new app password for your account.

After the password has been generated, scraper program will need to access it through environment variables.
Add the following environment variables:

    EMAIL_USER - your email
    EMAIL_PASS - generated password for gmail account

Running the crawlers
----------------------
Run the scraper by executing the following command on the project root:

    python scrape.py spider_name

This will run specified spider and then send an email notification if any
news are found.


