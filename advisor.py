"""Extract catalog lookup requests from a chat conversation."""

from collections.abc import Sequence
import os

from openai import OpenAI, OpenAIError
from pydantic import BaseModel, ConfigDict, ValidationError


INSTRUCTIONS = """Identify the construction products the user explicitly named for comparison
in the latest message. Return their names as written, plus any retailer and specification clues
the user supplied for each product. For a follow-up selecting or correcting a previous lookup,
use the immediately preceding conversation to identify the name and carry forward relevant clues.
Use null for absent clues. Return an empty list for broad categories, generic house requirements,
greetings, unrelated questions, or requests that do not identify any particular product. Do not
invent product names, emissions values, or substitutions. Return only the structured data."""


class ProductRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    retailer: str | None
    specification: str | None


class ComparisonRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    products: list[ProductRequest]


class AdvisorUnavailable(RuntimeError):
    """The app could not extract a usable comparison request."""


def extract_requests(messages: Sequence[dict[str, str]]) -> list[ProductRequest]:
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        raise AdvisorUnavailable("Chat needs an OpenAI API key. You can still browse the catalog.")

    try:
        with OpenAI(api_key=key, timeout=15.0, max_retries=0) as client:
            response = client.responses.parse(
                model=os.environ.get("OPENAI_MODEL", "").strip() or "gpt-4o-mini",
                instructions=INSTRUCTIONS,
                input=list(messages[-8:]),
                text_format=ComparisonRequest,
                store=False,
            )
    except (OpenAIError, ValidationError) as error:
        raise AdvisorUnavailable("The chat service is unavailable. Try again or browse the catalog.") from error

    if response.status != "completed" or response.output_parsed is None:
        raise AdvisorUnavailable("Chat could not read that request. Try again with the product names.")
    return response.output_parsed.products
