import pydantic


class NewsCrawlerConfig(pydantic.BaseModel):
    notifications: dict
    urls: dict[str, str]
