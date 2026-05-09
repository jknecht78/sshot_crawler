from typing import List, Literal, Optional
from pydantic import BaseModel


AdType = Literal[
    "banner", "video", "native", "popup", "interstitial",
    "sponsored-content", "search-ads", "social-ads"
]


class PageAnalysis(BaseModel):
    title:    Optional[str]  = None
    language: Optional[str]  = None
    summary:  Optional[str]  = None
    topics:   Optional[List[str]] = None
    category: Optional[Literal[
        "news", "encyclopedia", "e-commerce", "blog", "social-media",
        "docs", "forum", "government", "entertainment", "finance",
        "health", "tech", "other"
    ]] = None
    blocked:  Optional[bool] = None
    has_ads:  Optional[bool] = None
    ad_types: Optional[List[AdType]] = None
